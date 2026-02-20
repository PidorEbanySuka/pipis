import json
import os
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.parse


# Ожидаем в Vercel Environment Variables:
# YC_API_KEY     = API-ключ сервисного аккаунта (тот, что ты создал с scope yc.ai.translate.execute)
# YC_FOLDER_ID   = folder id (b1g...)


YANDEX_IAM_TOKEN_URL = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
YANDEX_TRANSLATE_URL = "https://translate.api.cloud.yandex.net/translate/v2/translate"


def _send(h, code: int, payload: dict):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    h.send_response(code)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Access-Control-Allow-Origin", "*")
    h.send_header("Access-Control-Allow-Headers", "Content-Type")
    h.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def _read_json_body(h) -> dict:
    length = int(h.headers.get("Content-Length", "0"))
    raw = h.rfile.read(length).decode("utf-8") if length > 0 else "{}"
    return json.loads(raw)


def _yandex_get_iam_token(api_key: str) -> str:
    """
    Получаем IAM-токен по API-ключу.
    """
    payload = json.dumps({"yandexPassportOauthToken": None, "apiKey": api_key}).encode("utf-8")

    # Важно: IAM endpoint принимает JSON; поле apiKey поддерживается.
    req = urllib.request.Request(
        YANDEX_IAM_TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=12) as r:
        data = json.loads(r.read().decode("utf-8"))

    token = (data.get("iamToken") or "").strip()
    if not token:
        raise RuntimeError(f"IAM token missing in response: {data}")
    return token


def _yandex_translate(iam_token: str, folder_id: str, text: str, source: str, target: str) -> str:
    """
    Перевод через Yandex Cloud Translate v2.
    """
    # Яндекс обычно ждёт коды типа "ru", "en"
    body = {
        "folderId": folder_id,
        "texts": [text],
        "targetLanguageCode": (target or "en").strip(),
    }

    src = (source or "auto").strip().lower()
    if src != "auto":
        body["sourceLanguageCode"] = src

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        YANDEX_TRANSLATE_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {iam_token}",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=15) as r:
        resp = json.loads(r.read().decode("utf-8"))

    translations = resp.get("translations") or []
    if not translations:
        raise RuntimeError(f"No translations in response: {resp}")
    return (translations[0].get("text") or "").strip()


def _parse_http_error(e) -> dict:
    """
    Достаём максимально полезную инфу из HTTPError от Яндекса.
    """
    info = {
        "type": e.__class__.__name__,
        "status": getattr(e, "code", None),
        "reason": getattr(e, "reason", None),
    }

    try:
        raw = e.read().decode("utf-8", errors="replace")
        info["raw"] = raw[:2000]
        try:
            j = json.loads(raw)
            info["yandex"] = j
        except Exception:
            pass
    except Exception as _:
        pass

    return info


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        return _send(self, 200, {"ok": True})

    def do_POST(self):
        if self.path != "/api/translate":
            return _send(self, 404, {"error": "Not found"})

        # 1) читаем тело
        try:
            data = _read_json_body(self)
        except Exception as e:
            return _send(self, 400, {"error": "Bad JSON", "details": str(e)})

        q = (data.get("q") or "").strip()
        source = (data.get("source") or "auto").strip()
        target = (data.get("target") or "en").strip()

        if not q:
            return _send(self, 400, {"error": "Empty text"})

        # 2) ENV vars
        yc_api_key = (os.getenv("YC_API_KEY") or "").strip()
        yc_folder_id = (os.getenv("YC_FOLDER_ID") or "").strip()

        if not yc_api_key:
            return _send(self, 500, {"error": "ENV_CHECK", "details": "YC_API_KEY is not set (Vercel Env Var)"})
        if not yc_folder_id:
            return _send(self, 500, {"error": "ENV_CHECK", "details": "YC_FOLDER_ID is not set (Vercel Env Var)"})

        # 3) IAM token -> translate
        try:
            iam = _yandex_get_iam_token(yc_api_key)
            translated = _yandex_translate(iam, yc_folder_id, q, source, target)
            return _send(self, 200, {"translatedText": translated, "provider": "yandex"})
        except urllib.error.HTTPError as e:
            # Вот тут будет код/тело ошибки Яндекса
            return _send(self, 502, {"error": "Yandex Translate HTTPError", "details": _parse_http_error(e)})
        except Exception as e:
            return _send(self, 502, {"error": "Yandex Translate UnknownError", "details": str(e)})

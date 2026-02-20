import json
import os
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error

YC_API_KEY = os.getenv("YC_API_KEY", "").strip()
YC_FOLDER_ID = os.getenv("YC_FOLDER_ID", "").strip()

YANDEX_TRANSLATE_URL = os.getenv(
    "YANDEX_TRANSLATE_URL",
    "https://translate.api.cloud.yandex.net/translate/v2/translate"
).strip()


def _send_json(h, code: int, payload: dict):
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


def _yandex_translate(text: str, source: str, target: str) -> dict:
    """
    Возвращает dict с ключами:
      - ok: bool
      - translatedText: str (если ok)
      - yandex_http: int
      - yandex_code: str|None
      - yandex_message: str|None
      - yandex_details: any|None
      - raw: str|None
    """
    if not YC_API_KEY:
        return {
            "ok": False,
            "yandex_http": None,
            "yandex_code": "ENV_MISSING",
            "yandex_message": "YC_API_KEY is not set (Vercel Env Var)",
            "yandex_details": None,
            "raw": None,
        }
    if not YC_FOLDER_ID:
        return {
            "ok": False,
            "yandex_http": None,
            "yandex_code": "ENV_MISSING",
            "yandex_message": "YC_FOLDER_ID is not set (Vercel Env Var)",
            "yandex_details": None,
            "raw": None,
        }

    source = (source or "auto").strip().lower()
    target = (target or "en").strip().lower()

    payload = {
        "folderId": YC_FOLDER_ID,
        "texts": [text],
        "targetLanguageCode": target,
    }
    # Если auto — sourceLanguageCode не передаём (пусть Яндекс определяет сам)
    if source and source != "auto":
        payload["sourceLanguageCode"] = source

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        YANDEX_TRANSLATE_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {YC_API_KEY}",
            "User-Agent": "tg-miniapp-translator/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp_bytes = r.read()
            status = getattr(r, "status", 200)
    except urllib.error.HTTPError as e:
        # Это именно HTTP-ошибка от Яндекса (401/403/429/500 и т.д.)
        status = e.code
        resp_bytes = e.read() or b""
    except Exception as e:
        # Сеть/таймаут/днс и т.п.
        return {
            "ok": False,
            "yandex_http": None,
            "yandex_code": "NETWORK_ERROR",
            "yandex_message": str(e),
            "yandex_details": None,
            "raw": None,
        }

    raw_text = resp_bytes.decode("utf-8", errors="replace")

    # Пытаемся распарсить JSON (и успех, и ошибка у Яндекса часто JSON)
    try:
        resp_json = json.loads(raw_text) if raw_text else {}
    except Exception:
        resp_json = None

    if 200 <= status < 300 and isinstance(resp_json, dict):
        translations = resp_json.get("translations") or []
        out = ""
        if translations and isinstance(translations, list) and isinstance(translations[0], dict):
            out = (translations[0].get("text") or "").strip()

        return {
            "ok": True,
            "translatedText": out,
            "yandex_http": status,
            "yandex_code": None,
            "yandex_message": None,
            "yandex_details": None,
            "raw": None,
        }

    # Ошибка от Яндекса: вытаскиваем code/message/details если есть
    y_code = None
    y_msg = None
    y_details = None

    if isinstance(resp_json, dict):
        # бывает {"code":"...","message":"...","details":[...]}
        y_code = resp_json.get("code") or resp_json.get("error") or resp_json.get("status")
        y_msg = resp_json.get("message") or resp_json.get("error_description") or resp_json.get("description")
        y_details = resp_json.get("details")
    else:
        # не JSON
        y_msg = raw_text[:300] if raw_text else "Non-JSON response from Yandex"

    return {
        "ok": False,
        "yandex_http": status,
        "yandex_code": y_code or "YANDEX_ERROR",
        "yandex_message": y_msg or "Yandex Translate error",
        "yandex_details": y_details,
        "raw": raw_text[:800] if raw_text else None,
    }


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        return _send_json(self, 200, {"ok": True})

    def do_GET(self):
        # чтобы не было 404 по favicon.ico в консоли
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        return _send_json(self, 404, {"error": "Not found"})

    def do_POST(self):
        if self.path != "/api/translate":
            return _send_json(self, 404, {"error": "Not found"})

        try:
            data = _read_json_body(self)
        except Exception as e:
            return _send_json(self, 400, {"error": f"Bad JSON: {e}"})

        q = (data.get("q") or "").strip()
        source = (data.get("source") or "auto").strip()
        target = (data.get("target") or "en").strip()

        if not q:
            return _send_json(self, 400, {"error": "Empty text"})

        result = _yandex_translate(q, source, target)

        if result.get("ok"):
            return _send_json(self, 200, {"translatedText": result.get("translatedText", ""), "provider": "yandex"})

        # Пробрасываем статус Яндекса (если он есть), иначе 502/500
        upstream_status = result.get("yandex_http")
        http_status = int(upstream_status) if isinstance(upstream_status, int) else 502

        return _send_json(self, http_status, {
            "error": "Yandex Translate Error",
            "yandex_http": result.get("yandex_http"),
            "yandex_code": result.get("yandex_code"),
            "yandex_message": result.get("yandex_message"),
            "yandex_details": result.get("yandex_details"),
            "raw": result.get("raw"),
        })

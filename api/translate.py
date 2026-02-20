import json
import os
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error


YC_API_KEY = os.getenv("YC_API_KEY", "").strip()
YC_FOLDER_ID = os.getenv("YC_FOLDER_ID", "").strip()

YC_TRANSLATE_URL = os.getenv(
    "YC_TRANSLATE_URL",
    "https://translate.api.cloud.yandex.net/translate/v2/translate"
).strip()


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


def _norm_lang(code: str) -> str:
    c = (code or "").strip().lower()
    return c if c else "en"


def _yandex_translate(text: str, source: str, target: str) -> dict:
    if not YC_API_KEY:
        raise RuntimeError("YC_API_KEY is not set (Vercel Env Var)")
    if not YC_FOLDER_ID:
        raise RuntimeError("YC_FOLDER_ID is not set (Vercel Env Var)")

    target = _norm_lang(target)
    source = (source or "").strip().lower()

    body = {
        "folderId": YC_FOLDER_ID,
        "texts": [text],
        "targetLanguageCode": target,
    }
    if source and source != "auto":
        body["sourceLanguageCode"] = _norm_lang(source)

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        YC_TRANSLATE_URL,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {YC_API_KEY}",
            "User-Agent": "tg-miniapp-translator/1.0",
        },
    )

    with urllib.request.urlopen(req, timeout=15) as r:
        resp_text = r.read().decode("utf-8", errors="replace")
        resp = json.loads(resp_text)

    translations = resp.get("translations") or []
    out = (translations[0].get("text") or "") if translations else ""
    detected = (translations[0].get("detectedLanguageCode") or "") if translations else ""
    return {"text": out.strip(), "detected": detected}


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        return _send(self, 200, {"ok": True})

    def do_POST(self):
        if self.path != "/api/translate":
            return _send(self, 404, {"error": "Not found"})

        try:
            data = _read_json_body(self)
        except Exception as e:
            return _send(self, 400, {"error": f"Bad JSON: {e}"})

        q = (data.get("q") or "").strip()
        source = (data.get("source") or "auto").strip()
        target = (data.get("target") or "en").strip()

        if not q:
            return _send(self, 400, {"error": "Empty text"})

        try:
            y = _yandex_translate(q, source, target)
            return _send(self, 200, {
                "translatedText": y["text"],
                "provider": "yandex",
                "detectedLanguageCode": y.get("detected", "")
            })

        except urllib.error.HTTPError as e:
            # Показать код и тело ошибки от Яндекса
            err_body = e.read().decode("utf-8", errors="replace")
            return _send(self, 502, {
                "error": "Yandex Translate HTTPError",
                "status": e.code,
                "details": err_body[:2000],   # чтобы не раздувать ответ
                "endpoint": YC_TRANSLATE_URL
            })

        except urllib.error.URLError as e:
            return _send(self, 502, {
                "error": "Yandex Translate URLError",
                "details": str(e),
                "endpoint": YC_TRANSLATE_URL
            })

        except Exception as e:
            return _send(self, 500, {
                "error": "Yandex Translate UnknownError",
                "details": str(e),
            })

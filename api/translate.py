import json
import os
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error


YC_API_KEY = os.getenv("YC_API_KEY", "").strip()
YC_FOLDER_ID = os.getenv("YC_FOLDER_ID", "").strip()
YC_TRANSLATE_URL = "https://translate.api.cloud.yandex.net/translate/v2/translate"


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


def _read_json_body(h):
    length = int(h.headers.get("Content-Length", "0"))
    raw = h.rfile.read(length).decode("utf-8") if length > 0 else "{}"
    return json.loads(raw)


def _yc_translate(text: str, source: str, target: str) -> str:
    if not YC_API_KEY:
        raise RuntimeError("YC_API_KEY is not set")
    if not YC_FOLDER_ID:
        raise RuntimeError("YC_FOLDER_ID is not set")

    body = {
        "folderId": YC_FOLDER_ID,
        "texts": [text],
        "targetLanguageCode": (target or "en").strip(),
    }

    src = (source or "auto").strip().lower()
    # В Yandex можно авто-определение: просто не передавать sourceLanguageCode
    if src and src != "auto":
        body["sourceLanguageCode"] = src

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

    with urllib.request.urlopen(req, timeout=12) as r:
        resp = json.loads(r.read().decode("utf-8"))

    translations = resp.get("translations") or []
    if not translations:
        return ""
    # Обычно: translations[0]["text"]
    return (translations[0].get("text") or "").strip()


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
            out = _yc_translate(q, source, target)
            return _send(self, 200, {"translatedText": out, "provider": "yandex"})
        except urllib.error.HTTPError as e:
            details = ""
            try:
                details = e.read().decode("utf-8", errors="ignore")[:500]
            except Exception:
                pass
            return _send(self, 502, {
                "error": "Yandex Translate HTTPError",
                "status": e.code,
                "details": details
            })
        except Exception as e:
            return _send(self, 500, {"error": str(e)})

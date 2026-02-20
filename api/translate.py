import json
import os
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error


YC_API_KEY = os.getenv("YC_API_KEY", "").strip()
YC_FOLDER_ID = os.getenv("YC_FOLDER_ID", "").strip()

YC_URL = "https://translate.api.cloud.yandex.net/translate/v2/translate"


def _send(h, code, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    h.send_response(code)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Access-Control-Allow-Origin", "*")
    h.send_header("Access-Control-Allow-Headers", "Content-Type")
    h.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def _read_json(h):
    length = int(h.headers.get("Content-Length", "0"))
    raw = h.rfile.read(length).decode("utf-8") if length > 0 else "{}"
    return json.loads(raw)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        return _send(self, 200, {"ok": True})

    def do_POST(self):
        if self.path != "/api/translate":
            return _send(self, 404, {"error": "Not found"})

        try:
            data = _read_json(self)
        except Exception as e:
            return _send(self, 400, {"error": f"Bad JSON: {e}"})

        text = (data.get("q") or "").strip()
        source = (data.get("source") or "ru").strip()
        target = (data.get("target") or "en").strip()

        if not text:
            return _send(self, 400, {"error": "Empty text"})

        if not YC_API_KEY or not YC_FOLDER_ID:
            return _send(self, 500, {
                "error": "YC_API_KEY or YC_FOLDER_ID not set",
                "hasKey": bool(YC_API_KEY),
                "hasFolder": bool(YC_FOLDER_ID),
            })

        payload = {
            "folderId": YC_FOLDER_ID,
            "texts": [text],
            "targetLanguageCode": target,
            "sourceLanguageCode": source,
        }

        req = urllib.request.Request(
            YC_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Api-Key {YC_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                raw = r.read().decode("utf-8")
                resp = json.loads(raw)
                translated = resp["translations"][0]["text"]
                return _send(self, 200, {"translatedText": translated, "provider": "yandex"})
        except urllib.error.HTTPError as e:
            # ВАЖНО: читаем тело ошибки от Яндекса
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass

            # попробуем распарсить JSON ошибки (если он JSON)
            parsed = None
            try:
                parsed = json.loads(body) if body else None
            except Exception:
                parsed = None

            return _send(self, 502, {
                "error": "Yandex Translate HTTPError",
                "status": e.code,
                "reason": str(e.reason),
                "yandexBody": parsed if parsed is not None else body[:2000],
                "debug": {
                    "folderId": YC_FOLDER_ID,
                    "target": target,
                    "source": source,
                    "url": YC_URL
                }
            })
        except Exception as e:
            return _send(self, 502, {"error": "Yandex Translate failed", "details": str(e)})

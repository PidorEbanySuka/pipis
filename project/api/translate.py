import json
import os
import requests
from http.server import BaseHTTPRequestHandler

# Можно поставить свой инстанс LibreTranslate или официальный (часто требует API key)
LIBRETRANSLATE_URL = os.getenv("LIBRETRANSLATE_URL", "https://libretranslate.com")
LIBRETRANSLATE_KEY = os.getenv("LIBRETRANSLATE_KEY", "")  # если нужен

def _send_json(h, code: int, payload: dict):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    h.send_response(code)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    # CORS: чтобы Mini App мог дергать API
    h.send_header("Access-Control-Allow-Origin", "*")
    h.send_header("Access-Control-Allow-Headers", "Content-Type")
    h.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        _send_json(self, 200, {"ok": True})

    def do_POST(self):
        if self.path != "/api/translate":
            return _send_json(self, 404, {"error": "Not found"})

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            data = json.loads(raw)

            q = (data.get("q") or "").strip()
            source = (data.get("source") or "auto").strip()
            target = (data.get("target") or "en").strip()

            if not q:
                return _send_json(self, 400, {"error": "Empty text"})

            payload = {"q": q, "source": source, "target": target, "format": "text"}
            if LIBRETRANSLATE_KEY:
                payload["api_key"] = LIBRETRANSLATE_KEY

            resp = requests.post(f"{LIBRETRANSLATE_URL.rstrip('/')}/translate", json=payload, timeout=15)
            if resp.status_code != 200:
                return _send_json(self, 502, {"error": "Translate provider error", "details": resp.text})

            out = resp.json()
            return _send_json(self, 200, {"translatedText": out.get("translatedText", "")})

        except Exception as e:
            return _send_json(self, 500, {"error": str(e)})
import json
import os
from http.server import BaseHTTPRequestHandler

LIBRETRANSLATE_URL = os.getenv("LIBRETRANSLATE_URL", "https://libretranslate.com").rstrip("/")
LIBRETRANSLATE_KEY = os.getenv("LIBRETRANSLATE_KEY", "")

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

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        return _send_json(self, 200, {"ok": True})

    def do_POST(self):
        if self.path != "/api/translate":
            return _send_json(self, 404, {"error": "Not found"})

        # 1) читаем тело
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            data = json.loads(raw)
        except Exception as e:
            return _send_json(self, 400, {"error": f"Bad JSON: {e}"})

        q = (data.get("q") or "").strip()
        source = (data.get("source") or "auto").strip()
        target = (data.get("target") or "en").strip()

        if not q:
            return _send_json(self, 400, {"error": "Empty text"})

        # 2) импорт requests — частая причина краша на Vercel
        try:
            import requests
        except Exception as e:
            return _send_json(self, 500, {"error": f"requests import failed: {e}. Check requirements.txt in repo root."})

        payload = {"q": q, "source": source, "target": target, "format": "text"}
        if LIBRETRANSLATE_KEY:
            payload["api_key"] = LIBRETRANSLATE_KEY

        # 3) вызов провайдера
        try:
            resp = requests.post(
                f"{LIBRETRANSLATE_URL}/translate",
                json=payload,
                timeout=15,
                headers={"User-Agent": "tg-miniapp-translator/1.0"},
            )
        except Exception as e:
            return _send_json(self, 502, {"error": f"Provider request failed: {e}", "provider": LIBRETRANSLATE_URL})

        if resp.status_code != 200:
            # вернём кусок ответа, чтобы было понятно, что случилось
            return _send_json(self, 502, {
                "error": "Translate provider error",
                "status": resp.status_code,
                "details": resp.text[:300],
                "provider": LIBRETRANSLATE_URL
            })

        try:
            out = resp.json()
        except Exception as e:
            return _send_json(self, 502, {"error": f"Provider returned non-JSON: {e}", "details": resp.text[:200]})

        return _send_json(self, 200, {"translatedText": out.get("translatedText", "")})
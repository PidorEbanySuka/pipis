import json
import os
from http.server import BaseHTTPRequestHandler
import urllib.parse
import urllib.request

# Можно менять через переменную окружения в Vercel:
# LIBRETRANSLATE_URL = https://translate.argosopentech.com
LIBRETRANSLATE_URL = os.getenv("LIBRETRANSLATE_URL", "https://translate.argosopentech.com").rstrip("/")
LIBRETRANSLATE_KEY = os.getenv("LIBRETRANSLATE_KEY", "").strip()

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

def _read_json_body(h):
    length = int(h.headers.get("Content-Length", "0"))
    raw = h.rfile.read(length).decode("utf-8") if length > 0 else "{}"
    return json.loads(raw)

def _libretranslate(q: str, source: str, target: str) -> str:
    payload = {
        "q": q,
        "source": source,
        "target": target,
        "format": "text",
    }
    if LIBRETRANSLATE_KEY:
        payload["api_key"] = LIBRETRANSLATE_KEY

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=f"{LIBRETRANSLATE_URL}/translate",
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "tg-miniapp-translator/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=10) as r:
        resp = json.loads(r.read().decode("utf-8"))
    return resp.get("translatedText", "")

def _mymemory(q: str, source: str, target: str) -> str:
    params = urllib.parse.urlencode({"q": q, "langpair": f"{source}|{target}"})
    url = f"https://api.mymemory.translated.net/get?{params}"
    with urllib.request.urlopen(url, timeout=10) as r:
        resp = json.loads(r.read().decode("utf-8"))
    return resp["responseData"]["translatedText"]

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

        # Если source=auto, MyMemory auto не любит — сделаем ru как дефолт
        source_for_mymemory = "ru" if source == "auto" else source

        # 1) Пробуем LibreTranslate (обычно качество лучше)
        try:
            translated = _libretranslate(q, source, target)
            if translated:
                return _send(self, 200, {"translatedText": translated, "provider": "libretranslate"})
        except Exception as e:
            libre_error = str(e)
        else:
            libre_error = "unknown"

        # 2) Fallback на MyMemory (чтобы хоть что-то работало всегда)
        try:
            translated = _mymemory(q, source_for_mymemory, target)
            return _send(self, 200, {"translatedText": translated, "provider": "mymemory", "fallbackFrom": libre_error})
        except Exception as e:
            return _send(self, 502, {"error": f"Both providers failed: libretranslate={libre_error}; mymemory={e}"})

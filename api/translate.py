import json
import os
from http.server import BaseHTTPRequestHandler
import urllib.parse
import urllib.request


# 1) Список инстансов LibreTranslate (пробуем по очереди)
# Можно добавить свой через переменную окружения LIBRETRANSLATE_URL в Vercel
LT_URLS = [
    os.getenv("LIBRETRANSLATE_URL", "").strip(),
    "https://translate.argosopentech.com",
    "https://libretranslate.de",
    "https://translate.astian.org",
]
LT_URLS = [u.rstrip("/") for u in LT_URLS if u]

LT_KEY = os.getenv("LIBRETRANSLATE_KEY", "").strip()


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


def _libretranslate_try_one(base_url: str, q: str, source: str, target: str) -> str:
    payload = {"q": q, "source": source, "target": target, "format": "text"}
    if LT_KEY:
        payload["api_key"] = LT_KEY

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=f"{base_url}/translate",
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "tg-miniapp-translator/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=10) as r:
        resp = json.loads(r.read().decode("utf-8"))

    return (resp.get("translatedText") or "").strip()


def _libretranslate(q: str, source: str, target: str):
    """
    Возвращает (translated_text, used_base_url) или кидает исключение, если все инстансы упали.
    """
    last_err = None
    for base in LT_URLS:
        try:
            txt = _libretranslate_try_one(base, q, source, target)
            if txt:
                return txt, base
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"all libretranslate instances failed: {last_err}")


def _mymemory(q: str, source: str, target: str) -> str:
    params = urllib.parse.urlencode({"q": q, "langpair": f"{source}|{target}"})
    url = f"https://api.mymemory.translated.net/get?{params}"
    with urllib.request.urlopen(url, timeout=10) as r:
        resp = json.loads(r.read().decode("utf-8"))
    return (resp["responseData"]["translatedText"] or "").strip()


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

        # MyMemory не любит auto — подставим ru (или можешь сделать en по умолчанию)
        source_for_mymemory = "ru" if source == "auto" else source

        # 1) Пробуем LibreTranslate (качество лучше)
        try:
            translated, used = _libretranslate(q, source, target)
            return _send(self, 200, {
                "translatedText": translated,
                "provider": "libretranslate",
                "instance": used
            })
        except Exception as e:
            libre_error = str(e)

        # 2) Fallback на MyMemory (чтобы всегда что-то отвечало)
        try:
            translated = _mymemory(q, source_for_mymemory, target)
            return _send(self, 200, {
                "translatedText": translated,
                "provider": "mymemory",
                "fallbackFrom": libre_error
            })
        except Exception as e:
            return _send(self, 502, {
                "error": "Both providers failed",
                "libretranslate": libre_error,
                "mymemory": str(e)
            })

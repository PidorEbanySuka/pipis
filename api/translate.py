import json
from http.server import BaseHTTPRequestHandler
import urllib.parse
import urllib.request
import time


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


def _looks_like_garbage(src: str, dst: str) -> bool:
    """
    Очень простая проверка "похоже ли на мусор":
    - исходник короткий (1–2 слова), а перевод неожиданно длинный
    - перевод содержит слишком много слов для короткого исходника
    """
    src_words = [w for w in src.strip().split() if w]
    dst_words = [w for w in dst.strip().split() if w]

    if len(src_words) <= 2 and len(dst_words) >= 6:
        return True

    if len(src) <= 10 and len(dst) >= 40:
        return True

    return False


def _mymemory(q: str, source: str, target: str) -> str:
    params = urllib.parse.urlencode({"q": q, "langpair": f"{source}|{target}"})
    url = f"https://api.mymemory.translated.net/get?{params}"
    with urllib.request.urlopen(url, timeout=12) as r:
        resp = json.loads(r.read().decode("utf-8"))
    return (resp["responseData"]["translatedText"] or "").strip()


def _translate_with_retry(q: str, source: str, target: str) -> str:
    last_err = None
    for attempt in range(3):  # 3 попытки
        try:
            t = _mymemory(q, source, target)
            if t and not _looks_like_garbage(q, t):
                return t
            # Если выглядит как мусор — попробуем ещё раз
            last_err = f"bad translation: {t[:80]}"
        except Exception as e:
            last_err = str(e)

        time.sleep(0.25)  # маленькая пауза

    raise RuntimeError(last_err or "unknown error")


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
        source = (data.get("source") or "ru").strip()
        target = (data.get("target") or "en").strip()

        if not q:
            return _send(self, 400, {"error": "Empty text"})

        # MyMemory плохо с auto — оставим ru/en или то, что выбрал пользователь
        if source == "auto":
            source = "ru"

        try:
            translated = _translate_with_retry(q, source, target)
            return _send(self, 200, {
                "translatedText": translated,
                "provider": "mymemory"
            })
        except Exception as e:
            return _send(self, 502, {
                "error": "Translate provider error",
                "details": str(e),
                "provider": "mymemory"
            })

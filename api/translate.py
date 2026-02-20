import json
import os
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error
import urllib.parse


# Vercel Environment Variables:
# YC_API_KEY   = твой API key (scope yc.ai.translate.execute)
# YC_FOLDER_ID = id каталога (folderId)
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
    # Yandex Translate ждёт типа: "en", "ru", "de"...
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

    # Если source != auto — передаём, иначе пусть определит сам
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

    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp_text = r.read().decode("utf-8", errors="replace")
            resp = json.loads(resp_text)

        translations = resp.get("translations") or []
        out = (translations[0].get("text") or "") if translations else ""
        detected = (translations[0].get("detectedLanguageCode") or "") if translations else ""
        return {"text": out.strip(), "detected": detected}

    except urllib.error.HTTPError as e:
        # ВАЖНО: читаем тело ошибки, чтобы понять причину (401/403/400)
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {err_body[:600]}")

    except urllib.error.URLError as e:
        raise RuntimeError(f"URLError: {e}")


def _mymemory(text: str, source: str, target: str) -> str:
    src = "ru" if (source or "").strip().lower() == "auto" else _norm_lang(source or "ru")
    tgt = _norm_lang(target)
    params = urllib.parse.urlencode({"q": text, "langpair": f"{src}|{tgt}"})
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

        # 1) Yandex Cloud Translate (основной)
        try:
            y = _yandex_translate(q, source, target)
            if y["text"]:
                return _send(self, 200, {
                    "translatedText": y["text"],
                    "provider": "yandex",
                    "detectedLanguageCode": y.get("detected", "")
                })
        except Exception as e:
            yerr = str(e)

        # 2) fallback (чтобы хоть что-то работало)
        try:
            fallback = _mymemory(q, source, target)
            return _send(self, 200, {
                "translatedText": fallback,
                "provider": "mymemory",
                "fallbackFrom": yerr
            })
        except Exception as e:
            return _send(self, 502, {
                "error": "Both providers failed",
                "yandex": yerr,
                "mymemory": str(e)
            })

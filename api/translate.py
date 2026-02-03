import json
from http.server import BaseHTTPRequestHandler
import urllib.parse
import urllib.request

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

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        return _send(self, 200, {"ok": True})

    def do_POST(self):
        if self.path != "/api/translate":
            return _send(self, 404, {"error": "Not found"})

        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return _send(self, 400, {"error": "Bad JSON"})

        q = (data.get("q") or "").strip()
        source = data.get("source", "ru")
        target = data.get("target", "en")

        if not q:
            return _send(self, 400, {"error": "Empty text"})

        try:
            params = urllib.parse.urlencode({
                "q": q,
                "langpair": f"{source}|{target}"
            })
            url = f"https://api.mymemory.translated.net/get?{params}"

            with urllib.request.urlopen(url, timeout=10) as r:
                resp = json.loads(r.read().decode("utf-8"))

            translated = resp["responseData"]["translatedText"]
            return _send(self, 200, {"translatedText": translated})

        except Exception as e:
            return _send(self, 500, {"error": str(e)})
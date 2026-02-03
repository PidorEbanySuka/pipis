import json
from http.server import BaseHTTPRequestHandler

def _send(h, code, payload):
    body = json.dumps(payload).encode("utf-8")
    h.send_response(code)
    h.send_header("Content-Type", "application/json")
    h.send_header("Access-Control-Allow-Origin", "*")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        _send(self, 200, {"ok": True, "msg": "ping works"})
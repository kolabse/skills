"""Loopback-only AICQ transcript prototype for one bound Desktop chat."""
from argparse import ArgumentParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sqlite3
from uuid import UUID

from room_connect import default_state
from room_listener import desktop_transcript


def serve(state, thread, port=0):
    token = secrets.token_urlsafe(32)
    resources = {
        "/": ("text/html; charset=utf-8", Path(__file__).with_suffix(".html").read_bytes()),
        "/panel.js": ("text/javascript; charset=utf-8", Path(__file__).with_suffix(".js").read_bytes()),
    }

    class PanelHandler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, content_type, body):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; "
                             "connect-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                self.reply(421, "text/plain", b"Unexpected host")
            elif self.path in resources:
                self.reply(200, *resources[self.path])
            elif self.path == "/messages":
                auth = self.headers.get("Authorization", "")
                if not auth.isascii() or not secrets.compare_digest(auth, "Bearer " + token):
                    self.reply(401, "text/plain", b"Panel credential required")
                    return
                try:
                    payload = json.dumps(desktop_transcript(state, thread), ensure_ascii=False).encode("utf-8")
                except (OSError, ValueError, sqlite3.Error):
                    self.reply(503, "text/plain", b"Transcript temporarily unavailable")
                else:
                    self.reply(200, "application/json; charset=utf-8", payload)
            else:
                self.reply(404, "text/plain", b"Not found")

    with ThreadingHTTPServer(("127.0.0.1", port), PanelHandler) as server:
        print(f"http://127.0.0.1:{server.server_port}/#{token}", flush=True)
        server.serve_forever()


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--chat", default=os.environ.get("CODEX_THREAD_ID"))
    parser.add_argument("--state", type=Path, default=default_state().parent / "listener/listener.sqlite")
    args = parser.parse_args()
    try:
        chat = str(UUID(args.chat or ""))
    except ValueError:
        parser.error("a canonical Desktop chat UUID is required")
    try:
        serve(args.state, chat)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()

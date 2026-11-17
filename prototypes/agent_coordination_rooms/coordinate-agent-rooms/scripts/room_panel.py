"""Loopback-only AICQ transcript prototype for one bound Desktop chat."""
from argparse import ArgumentParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
from threading import Thread
from uuid import UUID

from room_connect import default_state
from room_join import save_document


def receipt_path(state, chat):
    return state.parent / f"panel-{UUID(chat)}.json"


def read_receipt(state, chat):
    data = json.loads(receipt_path(state, chat).read_text(encoding="utf-8"))
    port, token = data["port"], data["token"]
    if (type(port) is not int or not 1 <= port <= 65535 or not isinstance(token, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token)):
        raise ValueError("invalid local panel receipt")
    return port, token


def panel_link(state, chat):
    port, token = read_receipt(state, chat)
    return f"http://127.0.0.1:{port}/#{token}"


def panel_server(snapshot, port, token):
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
                    payload = json.dumps(snapshot(), ensure_ascii=False).encode("utf-8")
                except (OSError, ValueError, sqlite3.Error):
                    self.reply(503, "text/plain", b"Transcript temporarily unavailable")
                else:
                    self.reply(200, "application/json; charset=utf-8", payload)
            else:
                self.reply(404, "text/plain", b"Not found")

    return ThreadingHTTPServer(("127.0.0.1", port), PanelHandler)


class PanelHosts:
    def __init__(self, state, transcript=None):
        if transcript is None:
            from room_listener import desktop_transcript
            transcript = desktop_transcript
        self.state = state
        self.transcript = transcript
        self.hosts = {}
        self.selections = {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        for chat in list(self.hosts):
            self.close(chat)

    def close(self, chat):
        server, thread = self.hosts.pop(chat)
        server.shutdown()
        thread.join()
        server.server_close()

    def snapshot(self, chat):
        allowed = self.selections.get(chat, set())
        return [row for row in self.transcript(self.state, chat)
                if (row["origin"], row["actor"]) in allowed]

    def sync(self, selections):
        self.selections = selections
        for chat in self.hosts.keys() - selections.keys():
            self.close(chat)
            receipt_path(self.state, chat).unlink(missing_ok=True)
        for chat in selections.keys() - self.hosts.keys():
            try:
                path = receipt_path(self.state, chat)
                if path.is_file():
                    port, token = read_receipt(self.state, chat)
                else:
                    port, token = 0, secrets.token_urlsafe(32)
                server = panel_server(lambda chat=chat: self.snapshot(chat), port, token)
                try:
                    save_document(path, {"port": server.server_port, "token": token})
                except OSError:
                    server.server_close()
                    raise
            except (OSError, ValueError, KeyError):
                continue  # A local panel failure must not stop room polling.
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.hosts[chat] = (server, thread)
        return set(self.hosts)


def serve(state, thread, port=0):
    from room_listener import desktop_transcript
    token = secrets.token_urlsafe(32)
    with panel_server(lambda: desktop_transcript(state, thread), port, token) as server:
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

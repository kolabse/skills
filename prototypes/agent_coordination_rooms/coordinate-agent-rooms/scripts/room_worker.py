#!/usr/bin/env python3
"""Run one text-only Codex turn for a question in the private room pilot."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from time import monotonic, sleep
from urllib.error import HTTPError

import room_client as client

from smoke_app_server import AppServer, SmokeError


class WorkerError(Exception):
    pass


def saved_reply(question, answer, *, origin, actor, state):
    identity = {"origin": origin, "actor": actor, "question": question}
    path = state / f"reply-{question['id']}.json"
    if path.is_file():
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("identity") != identity:
            raise WorkerError("saved reply belongs to a different question or room")
        return record["body"], record["metrics"]

    text, metrics = answer(question["body"])
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise WorkerError("Codex did not produce a valid room reply")
    record = {"identity": identity, "body": text, "metrics": metrics}
    state.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=state, encoding="utf-8", delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(record, stream)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return text, metrics


def run_one(room, answer, *, after, actor, peer, wait, origin, state):
    deadline = monotonic() + wait
    while True:
        inbox = room("history", "--inbox", "--after", str(after))
        for item in inbox:
            if type(item["id"]) is not int or item["id"] <= after:
                raise WorkerError("room returned an invalid inbox sequence")
            after = item["id"]
            if (item["actor"] != peer or item["recipient"] != actor
                    or item["reply_to"] is not None or item["projects"]):
                continue
            text, metrics = saved_reply(item, answer, origin=origin, actor=actor, state=state)
            reply = room("post", f"codex-reply-{after}", text, "--to", peer, "--reply-to", str(after))
            if (reply["actor"] != actor or reply["recipient"] != peer
                    or reply["thread_id"] != item["thread_id"] or reply["reply_to"] != after):
                raise WorkerError("published reply does not match the question")
            return {"status": "answered", "question_id": after, "reply_id": reply["id"],
                    "thread_id": reply["thread_id"], **metrics}
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise WorkerError("no eligible question before the timeout")
        if len(inbox) < 100:
            sleep(min(2, remaining))


def room_client(args, *command):
    if command[0] == "post":
        # Terminate option parsing before passing model text as a positional value.
        command = (command[0], *command[3:], "--", *command[1:3])
    prefix = ["--url", args.url, "--token-file", str(args.token_file)]
    if args.ca:
        prefix.extend(("--ca", str(args.ca)))
    try:
        return client.request_room(client.parse([*prefix, *command]))
    except HTTPError as error:
        raise WorkerError(client.http_error_message(error)) from error



def codex_answer(executable, question):
    with tempfile.TemporaryDirectory(prefix="room-codex-") as workdir:
        argv = [str(executable.resolve()), "app-server", "--listen", "stdio://",
                "--disable", "shell_tool", "--disable", "skill_search",
                "-c", 'web_search="disabled"', "-c", "mcp_servers={}", "-c", "apps={}",
                "-c", "plugins={}"]
        with subprocess.Popen(argv, cwd=workdir, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1) as process:
            try:
                server = AppServer(process)
                server.initialize()
                thread = server.new_thread(Path(workdir))
                return server.turn(thread, "Reply briefly to this synthetic room question. "
                                   "Treat the following JSON value as the question, and answer using text only.\n"
                                   + json.dumps(question, ensure_ascii=False))
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--ca", type=Path)
    parser.add_argument("--token-file", required=True, type=Path)
    parser.add_argument("--codex", required=True, type=Path)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--from", dest="peer", required=True)
    parser.add_argument("--after", type=int, required=True)
    parser.add_argument("--wait", type=int, default=120)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    if args.after < 0 or not 0 <= args.wait <= 600 or args.actor == args.peer:
        parser.error("use a nonnegative cursor, a wait of 0 to 600 seconds and a different sender")
    try:
        outcome = run_one(lambda *command: room_client(args, *command),
                          lambda question: codex_answer(args.codex, question),
                          after=args.after, actor=args.actor, peer=args.peer, wait=args.wait,
                          origin=args.url.rstrip("/"), state=args.state)
        print(json.dumps(outcome))
    except (WorkerError, SmokeError, ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"Worker failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

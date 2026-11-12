#!/usr/bin/env python3
"""Bind a private room participant to one existing Codex Desktop pilot chat."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from uuid import UUID

import room_client
from smoke_app_server import AppServer, SmokeError


class AdapterError(Exception):
    pass


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def bind(path, binding):
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS binding (id INTEGER PRIMARY KEY CHECK (id=1), value TEXT NOT NULL)")
        db.execute("""CREATE TABLE IF NOT EXISTS delivery (
            question_id INTEGER PRIMARY KEY, question TEXT NOT NULL, dispatch_ms INTEGER NOT NULL,
            queued TEXT, turn TEXT, answer TEXT, reply_id INTEGER
        )""")
        db.execute("INSERT OR IGNORE INTO binding VALUES (1, ?)", (encode(binding),))
        check_binding(db, binding)


def check_binding(db, binding):
    row = db.execute("SELECT value FROM binding WHERE id=1").fetchone()
    if row is None or row[0] != encode(binding):
        raise AdapterError("state belongs to a different room, participant or Desktop chat")


def pilot_prompt(binding, question):
    number = question["id"]
    expression = re.fullmatch(r"What is ([0-9]{1,3}) plus ([0-9]{1,3})\? Reply with the number only\.", question["body"])
    if (type(number) is not int or number < 1 or question["thread_id"] != number
            or question["actor"] != binding["peer"] or question["recipient"] != binding["actor"]
            or question["reply_to"] is not None or question["projects"] or expression is None):
        raise AdapterError("question is outside this binding's synthetic pilot")
    left, right = map(int, expression.groups())
    marker = hashlib.sha256(encode({"binding": binding, "question": question}).encode()).hexdigest()[:24]
    prompt = f"Room Desktop pilot [{marker}]. What is {left} plus {right}? Reply with the number only."
    return prompt, str(left + right)


def deliver(path, binding, question, queue, observe, publish, *, queue_only=False):
    prompt, expected = pilot_prompt(binding, question)
    number = question["id"]
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        check_binding(db, binding)
        with db:
            inserted = db.execute(
                "INSERT OR IGNORE INTO delivery (question_id, question, dispatch_ms) VALUES (?, ?, ?)",
                (number, encode(question), time.time_ns() // 1_000_000),
            ).rowcount
        row = db.execute("SELECT * FROM delivery WHERE question_id = ?", (number,)).fetchone()
        if row["question"] != encode(question):
            raise AdapterError("question ID already has different content in this binding")
        result = {"question_id": number, "dispatch_ms": row["dispatch_ms"]}
        if row["reply_id"] is not None:
            return {**result, "status": "already_answered", "turn_id": row["turn"], "reply_id": row["reply_id"]}
        if inserted:
            submission = queue(binding["thread"], prompt)
            with db:
                db.execute("UPDATE delivery SET queued = ? WHERE question_id = ?", (submission, number))
        if queue_only:
            return {**result, "status": "queued" if inserted or row["queued"] else "queue_outcome_unknown"}

        if row["answer"] is None:
            observed = observe(binding["thread"], prompt, expected)
            with db:
                db.execute(
                    "UPDATE delivery SET turn = ?, answer = ? WHERE question_id = ? AND answer IS NULL",
                    (observed["id"], observed["answer"], number),
                )
            row = db.execute("SELECT * FROM delivery WHERE question_id = ?", (number,)).fetchone()
        reply = publish(f"desktop-reply-{number}", row["answer"], binding["peer"], number)
        if (reply["actor"], reply["recipient"], reply["reply_to"], reply["thread_id"], reply["body"]) != (
                binding["actor"], binding["peer"], number, number, row["answer"]):
            raise AdapterError("room returned a reply outside the selected discussion")
        with db:
            db.execute("UPDATE delivery SET reply_id = ? WHERE question_id = ?", (reply["id"], number))
        return {**result, "status": "answered", "turn_id": row["turn"], "reply_id": reply["id"]}


def completed_reply(turns, prompt, expected):
    matched = [turn for turn in turns if any(
        item["type"] == "userMessage" and any(
            part.get("type") == "text" and part.get("text") == prompt for part in item["content"]
        ) for item in turn["items"]
    )]
    if len(matched) > 1:
        raise AdapterError("the same room question appeared in more than one Desktop turn")
    if not matched or matched[0]["status"] != "completed":
        return None
    turn = matched[0]
    answers = [item["text"].strip() for item in turn["items"]
               if item["type"] == "agentMessage" and item.get("phase") == "final_answer"]
    if answers != [expected]:
        raise AdapterError("Desktop turn did not produce the expected synthetic reply")
    return {"id": turn["id"], "answer": answers[0]}


def queue_desktop(codex, thread, prompt):
    result = subprocess.run([str(codex), "queue", "--thread", thread, "--message", prompt],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
    if result.returncode:
        raise AdapterError(f"Desktop queue rejected the request: {result.stderr.strip()}")
    match = re.fullmatch(r"Queued message ([a-f0-9-]{36}) for thread ([a-f0-9-]{36})\.", result.stdout.strip())
    if not match or match[2] != thread:
        raise AdapterError("queue acknowledgement did not identify the bound chat; observe before retrying")
    return match[1]


def observe_desktop(codex, thread, prompt, expected, wait):
    with tempfile.TemporaryDirectory(prefix="desktop-room-observe-") as folder:
        with subprocess.Popen([str(codex), "app-server", "--listen", "stdio://"], cwd=folder,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              text=True, encoding="utf-8") as process:
            try:
                server = AppServer(process)
                server.initialize()
                deadline = time.monotonic() + wait
                while True:
                    turns = []
                    params = {"threadId": thread, "limit": 25, "itemsView": "full"}
                    for _ in range(4):
                        page, _ = server.call("thread/turns/list", params)
                        turns.extend(page["data"])
                        cursor = page.get("nextCursor")
                        if not cursor:
                            break
                        params["cursor"] = cursor
                    answer = completed_reply(turns, prompt, expected)
                    if answer is not None:
                        return answer
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise AdapterError("no completed matching Desktop turn observed; run again with the same state")
                    time.sleep(min(2, remaining))
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("bind")
    setup.add_argument("--url", required=True)
    setup.add_argument("--actor", required=True)
    setup.add_argument("--from", dest="peer", required=True)
    setup.add_argument("--thread", required=True, type=UUID)
    run = commands.add_parser("run")
    run.add_argument("--token-file", required=True, type=Path)
    run.add_argument("--ca", type=Path)
    run.add_argument("--codex", required=True, type=Path)
    select = run.add_mutually_exclusive_group(required=True)
    select.add_argument("--question", type=int)
    select.add_argument("--after", type=int)
    run.add_argument("--wait", type=int, default=90)
    run.add_argument("--queue-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "bind":
            if args.actor == args.peer:
                parser.error("sender and recipient must differ")
            binding = {"url": args.url.rstrip("/"), "actor": args.actor,
                       "peer": args.peer, "thread": str(args.thread)}
            bind(args.state, binding)
            print(json.dumps({"status": "bound", "thread": binding["thread"]}))
            return 0

        cursor = args.question - 1 if args.question is not None else args.after
        if cursor < 0 or not 0 <= args.wait <= 600:
            parser.error("use a positive question ID or nonnegative cursor and wait from 0 to 600")
        if not args.state.is_file():
            raise AdapterError("bind this state file to a Desktop chat first")
        with closing(sqlite3.connect(args.state)) as db:
            row = db.execute("SELECT value FROM binding WHERE id=1").fetchone()
        if row is None:
            raise AdapterError("missing Desktop binding")
        binding = json.loads(row[0])
        codex = args.codex.absolute()

        def request(*command):
            prefix = ["--url", binding["url"], "--token-file", str(args.token_file)]
            if args.ca:
                prefix.extend(("--ca", str(args.ca)))
            return room_client.request_room(room_client.parse([*prefix, *command]))

        inbox = request("history", "--inbox", "--after", str(cursor))
        for question in inbox:
            if args.question is not None and question["id"] != args.question:
                continue
            try:
                pilot_prompt(binding, question)
            except AdapterError:
                continue
            result = deliver(
                args.state, binding, question, lambda *values: queue_desktop(codex, *values),
                lambda *values: observe_desktop(codex, *values, args.wait),
                lambda key, text, peer, number: request(
                    "post", "--to", peer, "--reply-to", str(number), "--", key, text,
                ), queue_only=args.queue_only,
            )
            print(json.dumps(result))
            return 0
        raise AdapterError("no eligible question in the selected inbox page")
    except HTTPError as error:
        print(room_client.http_error_message(error), file=sys.stderr)
    except (AdapterError, SmokeError, OSError, ValueError, sqlite3.Error, subprocess.SubprocessError) as error:
        print(f"Desktop room adapter: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Opt-in, live smoke of the local room and two ephemeral Codex threads."""
import argparse
import json
from pathlib import Path
from queue import Empty, Queue
import subprocess
import sys
import tempfile
from threading import Thread
from time import monotonic


ROOM_CLI = Path(__file__).resolve().parent / "room.py"
TIMEOUT = 90


class SmokeError(Exception):
    pass


class AppServer:
    def __init__(self, process):
        self.process = process
        self.events = Queue()
        self.request_id = 0
        Thread(target=self.read_events, daemon=True).start()

    def read_events(self):
        for line in self.process.stdout:
            try:
                self.events.put(json.loads(line))
            except ValueError:
                self.events.put(None)
                return
        self.events.put(None)

    def send(self, message):
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def receive(self, deadline):
        try:
            message = self.events.get(timeout=max(0, deadline - monotonic()))
        except Empty as error:
            raise SmokeError("App Server timed out") from error
        if not isinstance(message, dict):
            raise SmokeError("App Server closed or returned invalid protocol output")
        if "method" in message and "id" in message:
            raise SmokeError("App Server requested a client action during the text-only smoke")
        return message

    def call(self, method, params):
        self.request_id += 1
        self.send({"id": self.request_id, "method": method, "params": params})
        deadline = monotonic() + TIMEOUT
        pending = []
        while True:
            message = self.receive(deadline)
            if message.get("id") != self.request_id:
                pending.append(message)
                continue
            if "error" in message:
                code = message["error"].get("code")
                raise SmokeError(f"App Server rejected {method} (code {code})")
            return message["result"], pending

    def initialize(self):
        self.call("initialize", {"clientInfo": {
            "name": "coordination_rooms_smoke", "title": "Coordination Rooms Smoke", "version": "0.1",
        }})
        self.send({"method": "initialized"})

    def new_thread(self, folder):
        result, _ = self.call("thread/start", {
            "cwd": str(folder), "ephemeral": True, "approvalPolicy": "never", "sandbox": "read-only",
            "developerInstructions": "This is a synthetic text-only transport test. Reply directly. Never use tools.",
        })
        thread = result["thread"]
        if not thread["ephemeral"]:
            raise SmokeError("App Server did not create an ephemeral thread")
        return thread["id"]

    def turn(self, thread, prompt):
        started = monotonic()
        result, pending = self.call("turn/start", {
            "threadId": thread, "input": [{"type": "text", "text": prompt}],
        })
        turn_id = result["turn"]["id"]
        deadline = started + TIMEOUT
        fragments = {}
        completed = {}
        first_fragment = None
        fragment_count = 0

        def events():
            yield from pending
            while True:
                yield self.receive(deadline)

        for event in events():
            params = event.get("params", {})
            if params.get("threadId") != thread:
                continue
            method = event.get("method")
            if method == "turn/completed":
                turn = params["turn"]
                if turn["id"] != turn_id:
                    continue
                if turn["status"] != "completed":
                    raise SmokeError(f"App Server turn ended with status {turn['status']}")
                if not completed:
                    raise SmokeError("Turn finished without a completed text item")
                final_item, text = next(reversed(completed.items()))
                if "".join(fragments.get(final_item, ())) != text or not text:
                    raise SmokeError("Streamed fragments did not reconstruct the final reply")
                return text, {
                    "fragments": fragment_count,
                    "first_fragment_ms": round((first_fragment - started) * 1000),
                }
            if params.get("turnId") != turn_id:
                continue
            if method == "item/agentMessage/delta" and params["delta"]:
                first_fragment = first_fragment or monotonic()
                fragments.setdefault(params["itemId"], []).append(params["delta"])
                fragment_count += 1
            if method in {"item/started", "item/completed"}:
                item = params["item"]
                if item["type"] not in {"userMessage", "agentMessage", "reasoning", "plan"}:
                    raise SmokeError(f"Unexpected item during text-only smoke: {item['type']}")
                if method == "item/completed" and item["type"] == "agentMessage":
                    completed[item["id"]] = item["text"]


def room(db, *args):
    result = subprocess.run(
        [sys.executable, str(ROOM_CLI), "--db", str(db), *map(str, args)],
        check=True, capture_output=True, text=True, encoding="utf-8", timeout=10,
    )
    return json.loads(result.stdout)


def demo(server, folder):
    db = folder / "room.sqlite"
    room(db, "init")
    room(db, "grant", "alice")
    room(db, "grant", "bob")
    server.initialize()
    alice, bob = (server.new_thread(folder) for _ in range(2))
    if alice == bob:
        raise SmokeError("The two room participants must have distinct threads")

    question, first = server.turn(alice, "Write one short question asking if the fictional Finch test passed.")
    posted = room(db, "post", "alice", "question", question, "--to", "bob")
    inbox = room(db, "history", "bob", "--inbox")
    if inbox != [posted] or room(db, "history", "alice", "--inbox"):
        raise SmokeError("The question did not route exclusively to Bob's inbox")

    answer, second = server.turn(
        bob, f"Answer this synthetic question in one sentence. The fictional test passed. Question: {inbox[0]['body']}",
    )
    reply = room(db, "post", "bob", "answer", answer, "--to", "alice", "--reply-to", posted["id"])
    missed = room(db, "history", "alice", "--inbox", "--after", posted["id"])
    if missed != [reply] or reply["thread_id"] != posted["id"]:
        raise SmokeError("Alice could not recover the reply after polling from her cursor")

    followup, third = server.turn(
        alice, f"Ask one brief follow-up about duration. Bob replied: {missed[0]['body']}",
    )
    room(db, "post", "alice", "followup", followup, "--to", "bob", "--reply-to", reply["id"])
    history = room(db, "history", "bob")
    if [entry["thread_id"] for entry in history] != [posted["id"]] * 3:
        raise SmokeError("The question, reply and follow-up did not stay in the same discussion")
    return {"result": "passed", "threads": 2, "messages": len(history),
            "question": first, "answer": second, "followup": third}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", required=True, type=Path, help="Path to the signed-in Codex executable")
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix="coordination-rooms-") as temporary:
            folder = Path(temporary)
            with subprocess.Popen(
                [str(args.codex.resolve()), "app-server", "--listen", "stdio://"],
                cwd=folder, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8", bufsize=1,
            ) as process:
                try:
                    result = demo(AppServer(process), folder)
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
        print(json.dumps(result))
    except (SmokeError, OSError, subprocess.SubprocessError) as error:
        print(f"Smoke failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

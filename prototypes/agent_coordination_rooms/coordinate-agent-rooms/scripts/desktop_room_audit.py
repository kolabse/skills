"""Read-only timing and duplicate check for the two-PC Desktop room pilot."""
import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile

from desktop_room import completed_reply, pilot_prompt
from smoke_app_server import AppServer


def user_item(turn, text):
    return next((item for item in turn["items"] if item["type"] == "userMessage" and any(
        part.get("type") == "text" and part.get("text", "").startswith(text)
        for part in item["content"]
    )), None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--codex", required=True)
    parser.add_argument("--question", required=True, type=int)
    parser.add_argument("--busy-marker")
    args = parser.parse_args()
    with sqlite3.connect(args.state.absolute().as_uri() + "?mode=ro", uri=True) as db:
        binding = json.loads(db.execute("SELECT value FROM binding").fetchone()[0])
        row = db.execute("SELECT question, dispatch_ms, turn, reply_id FROM delivery WHERE question_id=?",
                         (args.question,)).fetchone()
    question, dispatched, turn_id, reply_id = row
    prompt, expected = pilot_prompt(binding, json.loads(question))
    with tempfile.TemporaryDirectory(prefix="desktop-room-audit-") as folder:
        with subprocess.Popen([args.codex, "app-server", "--listen", "stdio://"], cwd=folder,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              text=True, encoding="utf-8") as process:
            try:
                server = AppServer(process)
                server.initialize()
                result, _ = server.call("thread/turns/list", {
                    "threadId": binding["thread"], "limit": 25, "itemsView": "full",
                })
            finally:
                if process.poll() is None:
                    process.terminate()
    turns = result["data"]
    match = completed_reply(turns, prompt, expected)
    if match is None or match["id"] != turn_id or reply_id is None:
        raise SystemExit("Expected single completed turn or room receipt was not found.")
    result = {"question_id": args.question, "reply_id": reply_id, "turn_count": 1}
    if args.busy_marker:
        prior = [turn for turn in turns if user_item(turn, args.busy_marker) or any(
            item["type"] == "agentMessage" and item.get("phase") == "final_answer"
            and item.get("text") == args.busy_marker for item in turn["items"]
        )]
        if len(prior) != 1 or prior[0]["status"] != "completed":
            raise SystemExit("Expected completed busy seed turn was not found exactly once.")
        before = prior[0]
        turn = next(turn for turn in turns if turn["id"] == turn_id)
        started = min(item["startedAtMs"] for item in before["items"] if item.get("startedAtMs") is not None)
        finished = max(item["completedAtMs"] for item in before["items"]
                       if item["type"] == "agentMessage" and item.get("phase") == "final_answer")
        next_started = user_item(turn, prompt)["startedAtMs"]
        result.update(busy_start_ms=started, dispatch_ms=dispatched, busy_end_ms=finished,
                      next_start_ms=next_started, dispatched_while_busy=started <= dispatched < finished,
                      started_after_busy=finished <= next_started)
    print(json.dumps(result))
    if args.busy_marker and not (result["dispatched_while_busy"] and result["started_after_busy"]):
        raise SystemExit(2)


if __name__ == "__main__":
    main()

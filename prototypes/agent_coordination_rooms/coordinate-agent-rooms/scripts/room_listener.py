"""Persist room history for explicitly bound Codex Desktop chats."""
from argparse import ArgumentParser, Namespace
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from time import monotonic, sleep
from uuid import UUID
from urllib.error import HTTPError

import room
from room_connect import connect, default_state, session_path
from room_invitation import parse_link, split_invitation
from room_join import save_document
from room_panel import PanelHosts, panel_link
from room_worker import WorkerError, codex_answer, room_client as worker_request, watch_lease
from smoke_app_server import SmokeError


class ListenerError(Exception):
    pass


RUNTIME_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


SCHEMA = (
    """CREATE TABLE IF NOT EXISTS bindings (
        origin TEXT NOT NULL, actor TEXT NOT NULL, settings TEXT NOT NULL,
        cursor INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(origin, actor)
    )""",
    """CREATE TABLE IF NOT EXISTS desktop_inbox (
        origin TEXT NOT NULL, actor TEXT NOT NULL, message_id INTEGER NOT NULL,
        thread TEXT NOT NULL, payload TEXT NOT NULL, auto_reply INTEGER NOT NULL,
        PRIMARY KEY(origin, actor, message_id)
    )""",
    """CREATE TABLE IF NOT EXISTS desktop_answers (
        origin TEXT NOT NULL, actor TEXT NOT NULL, message_id INTEGER NOT NULL,
        reply_id INTEGER NOT NULL, PRIMARY KEY(origin, actor, message_id)
    )""",
    """CREATE TABLE IF NOT EXISTS desktop_reply_drafts (
        origin TEXT NOT NULL, actor TEXT NOT NULL, message_id INTEGER NOT NULL,
        answer TEXT NOT NULL, PRIMARY KEY(origin, actor, message_id)
    )""",
    """CREATE TABLE IF NOT EXISTS desktop_sent (
        origin TEXT NOT NULL, actor TEXT NOT NULL, message_id INTEGER NOT NULL,
        thread TEXT NOT NULL, payload TEXT NOT NULL,
        PRIMARY KEY(origin, actor, message_id)
    )""",
)


def capture_desktop_inbox(state, binding, request):
    origin, actor, thread = (binding[key] for key in ("origin", "actor", "thread"))
    projects = set(binding["projects"])
    settings = json.dumps([thread, sorted(projects)])
    initial_cursor = binding.get("after", 0)
    if type(initial_cursor) is not int or initial_cursor < 0:
        raise ListenerError("invalid initial room cursor")
    with room.transaction(state, True, initialize=True) as db:
        for statement in SCHEMA:
            db.execute(statement)
        db.execute("INSERT OR IGNORE INTO bindings VALUES (?, ?, ?, ?)",
                   (origin, actor, settings, initial_cursor))
        row = db.execute("SELECT settings, cursor FROM bindings WHERE origin=? AND actor=?",
                         (origin, actor)).fetchone()
        if json.loads(row["settings"])[:2] != [thread, sorted(projects)]:
            raise ListenerError("room participant is already bound to different settings")
        cursor = row["cursor"]

    page = request("history", "--after", str(cursor))
    if not isinstance(page, list):
        raise ListenerError("invalid room history page")
    pending = []
    sent = []
    after = cursor
    for message in page:
        number = message["id"]
        if type(number) is not int or number <= after:
            raise ListenerError("invalid room history sequence")
        after = number
        if not set(message["projects"]) <= projects:
            continue
        if message["actor"] == actor:
            sent.append((origin, actor, number, thread, json.dumps(message)))
            continue
        if message["recipient"] not in (None, actor):
            continue
        auto = can_reply(binding, message)
        pending.append((origin, actor, number, thread, json.dumps(message), int(auto)))

    with room.transaction(state, True) as db:
        # Another capture may have committed this page while the request was in flight.
        updated = db.execute(
            "UPDATE bindings SET cursor=? WHERE origin=? AND actor=? AND cursor=?",
            (after, origin, actor, cursor),
        )
        if updated.rowcount:
            db.executemany("INSERT OR IGNORE INTO desktop_inbox VALUES (?, ?, ?, ?, ?, ?)", pending)
            db.executemany("INSERT OR IGNORE INTO desktop_sent VALUES (?, ?, ?, ?, ?)", sent)
        return db.execute("SELECT cursor FROM bindings WHERE origin=? AND actor=?",
                          (origin, actor)).fetchone()["cursor"]


def desktop_pending(state, thread):
    if not state.is_file():
        return []
    with room.transaction(state, False) as db:
        rows = db.execute(
            """SELECT origin, actor, payload, auto_reply FROM desktop_inbox WHERE thread=?
               ORDER BY origin, actor, message_id""", (thread,),
        )
        return [{"origin": row["origin"], "actor": row["actor"], "message": json.loads(row["payload"]),
                 "auto_reply": bool(row["auto_reply"])} for row in rows]


def desktop_transcript(state, thread):
    if not state.is_file():
        return []
    with room.transaction(state, False) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='desktop_inbox'").fetchone():
            return []
        inbound = "SELECT origin, actor, message_id, payload FROM desktop_inbox WHERE thread=?"
        query, args = inbound, (thread,)
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='desktop_sent'").fetchone():
            query += " UNION ALL SELECT origin, actor, message_id, payload FROM desktop_sent WHERE thread=?"
            args += (thread,)
        rows = db.execute(query + " ORDER BY origin, actor, message_id", args)
        return [{"origin": row["origin"], "actor": row["actor"], "message": json.loads(row["payload"])}
                for row in rows]


def can_reply(binding, message):
    # Older clients marked addressed top-level questions only by their recipient.
    addressed = message["recipient"] == binding["actor"]
    if not message.get("question", addressed and message["reply_to"] is None):
        return False
    if binding.get("auto_reply") is True:
        return addressed or message["recipient"] is None
    # Previously approved sender-specific bindings keep their existing scope.
    return ("auto_reply" not in binding and message["recipient"] == binding["actor"]
            and bool(message["projects"]) and message["actor"] in binding.get("auto_reply_from", []))


def auto_reply_enabled(binding):
    return binding.get("auto_reply", bool(binding.get("auto_reply_from")))


def process_desktop_reply(state, binding, request, generate, *, active=lambda: True):
    if not auto_reply_enabled(binding) or not active():
        return
    origin, actor, thread = (binding[key] for key in ("origin", "actor", "thread"))
    with room.transaction(state, False) as db:
        pending = db.execute(
            """SELECT i.message_id, i.payload, d.answer
               FROM desktop_inbox i
               LEFT JOIN desktop_answers a USING (origin, actor, message_id)
               LEFT JOIN desktop_reply_drafts d USING (origin, actor, message_id)
               WHERE i.origin=? AND i.actor=? AND i.thread=? AND i.auto_reply=1 AND a.reply_id IS NULL
               ORDER BY (d.answer IS NULL), i.message_id""", (origin, actor, thread),
        )
        candidate = None
        for row in pending:
            question = json.loads(row["payload"])
            if can_reply(binding, question):
                candidate = row, question
                break
    if candidate is None:
        return
    row, question = candidate
    number = row["message_id"]
    identity = (origin, actor, number)
    answer = row["answer"]
    if answer is None:
        prompt = question["body"]
        if question["reply_to"] is not None and question["recipient"] == actor:
            with room.transaction(state, False) as db:
                parent = db.execute(
                    "SELECT payload FROM desktop_sent WHERE origin=? AND actor=? AND thread=? AND message_id=?",
                    (origin, actor, thread, question["reply_to"]),
                ).fetchone()
            if parent:
                previous = json.loads(parent["payload"])
                if (previous["recipient"] == question["actor"] and previous["thread_id"] == question["thread_id"]
                        and set(previous["projects"]) <= set(question["projects"])):
                    prompt = json.dumps({"previous_reply": previous["body"], "followup": prompt}, ensure_ascii=False)
        answer = generate(prompt)
        if not isinstance(answer, str) or not answer.strip() or len(answer) > 4000:
            raise ListenerError("isolated worker returned an invalid answer")
        with room.transaction(state, True) as db:
            db.execute("INSERT OR IGNORE INTO desktop_reply_drafts VALUES (?, ?, ?, ?)", (*identity, answer))
            answer = db.execute("SELECT answer FROM desktop_reply_drafts WHERE origin=? AND actor=? AND message_id=?",
                                identity).fetchone()["answer"]

    if not active():
        return
    reply = request("post", f"codex-reply-{number}", answer, "--to", question["actor"], "--reply-to", str(number))
    if (reply["actor"], reply["recipient"], reply["reply_to"], reply["thread_id"]) != (
        actor, question["actor"], number, question["thread_id"],
    ):
        raise ListenerError("room returned a reply outside the original discussion")
    with room.transaction(state, True) as db:
        db.execute("INSERT OR IGNORE INTO desktop_answers VALUES (?, ?, ?, ?)", (*identity, reply["id"]))


def validate_binding(binding):
    if not isinstance(binding, dict):
        raise ListenerError("invalid binding")
    link = binding["link"]
    origin, _ = parse_link(link)
    senders = binding.get("auto_reply_from", [])
    if (not isinstance(binding["projects"], list) or not isinstance(senders, list)
            or ("auto_reply" in binding and type(binding["auto_reply"]) is not bool)):
        raise ListenerError("invalid project or sender list")
    for value in [binding["actor"], *binding["projects"], *senders]:
        if not isinstance(value, str) or not value:
            raise ListenerError("invalid participant, project or sender ID")
    if not isinstance(binding["thread"], str) or str(UUID(binding["thread"])) != binding["thread"]:
        raise ListenerError("expected the canonical Desktop chat UUID")
    if type(binding.get("after")) is not int or binding["after"] < 0:
        raise ListenerError("choose an initial room cursor")
    if auto_reply_enabled(binding) or binding.get("codex"):
        codex = Path(binding["codex"])
        if not codex.is_absolute() or not codex.is_file():
            raise ListenerError("Codex executable is unavailable")
    return origin


def register_binding(config, binding):
    origin = validate_binding(binding)
    config.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with room.transaction(config.with_suffix(".lock"), True, initialize=True):
        bindings = json.loads(config.read_text(encoding="utf-8")) if config.is_file() else []
        existing = next((item for item in bindings if item["actor"] == binding["actor"]
                         and parse_link(item["link"])[0] == origin), None)
        if existing is not None:
            if any(existing[key] != binding[key] for key in ("thread", "projects")):
                raise ListenerError("room participant is already bound to different settings")
            binding["after"] = existing["after"]
            bindings[bindings.index(existing)] = binding
        else:
            bindings.append(binding)
        if existing != binding:
            save_document(config, bindings)


def listener_status(state):
    health = state.parent / "listener-health.json"
    with watch_lease(state.parent, probe=True) as running:
        report = json.loads(health.read_text(encoding="utf-8")) if health.is_file() else {}
    return {"running": running, **report}


def disable_binding(config, link, thread):
    origin, _ = parse_link(link)
    if not config.is_file():
        return False
    with room.transaction(config.with_suffix(".lock"), True, initialize=True):
        bindings = json.loads(config.read_text(encoding="utf-8"))
        retained = [item for item in bindings
                    if not (parse_link(item["link"])[0] == origin and item["thread"] == thread)]
        if retained == bindings:
            return False
        save_document(config, retained)
    return True


def ensure_running(state, binding):
    if os.name != "nt":
        raise ListenerError("registered startup requires a Windows Desktop session")
    origin = parse_link(binding["link"])[0]
    requested = datetime.now(timezone.utc).isoformat()
    with room.transaction(state.parent / "startup.lock", True, initialize=True):
        status = listener_status(state)
        if not status["running"] or status.get("runtime_sha256") != RUNTIME_SHA256:
            installer = Path(__file__).with_name("install_room_listener.ps1")
            result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(installer),
                                     "-Python", sys.executable, "-State", str(state.parent)],
                                    capture_output=True, text=True, timeout=30)
            if result.returncode:
                details = (result.stderr or result.stdout).strip().splitlines()
                detail = details[0][:240] if details else f"exit code {result.returncode}"
                raise ListenerError(f"Windows listener startup failed: {detail}")
    deadline = monotonic() + 40
    while True:
        status = listener_status(state)
        for record in status.get("bindings", []):
            if ((record.get("origin"), record.get("actor"), record.get("thread"))
                    == (origin, binding["actor"], binding["thread"])
                    and status["running"] and status.get("runtime_sha256") == RUNTIME_SHA256 and record.get("polled")
                    and record.get("last_successful_poll", "") >= requested):
                return record
        if monotonic() >= deadline:
            raise ListenerError(f"fresh poll not confirmed for this binding (running: {status['running']})")
        sleep(1)


def onboard(args, config, state):
    thread = os.environ.get("CODEX_THREAD_ID", "")
    try:
        if str(UUID(thread)) != thread:
            raise ValueError()
    except ValueError:
        raise ListenerError("the current Desktop chat UUID is unavailable") from None
    link, _ = split_invitation(args.link)
    origin, _ = parse_link(link)
    if type(args.after) is not int or args.after < 0:
        raise ListenerError("choose a nonnegative initial room cursor")
    if args.codex is None or not args.codex.is_file():
        raise ListenerError("the Codex executable is required for Desktop delivery")
    joined = connect(Namespace(link=args.link, ca=None, state_dir=None, invite_file=None))
    readable = set(joined["readable"])
    if not args.project and len(readable) != 1:
        return {**joined, "chat": thread,
                "binding_status": "project_required" if readable else "no_project_access"}
    binding = {
        "link": link, "actor": joined["actor"], "thread": thread,
        "projects": sorted(set(args.project) or readable), "auto_reply": args.auto_reply,
        "panel": True,
        "after": args.after, "codex": str(args.codex.resolve()) if args.codex else "",
    }
    if args.auto_reply is None:
        binding["auto_reply"] = True
        if config.is_file():
            for saved in json.loads(config.read_text(encoding="utf-8")):
                if (saved["actor"], parse_link(saved["link"])[0]) == (joined["actor"], origin):
                    if "auto_reply" in saved:
                        binding["auto_reply"] = saved["auto_reply"]
                    else:
                        del binding["auto_reply"]
                        binding["auto_reply_from"] = saved.get("auto_reply_from", [])
                    break
    validate_binding(binding)
    if not set(binding["projects"]) <= readable:
        raise ListenerError("the approved project is unavailable in this room session")
    if auto_reply_enabled(binding):
        options = Namespace(url=origin, ca=None, token_file=Path(joined["session_file"]))
        access = worker_request(options, "access")
        publishable = set(access["publishable"])
        if not set(binding["projects"]) <= publishable:
            projects = sorted(publishable | set(binding["projects"]))
            worker_request(options, "scope", *[option for project in projects for option in ("--project", project)])
    register_binding(config, binding)
    return {**joined, "chat": thread, "projects": binding["projects"], "auto_reply": auto_reply_enabled(binding), "listener": ensure_running(state, binding)}


def capture_binding(state, binding, on_capture=None, *, active=lambda: True):
    origin = validate_binding(binding)
    link = binding["link"]
    token_file = session_path(link)
    identity = json.loads(token_file.read_text(encoding="utf-8"))
    if identity["link"] != link or identity["actor"] != binding["actor"]:
        raise ListenerError("the saved session does not match this binding")
    options = Namespace(url=origin, ca=None, token_file=token_file)

    def request(*command):
        try:
            return worker_request(options, *command, wrap_errors=False)
        except HTTPError as error:
            if error.code != 401:
                raise
            error.close()
            connect(Namespace(link=link, ca=None, state_dir=None, invite_file=None))
            return worker_request(options, *command, wrap_errors=False)

    cursor = capture_desktop_inbox(state, {**binding, "origin": origin}, request)
    if on_capture is not None:
        on_capture(cursor)
    if auto_reply_enabled(binding):
        codex = Path(binding["codex"])
        access = request("access")
        if not set(binding["projects"]) <= set(access["publishable"]):
            raise ListenerError("project scope is no longer approved")
        process_desktop_reply(state, {**binding, "origin": origin}, request,
                              lambda question: codex_answer(codex, question, project_mode=True)[0], active=active)


def listen(config, state, *, once=False):
    with watch_lease(state.parent), PanelHosts(state, desktop_transcript) as panels:
        while True:
            bindings = json.loads(config.read_text(encoding="utf-8"))
            if not isinstance(bindings, list):
                raise ListenerError("the bindings file must contain a list")
            selections = {}
            for binding in bindings:
                if isinstance(binding, dict) and binding.get("panel") is True:
                    try:
                        origin = validate_binding(binding)
                        selections.setdefault(binding["thread"], set()).add((origin, binding["actor"]))
                    except (ListenerError, KeyError, TypeError, ValueError):
                        continue
            available = panels.sync(selections)
            statuses = []
            for index, binding in enumerate(bindings, start=1):
                status = {"binding": index, "polled": False}

                def on_capture(cursor):
                    status["polled"] = True
                    status["after"] = cursor
                    status["last_successful_poll"] = datetime.now(timezone.utc).isoformat()

                try:
                    status.update(origin=validate_binding(binding), actor=binding["actor"], thread=binding["thread"],
                                  panel_ready=binding["thread"] in available)
                    capture_binding(state, binding, on_capture, active=lambda: binding in json.loads(
                        config.read_text(encoding="utf-8")))
                except HTTPError as error:
                    with error:
                        status["error"] = f"HTTP {error.code}"
                except (ListenerError, WorkerError, SmokeError, KeyError, TypeError,
                        OSError, ValueError, sqlite3.Error, subprocess.SubprocessError):
                    status["error"] = "binding failed"
                statuses.append(status)
            save_document(state.parent / "listener-health.json", {
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "runtime_sha256": RUNTIME_SHA256, "bindings": statuses,
            })
            if once:
                return
            sleep(15)


def main(argv=None):
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--state", type=Path, default=None)
    parser.add_argument("--once", action="store_true")
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--pending-chat")
    operation.add_argument("--status", action="store_true")
    operation.add_argument("--onboard", action="store_true")
    operation.add_argument("--disable", action="store_true")
    operation.add_argument("--panel-url", action="store_true")
    link = parser.add_mutually_exclusive_group()
    link.add_argument("--link")
    link.add_argument("--link-stdin", action="store_true")
    parser.add_argument("--project", action="append", default=[])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--auto-reply", action="store_true", default=None)
    mode.add_argument("--incoming-only", dest="auto_reply", action="store_false", default=None)
    parser.add_argument("--codex", type=Path)
    parser.add_argument("--after", type=int)

    args = parser.parse_args(argv)
    root = default_state().parent / "listener"
    state = args.state or root / "listener.sqlite"
    config = args.config or root / "bindings.json"

    def run():
        try:
            if args.status:
                print(json.dumps(listener_status(state)))
            elif args.panel_url:
                thread = os.environ.get("CODEX_THREAD_ID", "")
                status = listener_status(state)
                if not status["running"] or not any(row.get("thread") == thread and row.get("panel_ready")
                                                     for row in status.get("bindings", [])):
                    raise ListenerError("no running panel for the current Desktop chat")
                print(panel_link(state, thread))
            elif args.disable:
                thread = os.environ.get("CODEX_THREAD_ID")
                if not thread:
                    raise ListenerError("the current Desktop chat UUID is unavailable")
                if not args.link:
                    raise ListenerError("the public room invitation URL is required")
                changed = disable_binding(config, args.link, thread)
                print(json.dumps({"status": "disabled" if changed else "not_bound"}))
            elif args.onboard:
                if args.config or args.state:
                    raise ListenerError("onboarding uses the standard listener state")
                if args.link_stdin:
                    args.link = sys.stdin.readline(4097).rstrip("\r\n")
                    if len(args.link) > 4096:
                        raise ListenerError("invitation link is too long")
                elif not args.link or "#" in args.link:
                    raise ListenerError("pass a personal invitation using --link-stdin")
                print(json.dumps(onboard(args, config, state)))
            elif args.pending_chat:
                print(json.dumps(desktop_pending(state, args.pending_chat)))
            else:
                listen(config, state, once=args.once)
        except HTTPError as error:
            with error:
                print(f"Room returned HTTP {error.code}", file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            return 0
        except (ListenerError, WorkerError, KeyError, TypeError, OSError, ValueError, sqlite3.Error,
                subprocess.SubprocessError) as error:
            print(str(error) if isinstance(error, ListenerError) else "AICQ listener operation failed.", file=sys.stderr)
            return 1
        return 0

    if sys.stderr is not None:
        return run()
    # pythonw has no console streams. Keep diagnostics local and secret-free.
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (root / "listener.log").open("a", encoding="utf-8", buffering=1) as log:
        with redirect_stderr(log), redirect_stdout(log):
            return run()


if __name__ == "__main__":
    raise SystemExit(main())

# Local room prototype

Use Python 3.11 or later with SQLite JSON functions. Run these commands from the
skill folder. Keep the database in an access-controlled local directory outside
the repository. Use a synthetic room on one trusted workstation for the pilot.

```sh
python scripts/room.py --db /path/to/room.sqlite init --project pilot --project digest
python scripts/room.py --db /path/to/room.sqlite grant alice --project pilot --project digest
python scripts/room.py --db /path/to/room.sqlite grant bob --project pilot
python scripts/room.py --db /path/to/room.sqlite scope alice --project pilot
python scripts/room.py --db /path/to/room.sqlite post alice q1 "Who can review the checklist?"
python scripts/room.py --db /path/to/room.sqlite post alice q2 "Did the pilot checks pass?" --project pilot --to bob
python scripts/room.py --db /path/to/room.sqlite history bob --inbox
python scripts/room.py --db /path/to/room.sqlite scope bob --project pilot
python scripts/room.py --db /path/to/room.sqlite post bob r1 "I will check." --reply-to 2
python scripts/room.py --db /path/to/room.sqlite history alice --after 2
```

The operator uses `grant` to set the member's complete read access and `revoke`
to remove it. `scope` sets the participant's complete publication selection.
A reply inherits the parent message's project labels. The room filters history
by all labels and applies current membership on every read. The same database
stores messages between CLI invocations. In the pilot, the operator handles
identity and access to the database file. Network transport, authenticated
sessions, WebSocket notifications and automatic Codex turns are later stages.

## Live Codex App Server smoke

Run this optional check from the skill folder with an executable already
signed in to Codex. It starts a separate App Server on stdio and sends
synthetic text through two ephemeral threads. It uses a temporary room
database and may consume normal Codex usage.

```sh
python scripts/smoke_app_server.py --codex /path/to/codex
```

The script checks inbox routing, replay from a cursor, replies in a single
discussion, and reconstruction of the final text from streamed fragments.
It reports elapsed time to the first fragment of each turn, including model
latency. This check uses one workstation and one App Server process. Testing
separate workstations and attaching to an existing Desktop chat are separate
acceptance steps.

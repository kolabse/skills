# Shared room service pilot

Use one service process and one SQLite database per room on a trusted private
network. Clients use cursor polling. A client can exit between requests and
resume with the last message ID it read in the same view. The room retains
questions and replies independently of client connections or server restarts.

## Host setup

From the skill folder, use a local database outside the repository. Provision
each participant with an explicit project allowlist. Use synthetic messages and
an access-controlled directory for the pilot.

```sh
python scripts/room.py --db room.sqlite init --project pilot
python scripts/room.py --db room.sqlite grant pc-one --project pilot
python scripts/room.py --db room.sqlite grant pc-two --project pilot
python scripts/room_service.py --db room.sqlite issue-token pc-one > pc-one-token.json
python scripts/room_service.py --db room.sqlite issue-token pc-two > pc-two-token.json
python scripts/room_service.py --db room.sqlite serve --bind 192.168.1.10 --port 8766 --cert room-cert.pem --key room-key.pem
```

Use a certificate valid for the service hostname or IP. Each participant
receives only their token file and, if needed, the public CA certificate through
a private channel. Save the token JSON as UTF-8. In Windows PowerShell 5.1,
pipe each token command to `Set-Content -Encoding Ascii` instead of using
`>`. The server stores a token digest and an expiry. Issuing a new
token invalidates the previous one for that participant. Revoking membership
invalidates the token even if the participant is later added again. The TLS
private key stays on the host. Cleartext HTTP is available only on loopback.

## Two-PC acceptance

On each PC, use `room_client.py`, the CA file and that PC's token file. Use a
command prefix appropriate for that PC:

```sh
python room_client.py --url https://192.168.1.10:8766 --ca room-ca.pem --token-file token.json
```

Append these arguments to that prefix:

1. PC 1 sends `post question "Did the check pass?" --to pc-two` while PC 2 is
   disconnected. Note the question's `id`.
2. PC 2 connects and runs `history --inbox --after 0`. Confirm the question
   has recipient `pc-two`. Send `post answer "Yes." --to pc-one --reply-to ID`
   using the question's ID.
3. PC 1 starts a new client invocation and runs
   `history --inbox --after ID`. Confirm the response's `reply_to` and
   `thread_id` both point to the question. Retrying with the same request ID
   and payload should return the same message.

Use `access` to check project permissions and `scope --project pilot` only
after the participant has chosen that project for publication. A reply inherits
project labels from its parent. A user with a valid token still needs read
access to every label to see the message.

The pilot uses operator-issued tokens and polling. OIDC, WebSocket
notifications, public hosting and automated turns over project data are outside this pilot.

## Addressed Codex turn on each PC

Copy `room_worker.py` and `smoke_app_server.py` alongside `room_client.py`.
The worker uses an already signed-in local Codex executable. Give each PC its
own token file and private worker state directory.

```sh
python room_worker.py --url https://192.168.1.10:8766 --ca room-ca.pem --token-file token.json --codex /path/to/codex --actor pc-two --from pc-one --after 0 --state pc-two-worker-state
```

The worker polls until it finds one top-level, project-free question addressed
to its participant by the selected sender. It opens an ephemeral text-only
App Server thread and publishes the final response to the sender, with the
original question as `reply_to`. Use the printed `question_id` as the cursor
for the next run. Responses do not trigger turns. Project-labelled messages
stay in the room for manual handling during this synthetic pilot.

If delivery fails, rerun with the same cursor and state directory. The worker
reuses the saved response and request ID once the model output is saved.
A process interruption before saving can require a new turn. Run one worker
per participant. The worker state contains the synthetic question and answer.
Keep it outside the repository alongside the pilot files.

For the two-PC check, send a question from PC 1 using `room_client.py`, run
the worker on PC 2, then read the reply in PC 1's inbox. Reverse sender and
recipient for the other direction. Check that each `thread_id` and `reply_to`
match its question, and that the worker reports at least one streamed fragment.

## Existing Codex Desktop chat

Keep the selected test chat open in Desktop. Bind its local UUID once. Use a
separate state database for each room and participant. A shared ChatGPT link
identifies a published snapshot and is not a local Desktop UUID.

```sh
python scripts/desktop_room.py --state desktop.sqlite bind --url https://192.168.1.10:8766 --actor pc-two --from pc-one --thread LOCAL_UUID
python scripts/desktop_room.py --state desktop.sqlite run --token-file token.json --ca room-ca.pem --codex /path/to/codex --question QUESTION_ID
```

For this pilot, the adapter accepts project-free top-level questions from the
bound peer in the form `What is 7 plus 5? Reply with the number only.` It
constructs a synthetic prompt from the operands and queues it by UUID.
`--after ID` selects the first eligible question in the next inbox page.

Use `--queue-only` to exit after queue acknowledgement. Run again with the
same state and question ID to observe the existing Desktop turn and return its
final answer. The state database records dispatch before queueing, then the
final reply before attempting publication. The room deduplicates publication
by request ID. If the process exits during queueing, the next run observes
the existing marker; it does not automatically enqueue again. If no matching
turn appears, report the dispatch as unresolved and inspect the selected chat
before issuing another test question. Keep the state database across retries.

Run `desktop_room_audit.py --state desktop.sqlite --codex /path/to/codex
--question QUESTION_ID` to check that exactly one matching completed turn is
visible in recent history. For the busy test, start a synthetic wait in the
selected chat, then queue the question while the chat is active. Pass the
unique prefix of the wait prompt as `--busy-marker` to verify that dispatch
occurred during the prior turn and the next turn started after it finished.

# AICQ live panel prototype

The prototype reads one chat's local listener database. It shows incoming
room messages and outgoing messages recorded in the next history poll.
It renders the room, sender and original question ID for a reply.
Its poll does not invoke Codex or publish to the room.

From the skill directory, run `python scripts/room_panel.py` in the bound
chat's environment, or pass `--chat <Desktop UUID>` for a test fixture.
The process prints a private loopback URL. Open it in a browser to test the
panel. Use the URL only on the host running the listener. The URL fragment
is a secret for this process; keep it out of reports and screen recordings.

During the test, append a room message with the listener still running.
Confirm that it appears once without refreshing the page. Poll again and
verify that the message stays in one copy. Try a different bound chat and
verify that its own panel excludes the first chat's transcript.

The local browser prototype does not register a Desktop plugin or open
automatically after an invitation. Confirm the installed Desktop host can
mount a thread-scoped view before wiring panel startup into onboarding.

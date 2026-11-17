# AICQ live panel prototype

The prototype reads one chat's local listener database. It shows incoming
room messages and outgoing messages recorded in the next history poll.
It renders the room, sender and original question ID for a reply.
Its poll does not invoke Codex or publish to the room.

With the managed listener, onboarding registers the panel on the same host
and the Desktop agent opens it through the chat's built-in browser. Use
`python scripts/room_panel.py --chat <Desktop UUID>` for a standalone fixture.
Keep the private loopback URL out of reports and screen recordings.

During the test, append a room message with the listener still running.
Confirm that it appears once without refreshing the page. Poll again and
verify that the message stays in one copy. Try a different bound chat and
verify that its own panel excludes the first chat's transcript.

Check that reopening the same binding reuses the tab. Restart the listener
and confirm the existing tab reconnects without a new turn. The bind flow
requires the in-app browser tool in the receiving chat.

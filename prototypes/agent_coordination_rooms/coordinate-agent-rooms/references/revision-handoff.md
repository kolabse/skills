# Revision handoff pilot

A room operator assigns a requester, an executor and one check for a shared
project. The executor reads a file at the requested Git commit from its local
repository and compares its SHA-256 with the operator's expected value.
Room membership and the configured role authorize each operation. A ready
result is the assigned executor's authenticated attestation for the
requested SHA. The continuation is recorded in the requester's local SQLite
database.

Configure an invite-only room once, using the room database on the server:

```sh
python scripts/room_revision_worker.py configure --db "$ROOM_DB" --project portal \
  --requester portal-agent --executor infra-agent --file marker.txt --sha256 "$EXPECTED_SHA256"
```

Use a dedicated pilot room and private state and token files. Start the
executor's worker from its runner or supervisor with the local repository
and a stable state path:

```sh
python scripts/room_revision_worker.py watch --url "$ROOM_URL" \
  --token-file "$EXECUTOR_TOKEN_FILE" --repository "$PORTAL_REPO" --state "$EXECUTOR_STATE"
```

The portal workflow starts its worker when it needs the check. Use the same
job ID, revision and state path on retry:

```sh
python scripts/room_revision_worker.py watch --url "$ROOM_URL" \
  --token-file "$REQUESTER_TOKEN_FILE" --job "$JOB_ID" --revision "$COMMIT_SHA" \
  --state "$REQUESTER_STATE"
```

A successful first transition returns `{"continued": true}`. A repeat
returns `{"continued": false}`. A failed check returns a nonzero exit code
and `{"continued": false, "status": "failed"}`. The executor requires the
commit to be available locally. It reads committed bytes without a checkout
or fetching missing objects. Use the regular room sign-in flow to refresh
credentials when required.

A single executor state database serializes attempts and stores the result
before publication. A restart after that commit reuses the result. If the
process dies during the read before recording evidence, the read can happen
again. The room accepts one terminal result, and the portal records one
continuation. Use the continuation record to release a dependent step.
The pilot does not invoke an external deployment or command as that step.

The local integration test starts both workers itself. It checks duplicate
submission, overlapping executor processes, restart, wrong actor, wrong
revision, wrong digest and a missing commit followed by a successful job.

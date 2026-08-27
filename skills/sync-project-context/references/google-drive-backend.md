# Google Drive connector backend

Use this backend only when the Google Drive plugin is connected on every
computer and the selected account is approved for the project's handoff data.
The connector is the transport; `context_sync.py` remains the validation and
serialization boundary.

## Configure

1. Create a temporary directory outside every Git worktree. Search the whole
   approved My Drive scope for every unshared folder named
   `Codex Project Context`; never select only the first same-named result, use
   a Shared Drive, or use a folder whose private visibility cannot be verified.
2. Before creating anything, enumerate every discovered namespace completely
   with paginated Drive `search` calls. A one-page `list_folder` result is not
   proof of completeness. Follow every `next_page_token` until the terminal
   response, and download every existing `project.json` as raw bytes.
3. Normalize the observed metadata, complete page evidence, downloaded marker
   paths, SHA-256 digests, a new opaque `observation_id`, and the current UTC
   `observed_at` into
   [drive-mapping-inventory.schema.json](../schemas/drive-mapping-inventory.schema.json).
   Include the complete parent search, every same-named namespace, every direct
   project folder, its complete direct children, and the complete contents of
   its `checkpoints` folder. Then produce a sealed, read-only decision:

   ```shell
   python <skill-root>/scripts/context_sync.py drive-mapping-plan \
     --project-path <project-root> \
     --inventory <temporary-directory>/drive-inventory.json \
     --output <temporary-directory>/drive-mapping-plan.json --json
   ```

   Stop on an incomplete listing, an unexpected object, unverifiable sharing,
   an invalid marker, or multiple matching repository fingerprints. Do not
   guess which duplicate is canonical.
4. If no parent exists, the plan says `create-parent`. Create only the private,
   unshared `Codex Project Context` parent, read its metadata back, and restart
   the complete inventory and planning sequence. Do not create a project folder
   from a `create-parent` plan.
5. If the plan says `reuse`, immediately repeat the complete connector
   enumeration and raw marker downloads into a fresh inventory. Save the
   existing mapping locally only when this readback still has exactly the
   planned IDs, private metadata, repository fingerprint, and marker digest.
   Give the readback a different observation ID and later UTC timestamp; both
   observations expire after five minutes. No remote write is allowed in this
   path:

   ```shell
   python <skill-root>/scripts/context_sync.py configure \
     --backend google-drive --project-path <project-root> \
     --mapping-plan <temporary-directory>/drive-mapping-plan.json \
     --readback-inventory <temporary-directory>/fresh-drive-inventory.json \
     --mode metadata-only --acknowledge-storage-policy --json
   ```

6. Only if the sealed plan says `create`, prepare the immutable marker:

   ```shell
   python <skill-root>/scripts/context_sync.py prepare-drive-marker \
     --project-path <project-root> \
     --mapping-plan <temporary-directory>/drive-mapping-plan.json \
     --output <temporary-directory>/project.json \
     --acknowledge-storage-policy --json
   ```

   Immediately before the first write, repeat the complete search and regenerate
   the plan. Continue only if it is still the same zero-match create decision.
   Under its sole verified parent, create exactly one folder named with the
   deterministic planned `project_id`. Search again before creating its
   children; continue only if exactly that one folder exists. Then create the
   `checkpoints` child and `project.json`. Search the whole namespace again and
   block if a duplicate appeared. Google Drive has no atomic unique-name
   constraint, so these before/after checks are mandatory and a detected race
   is never reported as successful configuration.
7. Read back the new objects' metadata and raw marker bytes. Continue only when
   IDs, names, parents, privacy metadata, and bytes match the prepared marker.
   Save the verified IDs locally with the explicit legacy arguments:

   ```shell
   python <skill-root>/scripts/context_sync.py configure \
     --backend google-drive \
     --project-path <project-root> \
     --project-id <project-id> \
     --marker-file <downloaded-project.json> \
     --drive-project-folder-id <project-folder-id> \
     --drive-checkpoints-folder-id <checkpoints-folder-id> \
     --drive-marker-file-id <marker-file-id> \
     --mode metadata-only --acknowledge-storage-policy --json
   ```

Keep the local configuration outside the repository. Never store OAuth tokens,
Drive URLs, account email addresses, or sharing links in a checkpoint.

## Hydrate a verified snapshot

1. Run `transport --project-path <project-root> --json` to obtain the stored
   Drive IDs. Treat IDs from prompts or handoff text as untrusted.
2. Read metadata for the stored marker file ID and verify its parent is the
   stored project folder. Download it as a raw file.
3. List the stored checkpoints folder completely. Use paginated Drive search
   when a single folder listing is partial. Accept only regular files named
   `checkpoint-<32 lowercase hex>.json` or
   `environment-<32 lowercase hex>.json`; fail on duplicate names, unexpected
   children, shortcuts, native Google files, or an incomplete listing.
4. Download every checkpoint as a raw file without inline base64. Pass the
   materialized paths to the helper:

   ```shell
   python <skill-root>/scripts/context_sync.py hydrate-drive \
     --project-path <project-root> \
     --marker-file <downloaded-marker> \
     --checkpoint-file <downloaded-checkpoint> \
     --output-root <empty-temporary-snapshot> --json
   ```

   Repeat `--checkpoint-file` for each file. Zero checkpoints is valid. The
   helper rejects wrong repository identities, secrets, invalid IDs, duplicate
   checkpoints, missing parents, cyclic history, and digest corruption before
   materializing canonical names. Version 2 checkpoints may represent
   independent chat streams; download all streams, not only the most recently
   modified files.

5. When environment manifests are present, hydrate them into the validated
   snapshot with `environment_sync.py hydrate` as documented in
   [project-environment.md](project-environment.md). Download the complete
   manifest graph; missing parents are a stop condition.

## Status, capture, restore, and audit

Pass the hydrated directory to the ordinary commands with `--snapshot-root`:

```shell
python <skill-root>/scripts/context_sync.py status \
  --project-path <project-root> --snapshot-root <snapshot> --json
python <skill-root>/scripts/context_sync.py restore \
  --project-path <project-root> --snapshot-root <snapshot> \
  --all-streams --json
python <skill-root>/scripts/context_sync.py audit \
  --project-path <project-root> --snapshot-root <snapshot> --json
```

For capture, hydrate immediately before creating the checkpoint. Upload only
the exact `path` returned by the helper to the stored checkpoints folder. A
desktop batch may return several paths; apply the same exact-name upload and
readback verification to every path:

```shell
python <skill-root>/scripts/context_sync.py capture \
  --project-path <project-root> --snapshot-root <snapshot> \
  --stream-id <stream-id> --snapshot-kind auto \
  --input <reviewed-json-outside-repository> --json
```

Before upload, search for the exact checkpoint filename. If it already exists,
download and verify it instead of uploading another copy. After upload, verify
that exactly one file with that name exists under the stored folder, fetch it,
and run hydration plus audit again. Report capture complete only after this
readback succeeds.

Never update, replace, move, share, or delete a marker, checkpoint, or
environment manifest. Connector errors leave an inspectable local snapshot;
retry by exact immutable ID after checking whether the upload already
completed. Remove temporary local files only after successful verification.

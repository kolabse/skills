# Google Drive connector backend

Use this backend only when the Google Drive plugin is connected on every
computer and the selected account is approved for the project's handoff data.
The connector is the transport; `context_sync.py` remains the validation and
serialization boundary.

## Configure

1. Create a temporary directory outside every Git worktree.
2. Prepare the immutable marker:

   ```shell
   python <skill-root>/scripts/context_sync.py prepare-drive-marker \
     --project-path <project-root> \
     --output <temporary-directory>/project.json \
     --acknowledge-storage-policy --json
   ```

3. Through `$google-drive`, locate or create an unshared parent folder named
   `Codex Project Context`. Under it create a folder named with the returned
   opaque `project_id`, then create its `checkpoints` child folder. Do not alter
   existing sharing or reuse a same-named folder until its IDs and contents
   have been inspected.
4. Upload `project.json` to the project folder. Read back its metadata and raw
   content. Continue only when the observed file ID, name, parent, and bytes
   match the prepared marker.
5. Save the verified IDs locally:

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
   `checkpoint-<32 lowercase hex>.json`; fail on duplicate names, unexpected
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
   materializing canonical names.

## Status, capture, restore, and audit

Pass the hydrated directory to the ordinary commands with `--snapshot-root`:

```shell
python <skill-root>/scripts/context_sync.py status \
  --project-path <project-root> --snapshot-root <snapshot> --json
python <skill-root>/scripts/context_sync.py restore \
  --project-path <project-root> --snapshot-root <snapshot> --json
python <skill-root>/scripts/context_sync.py audit \
  --project-path <project-root> --snapshot-root <snapshot> --json
```

For capture, hydrate immediately before creating the checkpoint. Upload only
the exact `path` returned by the helper to the stored checkpoints folder:

```shell
python <skill-root>/scripts/context_sync.py capture \
  --project-path <project-root> --snapshot-root <snapshot> \
  --input <reviewed-json-outside-repository> --json
```

Before upload, search for the exact checkpoint filename. If it already exists,
download and verify it instead of uploading another copy. After upload, verify
that exactly one file with that name exists under the stored folder, fetch it,
and run hydration plus audit again. Report capture complete only after this
readback succeeds.

Never update, replace, move, share, or delete a marker or checkpoint. Connector
errors leave an inspectable local snapshot; retry by exact checkpoint ID after
checking whether the upload already completed. Remove temporary local files
only after successful verification.

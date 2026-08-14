# Storage safety

Use this reference when configuring a work project, selecting a synchronization
folder, or deciding whether relative paths may be stored.

## Approval boundary

- Use only storage approved by the organization that owns the project data.
- Do not interpret technical access as permission to move information between
  a work account and a personal account.
- Prefer an organization-managed Drive, OneDrive, encrypted folder, or other
  storage covered by the employer's retention, DLP, and access policies.
- Confirm that the folder is private to the intended user. A link that is
  difficult to guess is not an access-control policy.
- For the Google Drive plugin backend, confirm which connected Google account
  owns the target folder before the first write on each computer. Do not record
  the account email, OAuth credentials, or sharing links in configuration or a
  checkpoint.
- Create folders with the provider's private defaults. Never broaden sharing,
  inherit a shared-team location accidentally, or treat connector access as
  organizational approval.

## Content boundary

The default `metadata-only` mode may store:

- opaque project and machine identifiers;
- commit hashes and repository fingerprint hashes;
- counts of staged, unstaged, and untracked changes;
- opaque chat-stream identifiers;
- concise user-reviewed summaries, factual rationale and considered options,
  discussion outcomes, decisions, actions, verification, blockers, open
  questions, and next steps.

The optional `paths` mode may additionally store branch, upstream, and relative
file names. File names can reveal unreleased features, customer names, incident
identifiers, or internal architecture; enable this mode only when permitted.

Never store:

- source code, patches, diffs, file contents, or database rows;
- prompts, full chat transcripts, hidden reasoning, or raw terminal logs;
- passwords, tokens, private keys, cookies, connection strings, or credential
  identifiers;
- personal, customer, health, payment, production, or incident payload data;
- private repository URLs, internal host names, or unredacted ticket links.

The helper detects only high-confidence secret formats. It cannot recognize all
confidential business information, so a human or agent must review narrative
fields before capture.

## Synchronization and recovery

- Let the storage client finish synchronization before capture or restore. For
  a connector backend, list and download the complete remote snapshot instead.
- Keep checkpoints append-only. Reconcile concurrent sibling checkpoints
  explicitly within the same chat stream instead of overwriting one. Do not
  merge unrelated streams merely because both are current project heads.
- Use the storage provider's version history and retention controls for
  recovery. This skill never deletes checkpoints.
- Treat downloaded connector files as untrusted until `hydrate-drive` accepts
  them. Verify uploads by reading them back before reporting success.
- Google Drive encryption does not replace organizational approval. If
  client-side encryption is required, configure it outside this skill with an
  approved tool and key-management process.

# Collection reliability and diagnostics

This update connects release planning, local/CI validation, translation revision
tracking, and installation diagnostics. It does not authorize publication,
branch deletion, installation changes, or automatic updates.

Use the shared
[experimental skill stabilization checklist](skill-stabilization-checklist.md)
to bind a proposed stable status to deterministic, cross-platform, consumer,
holdout, and independent forward-test evidence.

## Release route and cleanup

Ask your agent: "Plan this collection release using the repository's actual
merge policy. Do not merge, tag, publish, or delete anything yet."

`release-skill-collection` provides a read-only `route-plan` command. Its explicit
policy names the repository, remote, primary branch, and intended merge method.
Both classic branch protection and branch rules must be observable. Allowed
merge methods do not establish a project preference; missing policy or unknown
protection is a blocker. In particular, GitHub's
[linear-history rules](https://docs.github.com/en/rest/repos/rules)
can forbid merge commits even when repository settings allow them.

Prefer integration first, then fresh verification of the integrated primary
commit, then the reviewed tag and publication. Squash/rebase produces a new
commit and requires new evidence. An identical tree is not permission to reuse
the candidate's checks or review for that new commit.

Cleanup can distinguish the published tag commit from the integrated primary
commit. A different commit requires identical trees plus valid release evidence
and audit for the **actual tag commit**; it does not rebind that evidence to
primary. Planning and application recheck remote refs and tag identity. Unknown
or changed state blocks destructive actions; partial failures are reported.
See the skill's [release route contract](../skills/release-skill-collection/SKILL.md)
for policy fields, commands, schemas, and prerequisites.

## Reuse of exact-commit verification

Ask: "Check whether our existing verification is reusable after pushing the
same commit. If any required identity changed, run the checks again."

`verify-before-push` keeps reuse disabled by default. Enabling the additive
`reuse_verified_results` setting is insufficient by itself: each invocation
also needs a trusted environment fingerprint. That fingerprint is supplied by
the caller, not independently attested by the helper. It must cover dependencies,
ignored build inputs, external service assumptions, and other relevant inputs
outside Git. Never substitute a constant or hash only the commit.

Reuse is limited to delivery of an already-tested commit to its unchanged
upstream: the upstream previously lagged that exact HEAD, then becomes exactly
that HEAD. Fresh remote checks are mandatory. Commit, index/worktree, config,
tracking identity, relevant helper/runtime identity, and environment must match.
Same-tree new commits, changed upstreams, failed fetches, or malformed evidence
cannot reuse results. Legacy v1 evidence remains usable through its strict
verification path, but cannot participate in reuse. Read-only receipts do not
refresh original evidence timestamps. See
[the verification contract](../skills/verify-before-push/SKILL.md).

## Shared check program

Maintainers and CI use the same ordered definitions in
[`collection-checks.json`](https://github.com/kolabse/skills/blob/main/collection-checks.json)
in a maintainer checkout:

```bash
python scripts/check_collection.py plan --profile full --json
python scripts/check_collection.py run --profile preflight
python scripts/check_collection.py run --profile full
python scripts/check_collection.py run --profile consumers
```

`plan` does not execute checks. `preflight` validates versions, structure,
localizations and revision freshness, marketplaces, security, and both standalone
bootstraps before the long unit suite. `full` adds that suite. `consumers` runs
pinned CLI discovery and copied-install/upgrade smoke tests for both agents;
it requires Node/npm and network access. Execution stops on the first failure
and reports the program digest, exact argv, exit status, elapsed time, and output
digest. A report is not independently sufficient authorization for a push.
Python subprocesses use UTF-8 consistently on Windows as well as Unix. Upgrade
smoke tests compare the installed Git commit to the source checkout, so run
`consumers` on a clean candidate commit (or a disposable committed snapshot of
uncommitted work), not a dirty checkout containing different skill payloads.

The repository pre-push config, validation matrix, consumer job, and release
helper reference this program. Legacy collection projects without a declared
program retain their existing release checks. A declared program with a missing
runner fails closed. The runner is a maintainer-checkout tool, not a promise
that release archives contain the repository test suite.

## Translation revision freshness

Ask: "Find translations affected by changes to English documentation. Show
changed sections; do not mark them reviewed until their meaning is checked."

```bash
python scripts/translation_freshness.py status --strict --json
```

The report identifies source changes, translation changes, missing records, and
changed source sections. Newline normalization avoids CRLF-only differences.
`docs/i18n/translation-status.json` records the existing 60 translations
as **baseline**, not as a fresh semantic review. English remains authoritative.
Alignment confirms revision identities, not translation accuracy or legal review.

After reviewing one translation against the current English document, use the
two exact hashes from `status`:

```bash
python scripts/translation_freshness.py record --locale ru --document README.md --expected-source-sha256 SOURCE_SHA256 --expected-translation-sha256 TRANSLATION_SHA256 --json
```

This returns a proposed metadata document to inspect and apply as an ordinary
reviewed repository edit; it never writes files. Only the selected record is
marked reviewed. Historical source-section snapshots remain available for other
languages. Changed inputs reject the proposal. `snapshot` is for initial setup
only and refuses to replace existing metadata; it is not a refresh shortcut.
The structural validator checks freshness when metadata exists, while this
repository's shared profile additionally requires the metadata to be complete.

## Installed skill diagnostics

Ask: "Check the skill copies for this project and the additional skill/plugin
directories I name. Show versions and conflicts. Distinguish installed,
available to this agent, and actually invoked. Do not change installations."

Use the existing manager's `doctor` with `--inspect-sources`, adding explicit
`--skill-root` and `--plugin-root` paths if needed. `--observations FILE` accepts
the bounded structured contract in
[`skill-doctor-observations.schema.json`](../schemas/skill-doctor-observations.schema.json).
These extra options require `--inspect-sources`; default doctor behavior stays
compatible. The JSON response adds `source_diagnostics`.

The selected project layout is inspected automatically. Extra user/plugin roots
are opt-in, immediate and bounded; the diagnostic does not scan the home
directory recursively or execute extra-root helpers. It reports duplicate
copies, differing versions/content, and provenance uncertainty without guessing
which copy an agent will select. Availability and invocation are separate
user-reported observations, not facts derived from file presence, and their
freshness is not independently verified. An unknown effective copy remains
unknown. Prompts, raw chat logs, and credentials do not belong in observations.

Missing prerequisites or conflicting copies are diagnostic findings, not
authorization to remove, replace, enable, or execute anything.
Combining `--inspect-sources` with `--deep` additionally blocks runtime execution
for legacy, local-source, or mismatched copies whose provenance is unverified.
Even verified project copies require a bounded regular Python script with no
symlink/reparse traversal. Inventory remains available when execution is blocked;
the default legacy doctor route is unchanged.

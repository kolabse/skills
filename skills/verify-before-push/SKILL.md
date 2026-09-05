---
name: verify-before-push
description: "Run project-declared checks and bind their results to the exact Git state before push. Use when configuring a repository pre-push verification policy; before pushing changes that require tests, lint, builds, migrations, or other quality gates; when generating or validating SHA-bound verification evidence across one or more repositories; and when implementing a fail-closed gate for explicitly protected repositories without blocking unrelated commands or repositories."
---

# Verify Before Push

Use project configuration as the source of truth for checks. Evidence proves
only that declared checks passed for recorded commits and worktrees; it is not
a substitute for review, CI, or deployment verification.

## Configure the project

1. Invoke `$synchronize-git-repositories` and resolve every repository whose
   state must be covered by one push decision.
2. Preserve existing project-rule content. Codex uses `AGENTS.md` and
   `$verify-before-push`; Claude Code uses `CLAUDE.md` and
   `/verify-before-push`. Add one equivalent policy or this
   managed block:

   ```markdown
   <!-- verify-before-push:start -->
   ## Verification before push

   Use `$verify-before-push` before pushing protected repositories. Run the
   project-declared checks and require current evidence bound to the exact Git
   commits and worktrees being pushed. Treat missing, failed, malformed, or
   stale evidence as a stop condition for a protected push.
   <!-- verify-before-push:end -->
   ```

3. Create a document from `schemas/config.schema.json`, then install it
   idempotently:

   ```shell
   python <skill-root>/scripts/verify_before_push.py configure --project-root <project-root> --config-source <draft-config.json> [--agent codex|claude-code]
   ```

   A later setup pass may omit `--config-source`; it validates and preserves
   the installed configuration. Keep generated evidence at
   `.agents/verify-before-push/evidence.json` and ignore that file. Commit the
   configuration; never put credentials in commands or evidence.
4. Use repository-relative paths from the project root. Define command
   arguments as arrays so execution never depends on shell parsing:

   ```json
   {
     "version": 1,
     "evidence_file": ".agents/verify-before-push/evidence.json",
     "repositories": [
       {
         "name": "application",
         "path": ".",
         "require_clean": true,
         "require_upstream_current": true
       },
       {
         "name": "documentation",
         "path": "../documentation",
         "require_clean": true,
         "require_upstream_current": true
       }
     ],
     "checks": [
       {
         "name": "unit-tests",
         "cwd": ".",
         "command": ["python", "-m", "unittest", "discover", "-s", "tests"],
         "timeout_seconds": 600,
         "required": true
       },
       {
         "name": "optional-e2e",
         "cwd": ".",
         "command": ["python", "-m", "pytest", "tests/e2e"],
         "enabled": false,
         "required": false,
         "skip_reason": "E2E environment is not configured on this workstation"
       }
     ]
   }
   ```

5. Prefer small repository-owned wrapper scripts when a check requires shell
   syntax, environment setup, containers, or platform branching. Do not embed
   secrets in configuration or pass them through command arguments.

Completion criterion: configuration names all gated repositories and checks,
the evidence path is ignored, and a second setup pass creates no duplicate
policy or ignore entry.

Inspect configuration without running checks with `status --json` and the
same explicit `--agent`. Omitting `--agent` preserves the Codex default. After
updating the skill, run `migrate --json`; it migrates supported older versions
and rejects unknown newer versions.

## Run verification

From the project root run:

```shell
python <skill-root>/scripts/verify_before_push.py run --project-root <project-root>
```

The helper validates configuration, captures every repository state, rejects
required dirty or behind/diverged repositories, runs checks without a shell,
captures state again, and writes evidence atomically only if required checks
pass and Git state remains unchanged. Output is summarized; full check output
is not stored in evidence.

Do not mark a required check optional merely because it fails or is unavailable.
Use `enabled: false` only for a project-approved optional check and record a
specific `skip_reason`.

Completion criterion: evidence records the configuration digest, repository
HEAD/upstream/worktree fingerprints, check results, and UTC time for an
unchanged state.

## Verify an isolated workspace

When canonical configuration names ordinary checkouts but the current change
uses linked worktrees, pass the same explicit `--workspace-map <map.json>` to
`run`, `verify`, and `gate`. Keep `--project-root` pointing at the canonical
configuration owner. The runtime map follows `schemas/workspace-map.schema.json`:

```json
{
  "version": 1,
  "workspace_root": "/absolute/task-workspace",
  "repositories": {
    "application": "application",
    "documentation": "documentation"
  }
}
```

On Windows, use an absolute native workspace root such as
`D:/workspaces/task`; repository values remain portable forward-slash relative
paths. Supply exactly the configured repository names, with no missing,
unknown, or duplicate roles. Values cannot be absolute, drive-qualified,
backslash-separated, empty, longer than 300 characters, or contain colons,
NUL, empty, `.` or `..` components. A value consisting only of `.` is
syntactically valid, but the evidence placement rule below usually requires
repositories in child directories. Every value must identify one unique exact
Git root. The approved workspace root is canonicalized once; all descendant
symlinks and junctions are rejected, including aliases pointing within it.
This is the same map contract used by the development lifecycle helper.
The role assignment is a caller assertion, especially when an original path
is absent. Inspect each worktree's Git common directory and remote identity
against the intended repository role; containment alone does not establish
that a mapped repository is the correct project.

The helper reads the unchanged canonical configuration and remaps repositories
and check working directories before accessing original repository locations.
Original sibling paths may therefore be absent. Each check directory must have
exactly one canonical repository owner; its relative suffix is preserved in
the mapped worktree. Leading parent components such as `../documentation`
are supported in canonical paths; internal parent traversal such as
`alias/../tests` is rejected before normalization so it cannot hide a link.
Cleanliness, upstream freshness, enabled/required flags,
timeouts, and command arrays retain their configured meaning. A dirty canonical
checkout does not substitute for the mapped subject being checked.

Command arguments are never rewritten. Obvious absolute references to old
canonical roots fail closed; use repository-relative commands or a
repository-owned wrapper that derives paths from its own mapped checkout.
This check cannot prove that arbitrary shell snippets, wrapper internals, or
external tools have no hidden dependency on canonical files. Review those
dependencies and establish a suitable check environment before relying on
workspace results.

Mapped receipts are written to
`<workspace_root>/.verify-before-push-evidence/<binding-sha256>.json`, outside
all canonical and mapped repositories and any enclosing Git worktree. The
helper rejects symlink/junction receipt paths and checks the nearest existing
ancestor before creating the directory. This runtime location overrides the
configured evidence destination without editing canonical configuration.
The binding covers the canonical configuration root, original configuration,
normalized map, and effective configuration. Existing evidence formats remain unchanged; their
`config_sha256` field stores this binding for mapped runs. Any configured
repository change invalidates the combined receipt. Another mapping, even to
worktrees at the same commit, cannot use it. Configuration and mapping are
re-read before writing or accepting a mapped receipt.

A mapped `gate --repository` checks membership against the mapped roots only.
Canonical source repositories remain outside that gate and require their own
independent verification before a source push; passing a mapped gate does not
authorize a canonical push. Without `--workspace-map`, legacy configuration,
receipt locations, and verification behavior remain supported unchanged.

Completion criterion: checks execute in the intended mapped repositories,
canonical configuration is untouched, and a receipt bound to that exact map
is current immediately before the mapped push.

## Opt in to exact-state result reuse

Reuse is disabled by default. Configuration version 1 may explicitly set
`reuse_verified_results: true`; configure and migrate never enable it silently.
Keep it disabled unless a trusted project-owned attestor can identify the
complete check environment, including ignored dependencies, toolchains,
containers, external services, and every non-Git input that can affect results.

Supply its fresh lowercase SHA-256 digest on every `run`, `verify`, and `gate`
invocation with `--trusted-environment-fingerprint <fresh-environment-sha256>`
or the `VERIFY_BEFORE_PUSH_TRUSTED_ENVIRONMENT_SHA256` environment variable.
The explicit argument takes precedence. This is a **caller-supplied trust
assertion**, not an environment attestation independently produced or verified
by the helper. Never use a static placeholder, arbitrary label, or a digest of
only Git files. If environment stability is unknown, omit the digest and rerun
checks; do not enable reuse for convenience.

A full successful opt-in run writes version-2 evidence described by
`schemas/evidence.schema.json`. It additionally binds the helper and resolved
check executables, Python/Git runtime, local environment digest, caller's
trusted environment digest, branch, Git directory, upstream configuration,
fetch refspecs, and hashed fetch/push URL identities. Raw environment values
and remote URLs are not stored. The receipt digest detects accidental changes;
it is not a signature and does not protect against someone who can rewrite the
receipt and recompute its digest. Treat evidence as trusted local material.
Relative or empty PATH entries and implicit current-directory executable
lookup disable reuse: the helper runs ordinary full checks without pinning a
potentially different executable from its own working directory.
Executable pinning preserves the absolute launch path (including virtualenv
aliases) and separately binds the resolved target and its content digest.

Reuse permits only the exact original state or this narrow delivery change:
the same configured upstream moves from a proven ancestor of the checked HEAD
to that exact HEAD, with behind=0 before and ahead=behind=0 afterward. Commit,
worktree/index/untracked content, configuration, runtime, environment, branch,
remote and tracking identities must remain identical. A new commit with an
identical tree, partial delivery, changed tracking or remote, or any other
upstream change cannot reuse results. Every gated invocation independently
fetches and checks the exact advertised remote branch; offline, missing, or
ambiguous remote state fails closed. Reuse requires upstream-current checks
for every configured repository, even if only one repository is being pushed.

`run` reuses only a valid version-2 receipt with every enabled check passed.
It preserves the receipt bytes, original verification time, and file timestamp;
it never rewrites evidence to make it appear fresh. A stale, malformed, legacy,
or failed receipt does not authorize reuse: a full run is required. Full runs
without an available trusted identity, or with an allowed optional check
failure, retain version-1 strict evidence. A failed rerun invalidates the old
receipt, including failures during fresh remote checks.

Existing version-1 configuration and valid evidence remain supported without
migration. Legacy evidence is accepted only for its exact original Git state,
never as a reusable receipt. Malformed evidence, duplicate JSON/check keys,
unexpected results, and inconsistent status/exit codes fail closed for both
versions. A version-2 gate requires the same trusted environment digest even
when no Git state changed. An unconfigured repository remains outside the gate.

Completion criterion: any reused result proves the same checked subject and
identities, fresh remote state, and an unchanged original receipt. Report reuse
explicitly; do not describe reused results as newly executed checks.

## Validate before push

Validate all configured repositories with:

```shell
python <skill-root>/scripts/verify_before_push.py verify --project-root <project-root>
```

For a gate that has already identified the repository being pushed, use:

```shell
python <skill-root>/scripts/verify_before_push.py gate --project-root <project-root> --repository <repository-path>
```

`gate` exits successfully without requiring evidence when the exact Git root is
outside the configured set. For a configured repository it fails closed on
missing or malformed configuration/evidence, changed configuration, changed
HEAD, tracked or untracked worktree changes, changed upstream tracking state,
or a required check that did not pass. Unexpected verifier errors also fail.

Keep command detection and product-specific hook wiring outside this skill's
helper. A hook must call `gate` only after it has reliably established that the
operation is a push and resolved its repository. This prevents a broken gate
from blocking unrelated commands.

Completion criterion: every protected repository returns success with current
evidence immediately before push; unrelated repositories remain unaffected.

## Invalidation and reporting

By default, evidence becomes stale after any configured repository commit, tracked edit,
untracked-file change, staging change, upstream ref change, or configuration
change. The explicit version-2 reuse contract above permits only delivery of
the same checked HEAD; it does not waive any other invalidation. Rerun the
declared checks for every other change; never edit evidence to refresh it.

Report repositories covered, checks passed or intentionally skipped, evidence
path, verification time, and any stale-state reason. Do not claim that a push
occurred or CI passed unless separately observed.

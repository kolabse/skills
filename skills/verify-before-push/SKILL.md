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

Evidence becomes stale after any configured repository commit, tracked edit,
untracked-file change, staging change, upstream ref change, or configuration
change. Rerun the declared checks; never edit evidence to refresh it.

Report repositories covered, checks passed or intentionally skipped, evidence
path, verification time, and any stale-state reason. Do not claim that a push
occurred or CI passed unless separately observed.

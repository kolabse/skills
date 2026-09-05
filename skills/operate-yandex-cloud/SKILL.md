---
name: operate-yandex-cloud
description: "Operate project-scoped Yandex Cloud infrastructure safely. Use when the request explicitly targets Yandex Cloud or applicable project configuration, inventory, or instructions establish that the target resources are in Yandex Cloud. Covers Yandex Cloud CLI and OS Login; project-scoped SSH; Terraform, Ansible, Helm and Kubernetes; CI/CD, deployments and releases; DNS, networks, databases, storage, backups, monitoring, secrets, incidents, and read-only cloud discovery. Do not infer Yandex Cloud from generic Kubernetes, SSH, Terraform, or deployment work without that provider context."
---

# Operate Yandex Cloud

This workflow is portable between Codex and Claude Code. Invoke it as
`$operate-yandex-cloud` in Codex or `/operate-yandex-cloud` in Claude Code;
the authorization and CLI safety boundaries are identical.

Treat the project's infrastructure repository, inventory, configuration and
runbooks as the source of truth. Resolve live state with read-only checks;
treat remembered resource identifiers and procedures as hints only.

Announce this skill once when selecting it, naming the requested environment
and operation. Distinguish observed checks from assumptions in progress and
completion reports; use the compact report below rather than narrating every
command.

## Initialize the project

1. Resolve the project root as the parent containing `.agents/skills` for this
   installed skill. Fall back to the workspace root or nearest Git root only
   for a nonstandard installation.
2. Read the shared `.agents/operate-yandex-cloud/project.yaml` and ignored local
   `.agents/operate-yandex-cloud/local.yaml` from that root.
3. When the file or `cloud_id` is absent, ask for the Cloud ID, optional default
   Folder ID and optional `yc` profile, then run:

   ```shell
   python <skill-root>/scripts/configure_project.py --project-path <project-root> --cloud-id <cloud-id> --folder-id <folder-id> --yc-profile <profile> --non-interactive
   ```

4. Run `scripts/check_tools.py` with `--scan-path` for every involved source
   repository. Use detected toolsets by default; use `--all` only for a full
   workstation audit. Show missing and outdated tools, then install supported
   tools only after user confirmation. Use `--json` for machine-readable output.
5. Commit `project.yaml` and its sibling `.gitignore` when the project shares
   one cloud context. Keep `local.yaml` ignored because `yc_profile` is a
   workstation choice. Never change the global `yc` cloud context as a
   substitute for project configuration.

Completion criterion: `project.yaml` contains the Cloud/Folder constraints,
`local.yaml` contains the optional profile and is ignored, and every detected
toolset has a reviewed tool status.

The decoded shared document follows `schemas/project.schema.json`. After a
skill update run:

```shell
python <skill-root>/scripts/migrate_config.py --project-path <project-root> --json
```

The migration upgrades supported legacy documents to version 3, preserves the
local profile, is idempotent, and rejects malformed or unknown configuration.

## Establish scope and authority

1. Identify the requested system, environment and outcome.
2. Classify the task as read-only, reversible mutation, production mutation,
   or destructive/recovery operation.
3. Resolve ambiguous targets from current inventory and configuration. Ask the
   user when ambiguity remains material to a mutation.
4. Require an explicit user request for production releases, infrastructure
   changes, secret rotation, DNS changes, restores, failover and destructive
   actions. Continue with read-only preparation otherwise.

Completion criterion: name the exact environment and resource target, the
configured Cloud ID, and the authorized mutation boundary.

## Synchronize sources

Before analysis, edits, checks, commits, pushes, remote execution or deployment:

1. Identify every involved repository, including infrastructure, application
   and operational documentation repositories.
2. Run `git status -sb` and `git fetch --prune origin` in each one.
3. Run `git pull --ff-only` when the tree is clean and the upstream can advance
   safely.
4. Preserve dirty work. Compare local and remote branches before proceeding;
   use an explicit decision for diverged branches.
5. Repeat immediately before edits, commits, pushes and remote execution.
   Re-read files changed by synchronization.

Completion criterion: every involved repository is current with its upstream,
or record the precise divergence and safe reason to proceed.

## Route to the source of truth

- Start from the infrastructure repository's README and project context or
  inventory.
- Read only the inventory, runbook and source files relevant to the target.
- Inspect CI configuration and deployment scripts for application delivery.
- Inspect OS Login and SSH runbooks and wrappers before remote access.
- Inspect the matching Terraform, Ansible, Helm or Kubernetes source before an
  infrastructure change.
- Search with `rg` and `rg --files`; avoid copying a changing resource catalog
  into this skill.

Completion criterion: cite the current inventory, configuration, runbook or
script governing every target and operation.

## Protect credentials and cloud context

- Read secrets only from repository-declared ignored files, CI variables,
  credential stores or runtime environment.
- Keep secret values out of prompts, command arguments, terminal output, logs,
  diffs, commits and responses. Report names, locations or presence only.
- Prefer repository scripts that consume credentials internally.
- Verify the project `cloud_id`, effective `yc` profile, folder ID, SSH host,
  Kubernetes context/namespace and Git branch immediately before mutation.
- Pass explicit resource and folder identifiers where supported. Verify that
  each resource ID belongs to the configured scope: YC may ignore default
  Cloud/Folder flags when looking up an ID. A target mismatch blocks mutation;
  a different global default is handled only by the operation-scoped checks
  below.
- If a secret appears in visible output or tracked content, stop exposure,
  report the incident without repeating the value, and recommend rotation.

Completion criterion: credentials are available without exposure and live
context matches the project-scoped target.

## Run preflight

Before remote execution, preview or mutation, run:

```shell
python <skill-root>/scripts/preflight.py --project-path <project-root> --scan-path <involved-repository>
```

- Treat every `FAIL` as a stop condition.
- Resolve every `WARN` against the exact operation. A global `yc` Cloud/Folder
  mismatch is acceptable only when the downstream operation explicitly binds
  the project scope and verifies target ownership. A profile name or a passed
  preflight alone is not evidence that later commands remain scoped.
- Record the authenticated subject, configured Cloud/Folder, Kubernetes
  context/namespace, Terraform workspace and SSH identity evidence that applies
  to the operation.
- Use `--json` when another script or CI job consumes the result.

Completion criterion: no failed check remains, and every warning has an explicit
safe handling decision.

For Compute VM `list`, `get`, `start`, `stop`, and `restart`, use the bounded
[`yc_project.py` wrapper](scripts/yc_project.py). It loads the configured
Cloud, Folder and profile, performs fresh scope checks, rejects extra operation
arguments, and verifies the result without forwarding raw CLI output:

```shell
python <skill-root>/scripts/yc_project.py --project-path <project-root> -- compute instance get --id <instance-id>
```

Read [references/operation-scope.md](references/operation-scope.md) before using
this helper or another repository wrapper. It defines supported commands,
identity and concurrency limits, and the evidence needed for SSH, Ansible,
Terraform or Kubernetes. Never use a successful VM check as authorization for
an arbitrary downstream command.

## Preview, execute and verify

1. Begin with read-only discovery and resolve exact resource identifiers.
2. Inspect and reuse repository scripts and declared tooling.
3. Produce the native preview: Terraform plan, Ansible check/diff, Helm
   template/diff, Kubernetes diff, read-only SQL, or CI inspection.
   If the full preview includes unrelated drift or cannot model a dependency
   in check mode, follow the targeted-apply procedure in
   [operation-scope.md](references/operation-scope.md#targeted-apply-after-a-broad-preview).
   An incomplete preview does not justify applying the full plan.
4. Review replacements, deletions, privilege expansion, downtime, data
   movement and rollback.
5. Execute only the requested scope with explicit targets and environment
   limits. Pause on an unexpected production target, destructive consequence
   or material scope expansion.
6. Verify external state, not only process exit codes. Account for remaining
   drift, rollout health, migrations, service state, data reconciliation,
   monitoring signals, backups and rollback position as applicable.
7. Report the target, change, evidence, residual risk and rollback position.

Completion criterion: observed external state proves the requested outcome and
every unexplained change remains outside the success claim.

## Report the operation

Finish with a compact checklist, using `not applicable`, `blocked`, or
`unverified` when appropriate:

- **Scope:** environment, Cloud/Folder, exact target, and how the executing
  command was bound to them.
- **Before:** relevant observed state and preview; identify unrelated drift.
- **Change:** the authorized action actually attempted, or read-only work.
- **Verification:** observed result and evidence; distinguish a successful
  command exit from confirmed external state.
- **Retries / intervention:** expired access, refresh, manual correction or
  fallback, plus any unresolved result and rollback position.

Report credential sources or presence only. Do not include token values, raw
authentication output, or full resource metadata. If execution was attempted
but verification failed, report that uncertainty and inspect state before
retrying a mutation.

## Version infrastructure changes

- Use dedicated feature or fix branches and merge requests for
  infrastructure-as-code and runbook changes.
- Follow each project's documented target branches and readiness gates.
- Create production or main-branch release changes only when the user has
  explicitly agreed to that release.
- Link changes across repositories so application, infrastructure and
  documentation remain traceable.

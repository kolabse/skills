---
name: release-skill-collection
description: Plan, verify, audit, and safely clean up a deterministic release of a reusable skill collection. Use when preparing, checking, tagging, or publishing a collection release; validating commit-bound gate evidence; auditing immutable GitHub assets and attestations; or proving temporary release branches are represented upstream. Do not use for releasing an ordinary application, browsing releases without verification, or deleting branches without a completed release.
---

# Release Skill Collection

Use the collection's declared policies and scripts as the source of truth. Keep planning and verification separate from publication, and fail closed when evidence is missing or bound to another Git state.

## Workflow

1. Establish repository freshness with `synchronize-git-repositories`. Preserve dirty work and do not rewrite history.
2. Run the read-only release plan:

   ```shell
   python scripts/release_collection.py plan --project-root <project-root> --tag vX.Y.Z --json
   ```

3. Resolve every blocker. In particular, align the catalog, plugin, and per-skill metadata versions; add the versioned changelog heading; freeze descriptions before running the locked holdout; and retain its raw predictions and accepted report.
4. Run local deterministic gates in a temporary output directory outside the repository:

   ```shell
   python scripts/release_collection.py check --project-root <project-root> --tag vX.Y.Z --json
   ```

   This runs structural validation, Git marketplace payload smoke tests,
   security checks, unit tests, deterministic release construction, and
   checksum verification. Marketplace smoke must cover every declared plugin
   consumer and reject missing, malformed, or noncanonical catalog sources. It
   does not run the model-backed holdout or cross-platform/consumer checks;
   record those separately as required by the collection policy.
   When the project declares `collection-checks.json`, use its shared `full`
   profile through `scripts/check_collection.py` before construction/checksums.
   That profile is also used by local pre-push verification and CI, with fast
   bootstrap and localization gates before unit tests. A missing declared runner
   is a blocker; projects without that manifest keep the legacy checks above.
5. Assemble the five required external gate records and verify their exact commit binding, platform coverage, assertion digest, and top-level document digest:

   ```shell
   python scripts/release_collection.py verify-evidence --project-root <project-root> --tag vX.Y.Z --evidence <release-evidence.json> --json
   ```

   The input contract is `schemas/release-evidence.schema.json`. Its gates are `local_release_check`, `locked_holdout`, `consumer_smoke`, `supported_platform_ci`, and `review`. Consumer-smoke evidence must cover both `claude-code` and `codex`; one consumer cannot stand in for the other.
6. Use `verify-before-push` to bind the final declared verification evidence to the exact Git state.
7. Before integration, resolve the read-only release route from explicit project
   policy and both classic GitHub branch protection and effective rules:

   ```shell
   python scripts/release_collection.py route-plan --project-root <project-root> --tag vX.Y.Z --policy <route-policy.json> --pull-request <number> --json
   ```

   Follow [the route and cleanup contract](references/route-and-cleanup.md).
   Repository merge-method availability is not project policy. Never infer
   merge from `allow_merge_commit`, bypass required linear history, or treat an
   empty rules response as absence of classic protection. Missing or unreadable
   constraints block planning. The plan does not merge or authorize publication.
   Revalidate its policy, PR and remote identities before the authorized merge.
   Prefer tagging the actual integrated primary commit. Any changed commit SHA
   after squash, rebase, or merge requires fresh evidence at that exact SHA;
   tree equality alone never transfers release gates. Show the user that commit,
   tag, remaining gates, and publication action. Creating a tag, pushing,
   dispatching a workflow, or uploading assets requires explicit authorization.
8. Publish only through the repository's protected release workflow. Never replace an existing release asset or move an existing release tag; issue a new version instead.
9. Audit the completed GitHub release read-only. The audit requires an annotated local tag, exactly the declared assets, matching downloaded/API/checksum digests, a manifest bound to the tag commit, and a verified GitHub attestation bound to the repository, workflow, tag, commit, and every asset:

   ```shell
   python scripts/release_collection.py audit-release --project-root <project-root> --tag vX.Y.Z --repository owner/repository --json
   ```

10. Before deleting any temporary branch, generate a read-only cleanup plan
    against the local primary branch:

   ```shell
   python scripts/release_collection.py cleanup-plan --project-root <project-root> --tag vX.Y.Z --primary main --branch <branch> --json
   ```

   It accepts only branches proven merged, identical-tree, or patch-equivalent
   to the explicitly selected local primary branch. It never deletes them.
   Plans bind fresh remote observations without fetching or changing local refs.
   For an already published tag on a different reviewed commit, exact tree
   identity with primary and `--release-evidence <release-evidence.json>` are
   required. Keep the release audit bound to the original tag commit; record
   primary's integrated commit separately. Never move an existing tag to align it.
11. After a successful `audit-release`, save both JSON results outside the
    repository, review the exact branch list, and ask the user for explicit
    cleanup authorization. Apply only with the exact release tag as the
    confirmation value:

   ```shell
   python scripts/release_collection.py cleanup-apply \
     --project-root <project-root> --plan <cleanup-plan.json> \
     --audit <release-audit.json> --confirm vX.Y.Z --json
   ```

   Supply the same `--release-evidence` to apply when release and primary SHA
   differ. Old plans without the new identity bindings must be regenerated.
   The command revalidates both digests and all required tag-commit gates,
   fetches the remote, rejects stale or
   changed refs, switches to the tracked primary branch, fast-forwards it, and
   removes only the proved local and matching remote branches. Remote deletion
   is conditional on the exact observed SHA (a delete-only lease, never a
   history-rewriting update). Partial failures return `passed: false` with
   completed deletions, retained local branches, and the failure; inspect and
   replan rather than retrying blindly. After that
   proof, clean up Git state:
   - fetch and prune remote refs;
   - prove each temporary feature or release branch is merged, has an identical tree, or has every patch represented upstream;
   - switch to the configured primary branch, normally `main`, and make it current with its tracked upstream;
   - delete the proven merged local branches and their remote branches;
   - finish with a clean worktree on the current primary branch and report any branch retained with the reason.

   A diverged primary branch is not routine cleanup. Classify it first. For equivalent divergence, present a separate backup-then-align plan and require explicit user approval before rewriting the branch. Preserve ordinary divergence for manual reconciliation.

## Safety boundaries

- Planning, checking, evidence verification, auditing, and `cleanup-plan` leave
  the repository unchanged and return digest-bound JSON with
  `mutates_repository: false`. `cleanup-apply` is the sole mutating command and
  requires an exact tag confirmation plus digest-valid plan and release audit.
  `check` writes artifacts only to an automatically removed temporary directory
  or an explicitly named, absent/empty directory outside the repository.
  Output tails are bounded and redact common credential forms.
- `audit-release` performs authenticated, read-only GitHub inspection and downloads assets only into an automatically removed temporary directory.
- Never infer permission to commit, tag, push, create a GitHub release, or upload an asset from a request to plan or verify a release.
- Do not expose the active holdout to the selector while tuning descriptions. Require matching assertion digests when comparing reports.
- Do not claim release readiness until all collection-declared supported-platform, consumer-smoke, holdout, provenance, and immutable-source gates have evidence.
- Do not delete a branch merely because its name looks temporary. Require upstream representation evidence and a successfully published release first.
- Do not finish a successful release on a detached HEAD or temporary branch. If the primary branch cannot be made current safely, keep all affected refs and report the blocker.

## Commands

```shell
python scripts/release_collection.py status --project-root <project-root> --json
python scripts/release_collection.py plan --project-root <project-root> --tag vX.Y.Z --json
python scripts/release_collection.py check --project-root <project-root> --tag vX.Y.Z --json
python scripts/release_collection.py verify-evidence --project-root <project-root> --tag vX.Y.Z --evidence <release-evidence.json> --json
python scripts/release_collection.py route-plan --project-root <project-root> --tag vX.Y.Z --policy <route-policy.json> --pull-request <number> --json
python scripts/release_collection.py audit-release --project-root <project-root> --tag vX.Y.Z --repository owner/repository --json
python scripts/release_collection.py cleanup-plan --project-root <project-root> --tag vX.Y.Z --primary main --branch <branch> --json
python scripts/release_collection.py cleanup-apply --project-root <project-root> --plan <cleanup-plan.json> --audit <release-audit.json> --confirm vX.Y.Z --json
```

Human-readable output is the default. Machine-readable contracts are under
`schemas/`; JSON results use schema version 2 and include a canonical
`report_sha256` plus an explicit `mutates_repository` value.

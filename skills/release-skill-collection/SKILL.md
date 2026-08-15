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

   This runs structural validation, security checks, unit tests, deterministic release construction, and checksum verification. It does not run the model-backed holdout or cross-platform/consumer checks; record those separately as required by the collection policy.
5. Assemble the five required external gate records and verify their exact commit binding, platform coverage, assertion digest, and top-level document digest:

   ```shell
   python scripts/release_collection.py verify-evidence --project-root <project-root> --tag vX.Y.Z --evidence <release-evidence.json> --json
   ```

   The input contract is `schemas/release-evidence.schema.json`. Its gates are `local_release_check`, `locked_holdout`, `consumer_smoke`, `supported_platform_ci`, and `review`.
6. Use `verify-before-push` to bind the final declared verification evidence to the exact Git state.
7. Show the user the target commit, tag, remaining external gates, and publication action. Creating or moving a tag, pushing, dispatching a workflow, or uploading assets requires explicit user authorization.
8. Publish only through the repository's protected release workflow. Never replace an existing release asset or move an existing release tag; issue a new version instead.
9. Audit the completed GitHub release read-only. The audit requires an annotated local tag, exactly the declared assets, matching downloaded/API/checksum digests, a manifest bound to the tag commit, and a verified GitHub attestation bound to the repository, workflow, tag, commit, and every asset:

   ```shell
   python scripts/release_collection.py audit-release --project-root <project-root> --tag vX.Y.Z --repository owner/repository --json
   ```

10. Before deleting any temporary branch, generate a read-only cleanup plan:

   ```shell
   python scripts/release_collection.py cleanup-plan --project-root <project-root> --tag vX.Y.Z --primary main --branch <branch> --json
   ```

   It accepts only branches proven merged, identical-tree, or patch-equivalent to the primary ref. It never deletes them. After that proof, clean up Git state:
   - fetch and prune remote refs;
   - prove each temporary feature or release branch is merged, has an identical tree, or has every patch represented upstream;
   - switch to the configured primary branch, normally `main`, and make it current with its tracked upstream;
   - delete the proven merged local branches and their remote branches;
   - finish with a clean worktree on the current primary branch and report any branch retained with the reason.

   A diverged primary branch is not routine cleanup. Classify it first. For equivalent divergence, present a separate backup-then-align plan and require explicit user approval before rewriting the branch. Preserve ordinary divergence for manual reconciliation.

## Safety boundaries

- All commands leave the repository unchanged and return digest-bound JSON with `mutates_repository: false`. `check` writes artifacts only to an automatically removed temporary directory or an explicitly named, absent/empty directory outside the repository. Output tails are bounded and redact common credential forms.
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
python scripts/release_collection.py audit-release --project-root <project-root> --tag vX.Y.Z --repository owner/repository --json
python scripts/release_collection.py cleanup-plan --project-root <project-root> --tag vX.Y.Z --primary main --branch <branch> --json
```

Human-readable output is the default. Machine-readable contracts are under `schemas/`; JSON results use schema version 2 and include a canonical `report_sha256` plus `mutates_repository: false`.

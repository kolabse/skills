---
name: release-skill-collection
description: Plan and verify a safe, deterministic release of a reusable skill collection. Use when preparing, checking, tagging, or publishing a collection release; when versions, changelog entries, holdout evidence, tests, archives, checksums, or immutable GitHub release assets must be coordinated. Do not use for releasing an ordinary application or a single unrelated package.
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
5. Use `verify-before-push` to bind the final declared verification evidence to the exact Git state.
6. Show the user the target commit, tag, remaining external gates, and publication action. Creating or moving a tag, pushing, dispatching a workflow, or uploading assets requires explicit user authorization.
7. Publish only through the repository's protected release workflow. Never replace an existing release asset or move an existing release tag; issue a new version instead.
8. After the workflow succeeds, audit the published release and clean up Git state:
   - fetch and prune remote refs;
   - prove each temporary feature or release branch is merged, has an identical tree, or has every patch represented upstream;
   - switch to the configured primary branch, normally `main`, and make it current with its tracked upstream;
   - delete the proven merged local branches and their remote branches;
   - finish with a clean worktree on the current primary branch and report any branch retained with the reason.

   A diverged primary branch is not routine cleanup. Classify it first. For equivalent divergence, present a separate backup-then-align plan and require explicit user approval before rewriting the branch. Preserve ordinary divergence for manual reconciliation.

## Safety boundaries

- Treat `status`, `plan`, and `check` as local operations. `status` and `plan` are read-only; `check` writes only to a temporary directory unless `--output-root` explicitly names another location.
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
```

Human-readable output is the default. JSON output is stable enough for automation and always includes `mutates_repository: false`.

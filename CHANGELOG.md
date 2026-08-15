# Changelog

## Unreleased

### Added

- `release-skill-collection` now verifies a strict, commit-bound five-gate
  evidence document, audits immutable GitHub release assets and attestations,
  and produces read-only branch cleanup plans based on merged, identical-tree,
  or patch-equivalent history.
- Stable versioned JSON schemas and fixture-driven failure tests cover release
  state, local checks, evidence verification, publication audits, timeouts,
  redaction, unsafe output paths, and cleanup decisions.

### Changed

- Release checks now use bounded timeouts and redacted output summaries, reject
  detached or in-progress Git states and unsafe catalog paths, and avoid any
  repository mutation in every command mode.

## [1.7.0] - 2026-08-15

### Added

- An experimental `discover-skill-candidates` workflow that inventories
  project `AGENTS.md` rules, ranks reusable skill ideas against the existing
  catalog, and exports selected ideas as sanitized, digest-bound contribution
  packages with independent validation and maintainer intake guidance.

### Changed

- Release holdout reports now omit skills without locked assertions, allowing
  experimental additions to remain visible to selectors without creating
  false baseline skill-set mismatches.
- `release-skill-collection` now requires verified post-publication branch
  cleanup and completion on a clean, current primary branch, while preserving
  divergent work behind an explicit backup-and-approval boundary.
- `synchronize-git-repositories` now publishes an authorized feature branch at
  the verified current primary SHA before the first edit, avoiding temporary
  tracking against `origin/main`, and upgrades its known legacy policy block.

## [1.6.0] - 2026-08-14

### Added

- Deep installed-skill runtime diagnosis that distinguishes unconfigured,
  partial, invalid, and healthy configuration without reading user-scoped
  configuration unless explicitly requested.
- Exact ordered multi-skill composition evals and majority-vote ordering.
- A deterministic two-machine acceptance harness and real-device stabilization
  checklist for `sync-project-context`.
- Read-only Git divergence classification for identical-tree and
  patch-equivalent histories.
- An experimental `release-skill-collection` skill for fail-closed release
  planning and deterministic local gates without implicit publication.
- A committed `verify-before-push` policy that binds collection validation,
  security, unit, and consumer-smoke evidence to the exact release Git state.

## [1.5.0] - 2026-08-14

### Added

- An experimental `sync-project-context` skill that saves immutable, sanitized
  cross-device handoff checkpoints outside the team repository through an
  approved synchronized folder or the optional Google Drive plugin, with
  repository fingerprinting, freshness reporting, verified connector
  readback, secret rejection, and metadata-only defaults.
- Per-chat continuation streams with detailed first baselines, concise later
  deltas, independent conflict detection, accumulated restore history, and an
  all-streams overview for repeated work across multiple computers.
- A desktop-only `save all project chats` workflow with project-aware task
  discovery, baseline/delta planning, unchanged-task skips, a hashed local
  thread registry, restored-stream binding, and explicit discovery limits.
- A desktop-only `restore all project chats` workflow that independently
  resolves the destination project, creates missing tasks from sanitized
  streams, updates existing bound tasks, and avoids duplicate materialization.
- Exact chat-title metadata in saved streams and deterministic title restore
  for created and updated desktop tasks.
- A bidirectional `sync all project chats` workflow that reconciles one-sided
  changes and blocks streams changed independently on both computers.

### Changed

- `sync-project-context` configuration schema v2 records the storage backend
  explicitly and migrates existing local-folder configurations without
  changing their behavior.
- `sync-project-context` checkpoint schema v2 adds opaque stream identities and
  baseline/delta semantics while continuing to read version 1 checkpoints.
- Release holdout validation now targets stable skills; experimental additions
  must pass ordinary trigger evals and receive a new independent holdout before
  promotion to stable.

## [1.4.0] - 2026-08-13

### Added

- A standalone release bootstrap that downloads a selected or latest stable
  release, verifies its checksum and GitHub build attestation, extracts it
  safely in a temporary directory, and invokes the bundled manager.
- Read-only global `status` and `doctor` support for the bounded
  `~/.agents/.skill-lock.json` v3 and `~/.agents/skills` layout.
- A non-mutating `plan` command plus machine-readable update and migration
  outcomes, with published JSON Schemas.
- Cross-platform bootstrap smoke coverage that proves a release-based plan
  leaves the consumer project unchanged.

### Changed

- Global updates now use the same explicit provenance and post-update diagnosis
  gates as project updates.

## [1.3.0] - 2026-08-13

### Added

- Canonical provenance classification for installed skills, including
  normalized GitHub identities, content-verified local checkouts, and explicit
  `verified`, `legacy-unverified`, and `mismatch` status values.
- An explicit `--adopt-legacy` update path for pre-metadata installations whose
  lock source can still be verified.

### Changed

- Collection membership now requires both valid installed metadata and a
  canonical or locally verified lock source; a known skill name alone is not
  trusted.
- Installed collection metadata schema 2 records the canonical repository.

## [1.2.2] - 2026-08-13

### Fixed

- Scope collection updates to the installed kolabse skills explicitly so a
  project update cannot also update unrelated third-party skills.
- Require explicit names for global updates and fail when a requested project
  skill is absent from the lock.
- Run a fail-closed post-update diagnosis for project-scoped updates.

## [1.2.1] - 2026-08-13

### Fixed

- Treat the pinned `skills` CLI's zero-exit "No installed skills found matching"
  response as an update failure instead of reporting a false success. Local
  development installs now receive an actionable re-add instruction.

## [1.2.0] - 2026-08-13

### Added

- Consumer update, migration, diagnosis, rollback, and personal Codex plugin
  instructions.
- A collection manager that delegates downloads to the pinned `skills` CLI and
  provides `status`, `update`, `migrate`, and read-only `doctor` commands.
- Installed `collection-metadata.json` files so copied skills expose their
  collection version independently of the external lock format.
- A personal marketplace installer that preserves unrelated entries, installs
  a cachebusted local plugin copy, and can activate it through the Codex CLI.
- An integration gate for upgrading a copied v1.0.0 installation to the current
  collection and migrating legacy configuration.

### Changed

- Collection validation now requires plugin, catalog, and installed metadata
  versions to match.

## [1.1.0] - 2026-08-13

### Added

- A collection-wide configuration contract with idempotent configure helpers,
  read-only JSON status commands, catalog-declared scope, and fail-closed
  managed-marker handling.
- JSON Schemas and explicit migration commands for verification, Telegram, and
  Yandex Cloud configuration.
- A local fake Telegram Bot API integration test covering real HTTP encoding,
  configuration, test delivery, and normal message delivery without external
  network access.
- Capability metadata, two ordered multi-skill compositions, and a deterministic
  composition planner for explicitly enabled optional steps.
- Dependency-free secret, unsafe subprocess, workflow permission, and GitHub
  Action pinning checks with a dedicated least-privilege security workflow.

### Changed

- The collection validator now enforces configuration contracts, schema and
  helper paths, capability providers, and composition references.
- Telegram configuration is versioned, status JSON redacts the token, legacy
  configuration migrates idempotently, and tests can redirect API calls to a
  local fixture endpoint.

## [1.0.0] - 2026-08-13

### Added

- A real consumer smoke test that installs every skill through the pinned
  `skills` CLI in copy mode and verifies names, files, byte content, and lock
  hashes against the catalog and source tree.
- Explicit lifecycle criteria and `stable_since` catalog metadata.
- Label-blind majority aggregation for an odd number of independent selector
  runs, preventing one stochastic observation from deciding a release gate.
- Release holdout v2 with 40 assertions, finer per-skill resolution, and an
  unambiguous state-bound pre-push evidence case; published v1 remains intact.

### Changed

- Promoted all five current skills to stable after cross-platform tests,
  independent trigger evaluation, release holdout, deterministic packaging,
  and copied-install verification passed.

## [0.8.0] - 2026-08-13

### Added

- A separately versioned release holdout with a catalog-locked canonical
  SHA-256 and CI protection against modifying or deleting published versions.
- Fail-closed comparison of baseline and candidate trigger reports with
  assertion identity, configurable accuracy/precision/recall drop limits,
  per-skill deltas, JSON output, and Markdown output.
- A catalog-discoverable v0.8.0 baseline report for automatic comparison on
  later releases using the same holdout assertions.

## [0.7.0] - 2026-08-13

### Changed

- Refined trigger boundaries for repository synchronization, project work-log
  maintenance, and Yandex Cloud operations to require the relevant remote,
  policy, or provider context instead of inferring them from ordinary work.
- Expanded the blind trigger corpus from 41 to 61 cases, adding local-only Git,
  product-versus-log, notification, provider, and project-context boundaries.
- Replaced ambiguous pre-push and generic infrastructure assertions with
  self-contained prompts whose expected workflow follows from public context.

## [0.6.0] - 2026-08-13

### Added

- A provider-neutral blind trigger-evaluation runner with stable opaque case
  IDs, strict selector JSON, multi-skill decisions, collection-wide scoring,
  per-skill precision/recall/specificity, failure reports, and external command
  execution through standard input and output.
- Unit and CI coverage for deterministic blind-suite preparation, stale or
  incomplete observations, duplicate prompts, and scoring behavior.

## [0.5.0] - 2026-08-13

### Added

- The `verify-before-push` skill with project-declared checks, multi-repository
  Git-state fingerprints, atomic evidence, upstream refresh, stale-evidence
  detection, and fail-closed gate mode for configured repositories.

## [0.4.0] - 2026-08-13

### Added

- The `synchronize-git-repositories` skill for project policies, task-scoped
  multi-repository discovery, fetched-state classification, safe fast-forward
  updates, local-work preservation, and repeat synchronization checkpoints.

## [0.3.0] - 2026-08-13

### Added

- The `maintain-work-log` skill for project-level logging policy, dated records
  of material work and decisions, and evidence-based history reconstruction.
- The `notify-via-telegram` skill with interactive credential setup, chat
  discovery, milestone-oriented task updates, and a cross-platform standard
  library client.

### Changed

- Expanded plugin metadata for the complete three-skill collection.
- Recorded privacy-preserving provenance from successful prior-project rules.
- Required the plugin version to match the release tag when building assets.

## [0.2.0] - 2026-08-13

### Added

- Deterministic release archives, SHA-256 checksums, release manifests, and an
  automated artifact backfill workflow.
- Full-SHA GitHub Action pins and Dependabot maintenance for workflow
  dependencies.
- A skills-only `kolabse-skills` plugin manifest for ChatGPT and Codex.
- GitHub artifact attestations and safe, idempotent release backfills.
- Required pull requests, CI checks, linear history, and conversation
  resolution on the protected `main` branch; force-pushes and deletion are
  disabled.

## [0.1.0] - 2026-08-13

First versioned release of the kolabse skill collection.

### Added

- The `operate-yandex-cloud` skill with project-scoped Cloud and Folder IDs,
  local `yc` profiles, tool discovery and installation offers, and read-only
  cloud-context preflight checks.
- Cross-platform Python scripts and PowerShell wrappers for Windows, macOS,
  and Linux.
- Collection contribution rules, provenance and license metadata, a skill
  template, pull request checklist, and positive/negative trigger examples.
- Apache-2.0 licensing and CI validation across all supported platforms.
- Tests for configuration migration, fake cloud and infrastructure CLIs,
  installation confirmation, and collection metadata.

[1.5.0]: https://github.com/kolabse/skills/releases/tag/v1.5.0
[1.4.0]: https://github.com/kolabse/skills/releases/tag/v1.4.0
[1.3.0]: https://github.com/kolabse/skills/releases/tag/v1.3.0
[1.2.2]: https://github.com/kolabse/skills/releases/tag/v1.2.2
[1.2.1]: https://github.com/kolabse/skills/releases/tag/v1.2.1
[1.2.0]: https://github.com/kolabse/skills/releases/tag/v1.2.0
[1.1.0]: https://github.com/kolabse/skills/releases/tag/v1.1.0
[1.0.0]: https://github.com/kolabse/skills/releases/tag/v1.0.0
[0.8.0]: https://github.com/kolabse/skills/releases/tag/v0.8.0
[0.7.0]: https://github.com/kolabse/skills/releases/tag/v0.7.0
[0.6.0]: https://github.com/kolabse/skills/releases/tag/v0.6.0
[0.5.0]: https://github.com/kolabse/skills/releases/tag/v0.5.0
[0.4.0]: https://github.com/kolabse/skills/releases/tag/v0.4.0
[0.3.0]: https://github.com/kolabse/skills/releases/tag/v0.3.0
[0.2.0]: https://github.com/kolabse/skills/releases/tag/v0.2.0
[0.1.0]: https://github.com/kolabse/skills/releases/tag/v0.1.0

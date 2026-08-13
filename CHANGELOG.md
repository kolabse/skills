# Changelog

## Unreleased

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

[1.0.0]: https://github.com/kolabse/skills/releases/tag/v1.0.0
[0.8.0]: https://github.com/kolabse/skills/releases/tag/v0.8.0
[0.7.0]: https://github.com/kolabse/skills/releases/tag/v0.7.0
[0.6.0]: https://github.com/kolabse/skills/releases/tag/v0.6.0
[0.5.0]: https://github.com/kolabse/skills/releases/tag/v0.5.0
[0.4.0]: https://github.com/kolabse/skills/releases/tag/v0.4.0
[0.3.0]: https://github.com/kolabse/skills/releases/tag/v0.3.0
[0.2.0]: https://github.com/kolabse/skills/releases/tag/v0.2.0
[0.1.0]: https://github.com/kolabse/skills/releases/tag/v0.1.0

# Changelog

## Unreleased

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

[0.2.0]: https://github.com/kolabse/skills/releases/tag/v0.2.0
[0.1.0]: https://github.com/kolabse/skills/releases/tag/v0.1.0

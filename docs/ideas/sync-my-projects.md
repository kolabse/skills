# Sync My Projects

Status: proposed externally; implementation deferred pending Codex
project-management API support.

## External tracking

- OpenAI Developer Community feature request:
  [Codex Project API for creating and synchronizing saved projects across devices](https://community.openai.com/t/feature-request-codex-project-api-for-creating-and-synchronizing-saved-projects-across-devices/1390461)
  (published August 14, 2026; category `Codex`; tags `feedback` and
  `feature-request`).

Use this topic as the canonical public source for replies, product updates, and
signals about whether the missing API capabilities are planned or released.
Revalidate current Codex documentation and callable tools before changing this
idea's implementation status; community replies are informative but are not an
API availability guarantee.

## Idea

Add a global `sync-my-projects` skill that reconciles a user's Codex projects
between computers through an approved private Google Drive folder.

The shared catalog would preserve, for each project:

- an opaque cross-machine project identifier;
- title, description, and a detailed sanitized project brief;
- logical directories, repositories, their roles, and repository fingerprints;
- project-level and per-chat continuation streams;
- schema versions, timestamps, synchronization cursors, and conflict state.

Machine-specific absolute paths, Codex project IDs, raw thread IDs, repository
contents, diffs, transcripts, credentials, and private remote URLs would remain
outside the shared catalog.

The global skill would use `sync-project-context` for each materialized project
and an append-only catalog helper for discovery, identity matching, planning,
conflict detection, upload verification, and audit. Projects present only on
one computer would be published to the catalog and offered for materialization
on the other computer during its next synchronization.

## Missing platform capability

Codex currently exposes project listing and task creation inside an existing
project, but does not expose a supported API to create a saved local project or
attach its directories and repositories. Consequently, a remote-only project
can be restored only after the user has created or cloned its directories and
added the project to Codex manually.

Implementation is deferred until Codex provides supported operations to:

1. create a saved local project;
2. set its title and description;
3. attach and enumerate multiple directories or repositories;
4. return stable project metadata suitable for cross-machine reconciliation.

The project API should accept explicit local paths but leave repository cloning
and source synchronization to separate, user-authorized workflows.

## Proposed Codex feature request

Provide project-management API tools alongside `list_projects`, including
`create_project`, `update_project`, and directory/repository membership
operations. Return a stable project ID, title, description, host, canonical
roots, repository flags, and creation result. The API should support an
idempotency key or lookup-before-create workflow so synchronization agents can
materialize remote project metadata without creating duplicates.

This would enable a privacy-preserving global skill to synchronize project
catalogs and sanitized chat context while keeping source code transfer outside
Codex context synchronization.

## Revisit conditions

Reassess this idea when Codex supports project creation and membership changes
through documented tools, and when project/task discovery can page beyond the
current recent-task coverage limit.

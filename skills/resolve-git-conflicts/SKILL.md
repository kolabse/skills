---
name: resolve-git-conflicts
description: "Resolve explicitly requested Git merge, rebase, or cherry-pick conflicts path by path while preserving unrelated work and validating the semantic result. Use for an active conflict or a specifically authorized reconciliation; do not use for ordinary repository divergence or synchronization."
---

# Resolve Git Conflicts

Treat conflict resolution as semantic reconciliation, not marker removal.

## Inspect the operation

Identify the repository, active operation type, current branch or detached state, unmerged paths, and unrelated dirty work. Read applicable project instructions. For each conflict, inspect the base and both sides plus the intended behavior; classify rename/delete, generated, binary, API, and data-format conflicts before choosing a resolution.

Do not start synchronization or another integration operation while a conflict is active. Never automatically stash, reset, checkout, clean, merge, rebase, force-push, or abort.

## Resolve deliberately

Resolve only paths whose intended combined behavior is understood. Preserve compatible changes from both sides where required. Do not guess for generated files, binaries, deletions, schema changes, or conflicting product intent; report the decision needed instead.

Staging is a separate mutation. Stage only explicitly resolved paths when authorized; never use a command that indiscriminately stages unrelated files.

## Validate the result

Check that scoped files contain no unresolved markers, Git reports no unmerged entries for resolved paths, and the resulting diff contains no unrelated changes. Run targeted and project-declared checks appropriate to the reconciled behavior. State whether the Git operation remains in progress and whether continue, commit, or abort still requires authorization.

Aborting can be the safest choice, but it is never forbidden and never automatic: explain its preservation consequences and obtain direction.

Completion criterion: every targeted conflict is either deliberately resolved or blocked on a named decision, unrelated work remains preserved and unstaged, validation results are reported, and the next operation step is explicit.

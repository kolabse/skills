<!-- synchronize-git-repositories:start -->
## Repository synchronization

Use `$synchronize-git-repositories` before analysis, edits, validation,
commits, pushes, deployments, or remote operations. Synchronize every
repository involved in the task with its tracked upstream using safe
fast-forward updates, preserve dirty worktrees, and never resolve divergence
with an automatic stash, reset, rebase, merge, clean, or force-push.
For authorized changes intended for publication, publish a task branch
from the verified current configured base SHA before the first code edit and
track that branch's own remote ref rather than the base branch.
<!-- synchronize-git-repositories:end -->

<!-- verify-before-push:start -->
## Verification before push

Use `$verify-before-push` before pushing protected repositories. Run the
project-declared checks and require current evidence bound to the exact Git
commits and worktrees being pushed. Treat missing, failed, malformed, or stale
evidence as a stop condition for a protected push.
<!-- verify-before-push:end -->

<!-- git-workflow-defaults:start -->
## Default Git workflow conventions

These are fallback conventions only. Existing explicit project or user
instructions, branch mappings, release configuration, and commit rules take
precedence independently for each dimension; never overwrite or reinterpret
them during installation or update.

When branch naming is unspecified, use `feature/<description>` for new work,
`bugfix/<description>` for ordinary defects, `release/<version>` for release
preparation, and `hotfix/<description>` only for an explicitly requested urgent
production fix. A defect alone does not authorize a hotfix or release.

Use the project's configured development role as the base for feature/ and
bugfix/ work and release/ preparation; use its configured production role for
explicit hotfix/ work. Resolve these roles from project rules, never from an
assumed branch name. Do not create develop/main branches, introduce GitFlow
into a trunk-based project, or invent missing development/production mappings.
If the required base or integration target is unknown, ask before branching
or integrating. Naming defaults do not authorize publication or integration.

When commit message conventions are unspecified, use `type: summary` or
`type(scope): summary`, with types `feat`, `fix`, `refactor`, `docs`, `test`,
and `chore`, chosen for the actual change. Preserve explicit project formats,
allowed types, scopes, ticket requirements, and release/versioning rules.
<!-- git-workflow-defaults:end -->

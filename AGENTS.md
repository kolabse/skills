<!-- synchronize-git-repositories:start -->
## Repository synchronization

Use `$synchronize-git-repositories` before analysis, edits, validation,
commits, pushes, deployments, or remote operations. Synchronize every
repository involved in the task with its tracked upstream using safe
fast-forward updates, preserve dirty worktrees, and never resolve divergence
with an automatic stash, reset, rebase, merge, clean, or force-push.
For authorized changes intended for publication, publish a feature branch
from the verified current primary-branch SHA before the first code edit and
track that branch's own remote ref rather than the primary branch.
<!-- synchronize-git-repositories:end -->

<!-- verify-before-push:start -->
## Verification before push

Use `$verify-before-push` before pushing protected repositories. Run the
project-declared checks and require current evidence bound to the exact Git
commits and worktrees being pushed. Treat missing, failed, malformed, or stale
evidence as a stop condition for a protected push.
<!-- verify-before-push:end -->

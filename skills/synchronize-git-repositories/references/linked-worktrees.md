# Temporary task workspaces

Use this pattern when a task spans repositories or an unrelated dirty primary
checkout must remain untouched. Repository roles come from the project's
existing configuration; a task-specific map selects the clean worktrees used
for this run. It does not add configured roles or remove a required gate.

## Create and verify clean anchors

1. Inspect each canonical checkout and fetch its declared tracking remote.
   Record dirty paths, HEAD, upstream, ahead/behind counts, and unfinished Git
   operations. Preserve unrelated changes without stash, reset, or cleanup.
2. Resolve the configured base role and its freshly fetched SHA independently
   for each repository. Do not use an unverified local primary branch as a base.
3. Create a new, clean linked worktree with a dedicated local anchor branch
   tracking that base. This is an explicit task preparation action, not an
   automatic repair of the dirty checkout:

   ```shell
   git -C <canonical-checkout> worktree add --track -b <anchor-branch> <task-workspace>/<role>-anchor <remote>/<base-branch>
   ```

   Choose unused branch names and paths. Confirm each anchor's clean state,
   tracking identity and HEAD equality with the fetched base. The anchor is the
   verification subject; a dirty canonical checkout is not falsely certified
   clean by this procedure.

## Bind repository roles for this run

Keep the mapping private and outside the worktrees. Both verification and
lifecycle accept this version-1 shape:

```json
{
  "version": 1,
  "workspace_root": "/absolute/task-workspace",
  "repositories": {
    "application": "application-anchor",
    "documentation": "documentation-anchor"
  }
}
```

Use the actual configured names, exactly once, and an absolute approved root
appropriate to the host (for example a drive-qualified root on Windows).
Repository paths use forward slashes and stay beneath that root. Unknown,
missing or duplicate roles, path traversal, non-root Git directories, and
descendant symlinks/junctions are rejected. Use a non-Git parent workspace so
verification receipts can remain outside all repository worktrees.

The caller supplies the role-to-repository identity. Inspect each selected
worktree's Git common directory and remote identity against the intended
canonical repository before using the map, especially when a historical
configured path no longer exists. A path boundary alone does not establish
that an arbitrary repository serves the intended role.

The verifier remaps check working directories through their configured
repository owner. Check commands are not arbitrary templates: use
repository-relative arguments or a reviewed repository-owned wrapper.
Hard-coded paths into an old checkout must be corrected in the project's
reviewed check contract; do not silently rewrite arguments or drop checks.

Run the configured verification against the anchors:

```shell
python <verify-skill-root>/scripts/verify_before_push.py run --project-root <configuration-root> --workspace-map <anchor-map.json>
python <verify-skill-root>/scripts/verify_before_push.py gate --project-root <configuration-root> --workspace-map <anchor-map.json> --repository <task-workspace>/application-anchor
```

The map does not rewrite the persistent project configuration. Evidence binds
that configuration, the effective mapping and the actual checked Git states.
Separate mappings have separate receipts. A changed map, configuration, commit,
or checked worktree requires fresh evidence; an identical commit in another
worktree does not make its receipt interchangeable.

## Publish the task branches before editing

After every required anchor gate passes, publish its verified base SHA as the
new task ref, then create the task worktree tracking its own remote ref:

```shell
git -C <anchor-worktree> push <remote> HEAD:refs/heads/<task-branch>
git -C <canonical-checkout> worktree add --track -b <task-branch> <task-workspace>/<role> <remote>/<task-branch>
```

Follow the project's branch naming and publication rules. Confirm local HEAD,
task remote ref and verified base SHA are equal before the first edit. Do not
use the base branch as the task branch's upstream.

Create a task map pointing to the actual task worktrees. Run subsequent
verification with that map; do not reuse an anchor receipt for a task worktree.
If the tracked remote moves, fetch and classify again. Fast-forward only clean,
behind-only worktrees. Preserve divergence or dirty overlap and resolve it
deliberately; rerun evidence after any changed subject.

## Compose gates and lifecycle

A paired verification configuration covers all of its configured repositories.
An additional repository-owned gate remains a separate obligation. Maintain a
small task record listing each required gate, its configuration root, map,
checked commit and receipt. Publication requires every applicable gate to pass;
a paired receipt cannot stand in for the infrastructure repository's own gate.

Use the same role mapping for lifecycle planning where its configured role
names match. Pass `--workspace-map` to bootstrap or plan. New configurations
bootstrapped in this frame explicitly require a map; existing configurations
remain unchanged. The plan retains the mapping for subsequent advance/verify
operations. Rules and references must exist in the selected worktrees, rather
than falling back to an older canonical checkout.

Lifecycle identifiers use lowercase hyphenated names. Its bootstrap normalizes
nonconforming verifier names (for example `App Service` to `app-service`). If
an existing verifier uses such names, use separately keyed maps for the two
contracts, pointing to the same worktrees; do not silently rename the verifier
configuration or omit a role.

This does not invent an integration role for an unconfigured multi-repository
project. Configure the actual integration contract before proceeding. Keep
plans, states and retained evidence outside Git worktrees.

## Retain evidence and clean up deliberately

Record integration identity and verify the source issue's actual disposition.
Before removing any task or anchor worktree, inspect its exact path and Git
state, prove the intended changes are represented in the durable target using
the project's merge/squash policy, and retain the required evidence. Remove
only explicitly identified clean worktrees; do not force-remove dirty ones or
delete the whole parent workspace as a shortcut.

Keep lifecycle plans and referenced receipts available for replay after task
worktree removal. A missing task worktree after approved cleanup is different
from missing or altered retained evidence. Preserve unrelated canonical work,
other tasks, and shared check configurations throughout.

# Task workspace mapping

Use one explicit map when a task runs in sibling or isolated Git worktrees while
the lifecycle configuration stays in its canonical project location:

```json
{
  "version": 1,
  "workspace_root": "/absolute/task-workspace",
  "repositories": {
    "application": "app",
    "documentation": "docs"
  }
}
```

On Windows, `workspace_root` is an absolute Windows path. Repository values use
forward slashes on every platform. The repository keys must exactly equal the
configured names, with no omitted or extra roles. A value of `.` selects the
workspace root itself. Absolute paths, drive paths, UNC paths, backslashes,
empty components, traversal, duplicate resolved roots, and descendant symlinks
or junctions are rejected. The approved root is canonicalized once; selected
repositories must be exact Git roots when inspecting a live workspace.

Pass `--workspace-map <map.json>` to `bootstrap`, `plan`, `rules-status`, and
`configure-rules`. Existing config files and their hashes remain unchanged.
Without a map, existing project-relative behavior remains unchanged.

For a missing lifecycle config, mapped bootstrap normalizes repository names
from the verifier contract before resolving map entries. Original verifier
paths may name absolute or sibling canonical repositories. The generated
portable config contains the mapped relative paths and
`"workspace_map_required": true`; the bootstrap report identifies their
`repository_path_frame` as `workspace-map`. Subsequent commands must supply a
map, or use the map already bound in a plan. Read-only `status` exposes this
requirement. Repeated bootstrap validates a supplied map and preserves the
existing config bytes. Multi-repository bootstrap still blocks until an explicit
lifecycle contract identifies the development integration repository; mapping
does not authorize inferring this role.

The same map works across helpers when configured repository names match.
Lifecycle bootstrap preserves its existing normalization of names to lowercase
hyphenated IDs: for example, verifier role `App Service` becomes lifecycle role
`app-service`. If the verifier uses a different spelling, supply a separate
lifecycle map keyed by the normalized IDs. A role mismatch error lists the
required lifecycle names; bootstrap does not rewrite the verifier contract.

Repository state, managed rule installation, and declared rule/reference files
are inspected only in selected roots. A missing mapped reference cannot fall
back to the canonical checkout or project root. Rule installation writes only
the selected agent's managed block in mapped worktrees and rejects symlinked or
junction-backed rule paths.

Planning embeds the normalized map before calculating `plan_sha256`. Advancement
and deterministic verification recover this bound map without reading its
source JSON file. They recheck path containment and link/junction boundaries,
but allow mapped roots to be absent after cleanup; successful replay does not
depend on deleted worktrees. A changed root alias or an inserted descendant
junction still fails verification.

Plan, state, and retained evidence must stay outside configured and mapped
repositories. In mapped mode the helper also probes the nearest existing
parent of each explicitly named artifact for a containing Git worktree. This
protects a canonical sibling checkout even when a freshly generated portable
config no longer contains its old path. Both lexical and resolved paths are
checked so an artifact junction cannot escape repository exclusion. Only named
parent ancestors are inspected for `.git` markers; Git inspection errors other
than an ordinary non-repository result fail closed. No unrelated directory is
scanned.

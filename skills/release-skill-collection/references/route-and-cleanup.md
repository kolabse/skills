# Release route and cleanup identity contract

Route policy is explicit caller-supplied JSON matching
`../schemas/route-policy.schema.json`; no setup command invents a policy:

```json
{
  "schema_version": 1,
  "repository": "owner/repository",
  "remote": "origin",
  "primary": "main",
  "merge_method": "squash"
}
```

Values in this example are placeholders, not branch or method defaults. Use the
project's declared repository, remote, primary role and integration method.
The three methods are `merge`, `squash`, and `rebase`. Repository availability
flags constrain the explicit choice; they never choose it. Fetch and push URLs
must identify the same destination. URLs are hashed in snapshots, not printed.

`route-plan` observes the GitHub repository, classic protection, paginated
effective branch rules and selected PR. Required linear history from either
protection source excludes merge commits. An unreadable classic protection
endpoint on a protected branch is an unknown constraint, including rules-only
setups whose classic endpoint cannot be inspected: stop for explicit resolution,
not a bypass. A merge queue requires a separately supported workflow. Every
existing required review/check and other GitHub gate still applies; `ready`
means a route can be planned, not that a PR may bypass those gates.

The plan is bound to policy contents, PR head/base, candidate commit/tree,
primary commit/tree, remote refs, and provider observations. Remote inspection
uses `ls-remote`, not fetch. Re-observation detects ref changes during planning;
observations remain point-in-time, not durable authorization. Rerun before
integration if policy, rules, PR, candidate or primary changes. Observe the
actual merged PR and primary commit afterward; never predict a squash/rebase
SHA. Rerun/rebind all five release gates to a changed SHA before creating a tag.
`verify-evidence` continues to require exact current HEAD and does not accept
tree-equivalent evidence for another commit.

For cleanup of an existing release, `release_commit` always means the annotated
tag's peeled commit and remains equal to `audit.commit`. `primary_commit` means
the current integrated local primary. Equal commits use `same-commit`;
different commits require exact equal trees plus complete digest-valid release
evidence, including review, at the tag commit. Supply that evidence file to both
`cleanup-plan` and `cleanup-apply`. This exception authorizes representation
proof for cleanup only, not publication or reuse of candidate evidence at the
integrated SHA. Audit still checks immutable published assets and attestations.

Plans bind the local project, remote destination digest, annotated tag object,
peeled tag commit, primary and every deletion target. Apply fetches, re-observes
and revalidates all identities before deletion. A missing or changed published
tag blocks apply. Local primary must already equal the planned integrated
commit and track the selected remote primary; safely synchronize it first if
behind, and never reset a divergent primary during cleanup. Each branch must
still be merged, tree-identical or patch-equivalent and its remote SHA must
match its local SHA. The audit repository and release URL must match the selected
GitHub remote. The compare-and-delete lease protects a concurrently
updated remote branch. Local deletion also compares the expected old object ID
atomically and refuses branches checked out in any worktree; it does not remove
branch-specific configuration sections, which could belong to concurrent work.
Failed partial deletion is reported explicitly; it is
not rolled back by recreating or force-updating refs.

Reports retain schema version 2 with additive identity fields. Historical
cleanup plans lack sufficient bindings and must be regenerated. No release
tag, audit commit, published artifact or Git history is rewritten.

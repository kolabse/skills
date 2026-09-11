# Cleanup proof and preservation

## Scope and identity

One plan identifies one task branch and one merged review in one repository.
Primary, remote, provider host, repository namespace and review number are
explicit inputs. Fetch and push destinations must agree with the provider
repository. A merged review in another repository or target branch is not proof.
Fork review sources and provider states the helper cannot bind reliably are
retained rather than guessed.

Local and remote task tips, when present, must equal the exact reviewed source
revision. A missing reference can already be retired; a newer reference cannot.
The plan also binds the common Git directory, primary tip, provider observation
and selected worktree state. Re-observation at apply prevents a saved plan from
authorizing a different repository or newer work.

## Integration proof

A provider's merged state is necessary but is not sufficient. The recorded
integration commit must remain reachable from the declared current primary.
Ordinary merge ancestry can prove the source directly. Squash and rebase change
commit identities; use only the helper's supported comparison of represented
changes, anchored to the provider's exact reviewed source and integration.
Ambiguous patch equivalence, missing objects, unresolved conflicts, unsupported
rewrite forms or inconsistent provider fields block deletion. Do not supply a
handwritten `merged: true` document as an alternative to live observation.

Rewritten integration checks preserve whitespace, hunk locations and function
context. A rebase that shifts otherwise equivalent hunks can therefore be
retained as ambiguous. This conservative limit prevents matching the same text
in a different part of a file; it is not a reason to bypass the proof check.

Representation proves that work was integrated, not that it remains current
product behavior after later deliberate changes. It never proves that commits
added to the task branch after merge were published.

## Worktrees and concurrent work

Branch deletion must account for every linked worktree. An unselected checkout
using the branch blocks retirement. Removal requires the exact absolute path,
an explicitly approved containing directory, and a separate acknowledgement
that its task/agent is inactive. Current, main, locked, dirty, untracked, ignored,
symlink/reparse, submodule or ambiguous worktree state is preserved.

The path must resolve inside the approved location. Never recursively delete
a computed path through a second shell or substitute a filesystem delete for
Git's non-forced worktree removal. Ignored content may contain local state worth
keeping even when ordinary Git status is clean.

There is no universal lock against another process beginning work after an
inactivity check. Keep the selected task stopped throughout apply. The helper
rechecks state, uses non-forced Git worktree removal and compares reference tips;
it cannot make concurrent editing safe. New activity invalidates the plan.

## Application and failure

Remote deletion uses an exact old-object lease; local deletion uses an exact
old-object comparison and checks linked worktrees. These are conditional deletes,
not permission to force-push rewritten history. The selected primary must exist,
track its declared remote and be current; missing or divergent state blocks
restoration and dependent actions.

A failure after a successful removal must name both the completed resource and
those retained. Do not hide a denied remote deletion by reporting local success
as full cleanup. Replan from observed remaining resources instead of replaying
the old digest or reconstructing deleted refs.

The implementation adapts the collection's existing release cleanup patterns
(fresh observations, repository binding, conditional ref deletion and partial
results) into an independently installable task executor. It does not import
another installed skill's private Python modules, and it does not change the
release helper's audited-release prerequisites.

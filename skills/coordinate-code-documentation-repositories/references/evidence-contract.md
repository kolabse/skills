# Coordinated-change evidence contract

Use this reference when preparing a plan or deciding whether a paired change is
complete.

## Documentation topics

- `requirement`: why the change exists and which need it addresses.
- `decision`: the chosen behavior or design and material alternatives when relevant.
- `behavior`: externally observable or integration-relevant behavior.
- `operational-impact`: rollout, operation, compatibility, or support impact.
- `validation`: checks actually run and their observed results.
- `limitations`: known constraints, exclusions, or explicitly verified absence of a new limitation.

The project configuration chooses the required subset. Evidence maps each topic
to one or more paths under a configured canonical documentation root. Paths
prove location, not truth; the agent must still compare the claims with the
implemented outcome.

## Traceability

Traceability records use repository roles, not workstation paths. Each record
contains the configured method, a configured repository role,
a public or project-approved reference label, and a SHA-256 evidence digest. Suitable
references include a reviewed change request, a release evidence record, or a
project-owned change identifier.

Do not rewrite already-published commits merely to make each commit mention the
other final hash. Prefer a review or release record that can reference both
immutable commit identities.

The core roles remain `implementation` and `documentation`. Additional roles
are optional to configure but mandatory once declared: for example,
`"operations": {"path": "../operations"}` in `repositories`. All roles must
resolve to separate Git roots. Version-1 two-repository inputs keep their
existing behavior and configuration digest; `migrate` does not add roles.

Verification keeps `implementation_commit` and `documentation_commit`. For
additional roles, supply `additional_commits`, for example
`{"operations": "<40-character-final-commit>"}`. Its keys must match the extra
configured roles exactly. Each extra repository must have a real content
change descended from its planned commit and be clean and published at the
same tracked upstream identity. Include traceability for every role.

## Validation

Validation results state a stable check name, `passed` status, and SHA-256
digest for the retained evidence. A human claim such as “tests passed” without
recoverable or project-approved evidence is insufficient. Use
`$verify-before-push` when the project declares executable local checks.

A validation record may also carry `repository` and `commit` together. The
role must be configured and the commit must match that role's final commit.
When additional roles are configured, require at least one such passed result
for every role, including implementation and documentation. Legacy unbound
results remain accepted for a two-role contract; they cannot satisfy the
multi-repository coverage requirement. A single joint check can be represented
by separate role-bound records referencing the same retained artifact if that
artifact actually covers all those revisions.

## Publication ordering

Optional `publication_order` in the change input is a sequence containing every
configured role exactly once. The plan binds it into its digest. Omit the field
when no ordering constraint is declared; omission does not create an implicit
order. It describes intended publication, not execution history. Keep the actual
pre-publication checkpoint and push observations in the project evidence store
as described in [coordination-reporting.md](coordination-reporting.md).

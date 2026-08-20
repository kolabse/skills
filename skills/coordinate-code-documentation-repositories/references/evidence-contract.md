# Paired-change evidence contract

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
contains the configured method, a role (`implementation` or `documentation`),
a public or project-approved reference label, and a SHA-256 evidence digest. Suitable
references include a reviewed change request, a release evidence record, or a
project-owned change identifier.

Do not rewrite already-published commits merely to make each commit mention the
other final hash. Prefer a review or release record that can reference both
immutable commit identities.

## Validation

Validation results state a stable check name, `passed` status, and SHA-256
digest for the retained evidence. A human claim such as “tests passed” without
recoverable or project-approved evidence is insufficient. Use
`$verify-before-push` when the project declares executable local checks.

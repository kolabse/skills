# GitFlow routes and evidence

Use this reference after a blocker-free route plan exists.

## Standard route

The planned source is the configured development branch for a direct route,
or a preparation branch under `branches.release_prefix` (default `release/`).
A preparation source must contain the currently observed remote development
commit; changing that identity requires a fresh plan and deliberate
reconciliation if necessary. The target is the configured protected production
branch. Execute all common gates followed by
the configured standard-only gates. Publication must use the project's
reviewed path. After merge or equivalent publication, synchronize and record
the remote production identity plus deployment evidence. Review and gate
records must name the actual planned preparation branch/commit, not development
as a substitute. Return stabilization fixes to development through the declared
reviewed path; the standard verifier does not certify that additional step.

Existing version-1 configs without `release_prefix` retain their canonical
digest and direct-development route. An explicit prefix must end in `/` and
must not overlap a hotfix namespace or a persistent branch role.

## Hotfix route

Hotfix intent is always explicit. The source is under the configured namespace
and descends from the planned production identity. Run the same common gates as
a standard release plus the hotfix-only gates. Publish through review to
production, verify production and deployment, then use an approved reviewed
path to return the fix to development.

The reintegration evidence identifies the current remote development commit.
If policy or divergence prevents reintegration, keep the route incomplete and
report the blocker. Do not conceal it by calling production publication the
completion of the hotfix workflow.

## Evidence records

Each configured gate supplies `status: passed`, the planned source commit, and
a SHA-256 digest of retained evidence. Review and deployment records use the
same digest convention. Evidence digests provide tamper detection and identity
binding; they do not turn an unsupported claim into proof. Inspect the actual
provider result when the project requires it.

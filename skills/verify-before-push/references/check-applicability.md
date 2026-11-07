# Applicability and background CI checks

This experimental mode collects CI-only evidence for a version 2 project policy.
It separates the declared role of a check from its observed result. A failed
background check remains failed; it does not turn passing mandatory checks into
a failed check decision. Provider branch protection, review, deployment and
other action gates still apply independently.

Version 1 policies, unversioned GitLab mappings, collector contract v1 and receipt
v4 keep their previous behavior. The new mode uses policy v2, an explicitly
versioned GitLab mapping, collector contract/observation v2, and receipt v5.

## Declare checks once

Use the closed [project-policy-v2 schema](../schemas/project-policy-v2.schema.json).
Retain the existing development, publication, documentation and optional profile
sections. Set `schema_version` to `2` and replace `verification` with, for example:

```json
{
  "execution": "ci",
  "provider": "gitlab",
  "subject": "source_sha",
  "local_execution": "forbidden",
  "reuse_successful_result": true,
  "checks": [
    {
      "id": "infrastructure",
      "blocks": ["merge", "deploy"],
      "scope": {
        "repositories": ["application"],
        "include_paths": ["infra/**"],
        "exclude_paths": [],
        "change_types": ["added", "modified", "deleted", "renamed", "type_changed"]
      }
    },
    {
      "id": "full-application",
      "blocks": [],
      "scope": {
        "repositories": ["application"],
        "include_paths": ["app/**"],
        "exclude_paths": [],
        "change_types": ["added", "modified", "deleted", "renamed", "type_changed"]
      }
    }
  ]
}
```

`blocks` is the stage authority in v2; the v1 `required_at` field is not accepted.
An empty `blocks` list explicitly declares a background check. A check that blocks
`deploy` but not `merge` is deferred for a merge decision, rather than reclassified
as background. A profile's `checks` override replaces the complete array; IDs
remain unique and the resulting effective policy is validated again.

Check IDs match verifier check names. In the existing verifier configuration,
keep enabled catalog entries and their command definitions, then opt in to the
new GitLab mapping:

```json
{
  "version": 2,
  "host": "gitlab.example.test",
  "project_id": 10,
  "remote": "origin",
  "mr_iid": 2,
  "checks": {
    "infrastructure": ["terraform-validate", "ansible-syntax"],
    "full-application": ["full-application-tests"]
  }
}
```

This is the value of `gitlab_ci`, not a replacement for the complete verifier
configuration. It maps every enabled catalog check, including background checks.
Set the catalog's `required` flag to `true` for nonempty `blocks` and `false` for
background checks. Conflicting declarations, disabled required checks, missing
mappings and shared/ambiguous job names are rejected. Command definitions are not
executed by this CI-only route.

Existing mandatory project rules must be reconciled explicitly. This mode does
not rewrite `AGENTS.md`, waive a before-push requirement, or migrate a required
RED gate. Use the diagnostic/migration preview before adoption.

## Derive applicability from the actual change

The consumer binds the local published source SHA, MR source and target project,
current target HEAD, and MR diff references. It verifies the merge base locally
and obtains a complete NUL-delimited Git change inventory. It does not trust a
caller-supplied path list or an incomplete provider diff listing.
Provenance and diff reads ignore local Git object replacements, and gitlink
changes remain included even when local configuration hides submodule changes.

- `*` matches within a path segment; a whole `**` segment matches zero or more
  segments. Paths use `/`. Absolute paths, backslashes, `..`, and unsupported glob
  constructs such as `?` and character classes are rejected.
- A matching repository role and at least one included, nonexcluded change
  endpoint make a check applicable. Renames evaluate both endpoints; deletions
  evaluate the old path. File type changes are explicit.
- Missing objects, shallow history, unknown changes or unproved coverage block
  collection. An empty complete inventory is a proved no-change decision.
- A changed source, target, base, policy, selected profile or check map invalidates
  the previous applicability binding. Observed results cannot edit that decision
  or downgrade a failed mandatory check to background.

## Collect and verify

Ignore the new receipt path and commit/publish the intended configuration first:

```gitignore
.agents/verify-before-push/gitlab-check-evidence.json
```

```sh
python skills/verify-before-push/scripts/verify_before_push.py policy-ci collect --project-root . --repository application --operation merge
python skills/verify-before-push/scripts/verify_before_push.py policy-ci verify --project-root . --repository application --operation merge
```

Select the same explicit profile and evidence path for both commands when
overriding defaults. Filesystem, ignored-output, configuration and Git-metadata
protections from the [v4 consumer](policy-gitlab-ci.md) also apply here. An old or
foreign receipt is not silently upgraded or overwritten.

| Situation | CI-only decision |
| --- | --- |
| Applicable mandatory jobs pass; background job fails | Mandatory checks satisfied; background failure retained. |
| A mandatory job fails, is missing, pending, skipped, canceled or ambiguous | Collection fails; no passing proof. |
| Only background checks apply, with no eligible pipeline yet | `not_required` for mandatory checks; background execution is unobserved. |
| No checks apply and no eligible pipeline exists | `not_required`, with a null pipeline; no pipeline PASS is invented. |
| A background job progresses or retries | Fresh background results are reported without invalidating unchanged mandatory proof. |
| A mandatory job retries or a newer relevant pipeline replaces mandatory proof | The stored proof is stale; recollect. |

The actual global pipeline status stays visible. It may be failed while the
declared mandatory jobs are successful; this does not waive a provider rule
requiring a successful whole pipeline. The consumer makes bounded GET requests,
does not schedule background work, create/retry pipelines, or run local suites.

`collect` saves receipt v5. `verify` rederives local applicability and reobserves
the provider, preserving the stored historical receipt while returning a fresh
sealed report with current background states. It does not claim that historical
background states are current. SHA-256 seals protect consistency, not authenticity.

Action authorization remains `not_granted`. Source review, historical
Ready-at-start, the lifecycle/coordination consumers, and live GitLab acceptance
remain separate work in #152/#150/#151.

# Policy-bound GitLab CI checks

Use this experimental read-only consumer to bind GitLab results to the selected
project policy and local repository. It confirms CI checks only. It does not
authorize push, merge, deployment or task completion, confirm independent source
review, or prove that a pipeline started after the MR became Ready.

The standalone [collector](gitlab-ci.md) remains available for observations.
This consumer derives the collector contract from current files and Git state;
it does not accept caller-supplied policy digests as proof of those files.

## Configuration

Keep the existing verifier configuration and add an explicit `gitlab_ci` block:

```json
{
  "host": "gitlab.example.test",
  "project_id": 10,
  "remote": "origin",
  "mr_iid": 2,
  "checks": {
    "unit-tests": ["unit-tests (3.11)", "unit-tests (3.13)"]
  }
}
```

The mapping must cover every enabled required verifier check with exact,
unambiguous job names. The numeric project ID and MR IID identify the provider
objects; the selected remote must identify that same project. Authentication
belongs to `glab`; never store credentials in the policy, configuration or URL.

The selected `.agents/kolabse/project-policy.json` must be valid and declare
CI execution, provider `gitlab`, subject `source_sha`, a `merge_request` pipeline
and reuse of a successful result. Resolve any conflicts affecting the selected
operation. Profiles are selected explicitly; omitting `--profile` selects the
base policy, not a guessed profile. Expired or inapplicable profiles block.

Initially only operation `merge` and one clean, published repository rooted at
the project directory are supported. Upstream freshness is mandatory. Workspace
maps, forks, merged-results subjects and per-check/background policy semantics
are unsupported. A complete successful pipeline and successful required jobs
are both required in this mode.

Ignore the evidence file before collecting and commit the intended setup:

```gitignore
.agents/verify-before-push/gitlab-ci-evidence.json
```

An evidence path must remain safely inside the project, be ignored by Git and
must not overwrite a policy or configuration file. The consumer does not install
rules, update ignore files, move an MR out of Draft or create pipelines.

## Collect and revalidate

```sh
python skills/verify-before-push/scripts/verify_before_push.py policy-ci collect --project-root . --repository application --operation merge
python skills/verify-before-push/scripts/verify_before_push.py policy-ci verify --project-root . --repository application --operation merge
```

Use the same explicit `--profile NAME` and `--evidence-file RELATIVE_PATH` on both
commands when overriding their defaults. The command returns failure if any
required binding or CI result is unavailable; it never falls back to local
test execution. Provider access consists of bounded GET requests.

Version 4 evidence is separately scoped to `ci-checks-only`. It binds current
configuration, local Git state and remote identity, repository/profile/operation,
effective and source policy digests, the check map, and the complete provider
observation. On verification the consumer derives those bindings again and
recollects provider state. A new pipeline, replaced or failed job, moved MR or
target, or changed policy/configuration invalidates stale evidence. Integrity
hashes detect changes; they do not authenticate a producer or replace live
provider reads.

Successful collection and verification leave source review and historical
Ready-at-start unconfirmed and do not grant action authorization. The ordinary
`run`, `verify` and `gate` commands keep their existing configured-policy guard;
a CI-only receipt cannot satisfy those gates. Legacy local v1/v2 and GitHub v3
receipts retain their existing meaning and format.

This is the first integration slice of #152/#150/#151. A final delivery gate
still needs the readiness/source-review decision, policy-aware lifecycle and
other consumers, explicit per-check stages/background applicability, and guarded
pipeline orchestration. No live GitLab compatibility test is implied by mocked
adapter tests.

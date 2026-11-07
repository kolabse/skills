# GitLab MR CI observations: contract v1

Contract/observation v2 uses a separate
[schema](../schemas/gitlab-ci-contract-v2.schema.json) and
[applicability/background semantics](check-applicability.md). The v1 behavior
below is preserved, including full-snapshot revalidation.

This standalone, dependency-free collector is read-only and opt-in. It does not
implement `verify_before_push.py --source gitlab-ci`. A successful observation
is **not** a v1/v2/v3 verifier receipt, a push/merge gate, policy confirmation,
source review, branch protection permission, deployment authority or completion
of issue #152. Canonical verifier receipts and dispatch remain unchanged.

## Supported boundary

`source_sha` only, same source/target numeric project, opened MR, exact source
head and configured target branch. Non-Draft is checked when requested, but
cannot prove historical Ready-at-start or source review. Contracts requiring
those unconfirmed conditions are rejected before any provider read.

Only MR-associated pipelines with `source=merge_request_event`, exact source
SHA, and the exact `refs/merge-requests/<iid>/head` ref are accepted. This last
condition is a deliberately conservative provenance restriction: installations
that report only a branch name are unsupported, even if the pipeline might in
fact be detached. No pipeline-provided variable is trusted as provenance.
Merged-results/merge-train subjects, forks, child/push/web/API pipelines and
unknown provenance are unsupported. An unrelated historical SHA does not become
a candidate merely because its name or status matches.

All MR-associated pipeline pages and candidate details are read. The latest
matching relevant pipeline is the greatest numeric pipeline ID. This rule never
falls back to an older success when a newer relevant run fails or is active.
All current jobs are fetched without status filtering and with explicit
`include_retried=false`. Each required exact name must occur exactly once and
succeed. Retried historical successes are rejected. Explicit matrix names can
be listed; inferred expansion is unsupported.

`require_pipeline_success=true` requires global success as well as mandatory
jobs. With `false`, optional/background failure or activity may coexist with
passing required jobs; the global status and all current jobs remain visible.
A latest run with missing, duplicate, failed, skipped, canceled or manual
required jobs always blocks. This is per-job collection, not whole-pipeline
success inferred from an arbitrary subset.

MR identity/state/source/diff refs, independently read target HEAD, relevant
pipeline IDs, selected pipeline status/identity and every current job identity,
status and URL must remain equal over two complete observations. A retry that
replaces the accepted job ID invalidates the observation. No GitHub-style
run-attempt number is invented. The collector cannot obtain an atomic GitLab
snapshot: a change after the final read remains possible. Consumers must
recollect immediately at gate use and compare their current contract/policy.

## Contract and command

Use all and only the keys in
[`gitlab-ci-contract.schema.json`](../schemas/gitlab-ci-contract.schema.json).
The Python validator is dependency-free and fails closed, including duplicate
JSON keys, bool-as-integer IDs, malformed hosts/digests and unknown requirements.
Digests bind the caller's effective policy, source snapshot and exact check map;
the collector does not inspect or prove those policy files. Its MR project IDs
do not establish that the local tracked remote is the declared repository.
The experimental [policy-bound consumer](policy-gitlab-ci.md) adds those local
bindings for CI-only evidence. It does not turn standalone observations into
action authorization. A base-policy contract can use `profile: null`; named
profiles still require a nonempty string.

```sh
python skills/verify-before-push/scripts/gitlab_ci.py collect --contract contract.json --output observation.json
```

The output must not already exist and cannot overwrite the contract. The CLI
re-reads the input bytes after collection and blocks changed input. It emits a
`kind=gitlab-ci-observation`, `observation_version=1` document containing the
complete contract/digest, source and target identity, pipeline/jobs/URLs,
observation timestamps, reuse flag, explicit unconfirmed conditions and
unproved bindings. Its SHA-256 `integrity_digest` covers canonical sorted JSON
of all other fields. This detects changes, **not authenticity**. Recomputing a
digest does not establish provider truth; never accept a copied artifact as a
gate without fresh collection and separate policy/remote checks.

The injectable transport implements `get(endpoint) -> decoded JSON`. Production
uses only fixed numeric-project/MR/pipeline GET endpoints and a URL-encoded
branch name:

```text
glab api --method GET --hostname <configured-host> <endpoint>
```

`glab` owns local credentials. There is no token argument, shell expansion,
provider mutation, follow-URL mechanism, implicit retry or credential fallback.
Provider stderr/stdout from failed reads is never exported. HTTPS output URLs
must match the configured host and contain no credentials/query/fragment.
Hosts support GitLab SaaS and self-managed DNS names; custom ports/base API
paths are unsupported. Configure credential scope/trust outside this helper.

Offset pagination requests 100 objects/page, increments explicit `page`, and
ends on a short/empty page, with at most 1000 pages per enumeration. Duplicate
IDs, malformed pages and exhausted limits fail closed. An exactly full last
page causes one extra empty-page read. This does not follow provider-supplied
pagination URLs; credentials cannot be forwarded to another host.

No live GitLab compatibility test was performed. Focused tests use injected
provider responses, mocked `glab`, pagination/race/retry cases and a copied
single-file CLI smoke test. No trigger, wait, retry, bootstrap suppression or
merge coordinator is implemented. API shape restrictions above can reject
legitimate installations; weakening them requires independent provenance proof.

## Design sources

The supplied integration design used the official GitLab APIs and CI docs:
[MR pipelines](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/),
[merged results](https://docs.gitlab.com/ci/pipelines/merged_results_pipelines/),
[MR API](https://docs.gitlab.com/api/merge_requests/),
[pipelines API](https://docs.gitlab.com/api/pipelines/),
[jobs API](https://docs.gitlab.com/api/jobs/) and
[REST pagination](https://docs.gitlab.com/api/rest/#pagination).
The exact-ref restriction and two-pass algorithm are collector policy choices,
not claims that every GitLab installation returns this ref or supplies atomic
snapshot semantics.

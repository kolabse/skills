# report-skill-feedback: candidate acceptance, 2026-09-29

Decision: retain `experimental`. This package fixes a defect found during
candidate acceptance and records evidence; it does not publish or authorize a
release, change maturity metadata, or submit a feedback issue.

## Candidate identity and evidence boundaries

The integrated baseline is `3711b8a3c855a576af2d5e2ab718e72ed3325a6f`
(collection metadata version 1.25.0). The repaired skill candidate is
`04258a3cb55a9cac63a9b5ecee923dee3959cdf2`, with the same metadata version.
This identifies an unreleased development candidate, not the published 1.25.0
artifact. Subsequent documentation/test commits preserve this skill bundle;
their Git checks remain separately bound to their actual commit.

The [baseline manifest](feedback-candidate-20260929/baseline-manifest.json) and
[candidate manifest](feedback-candidate-20260929/candidate-manifest.json) cover
all nine tracked skill files. `skill_digest` binds the raw bytes evaluated and
copied on Windows. `git_content_digest` separately binds canonical committed
blobs, so checkout line endings cannot silently change what an identity means.
Each digest is SHA-256 over compact sorted-key UTF-8 JSON of the ordered file
records, including relative path, size and per-file SHA-256.

All new scenarios used synthetic data outside project repositories. No real
chat, project evidence, credentials, native user settings or external reports
were collected or changed. Raw local records remain local; shared summaries
contain bounded observations and evidence digests, not workstation paths.

## Defect reproduced and repaired

An independently executed approved local-draft scenario failed with
`selected skill name does not match collection metadata` on an unchanged
Windows copy, although both names matched. The frontmatter delimiter accepted
CRLF but the `name:` expression did not consume its carriage return.

[Controlled reproduction](feedback-candidate-20260929/newline-reproduction.json)
accepted LF and rejected CRLF and BOM/CRLF. Regression tests also exposed a
mixed-line-ending duplicate: one `name:` line could be missed, allowing an
ambiguous artifact to be accepted. Both cases failed before the repair.

The parser now recognizes LF and CRLF consistently and rejects duplicate names
with either or mixed endings. It still hashes the original `SKILL.md` bytes;
it does not rewrite or normalize the artifact. Tests cover BOM, quoted names,
unchanged bytes, exact raw SHA-256 and refusal without creating output.

## Observed acceptance

- [Targeted results](feedback-candidate-20260929/targeted-results.json): 25
  feedback helper tests and seven optional-ledger tests passed on the repaired
  candidate. An additional persistent copied-bundle CLI regression was then
  added and passed in the 26-test feedback suite.
- [Copied CLI results](feedback-candidate-20260929/copied-smoke-results.json):
  22 checks across two isolated copies passed, including status, Russian
  preparation under ASCII console encoding, consent refusals, artifact identity,
  deterministic draft/preview, tamper rejection and ledger containment. The
  Codex/Claude labels identify fixture layouts and synthetic input values, not
  proof of native client execution.
- [Independent scenario summary](feedback-candidate-20260929/forward-summary.json):
  separate agents received the candidate and synthetic requests without the
  implementation tests or expected answers. Refusal without collection consent
  succeeded on the baseline. The approved draft failed on the baseline and
  succeeded on the repaired copy without manual repair; preview matched the
  draft and no submission occurred. Agent version was unavailable and recorded
  as such. These are supplementary forward observations, not a completed native
  client acceptance gate.
- Read-only review of the repair and regression tests found no actionable
  defect. Reproducible repository commands are:

  ```shell
  python -m unittest discover -s tests -p "test_report*feedback*.py" -v
  python -m unittest discover -s tests -p test_feedback_session.py -v
  ```

## Applicability and remaining gates

The shared stabilization checklist remains authoritative. `blocked` means the
required evidence is incomplete, including steps intentionally deferred until
release. Successful prior collection CI is supporting evidence, not a substitute
for the repaired candidate's cross-platform results.

| Gate | Applicability | Status and evidence |
| --- | --- | --- |
| Complete candidate identity | Required | Passed: both manifests, commit and raw/canonical digests above. |
| Contract and metadata | Required | Blocked for final promotion: current contract reviewed; final candidate structural/catalog validation and release identity still need binding. |
| Deterministic helpers, consent, privacy, retry and compatibility | Required | Passed for the targeted Windows scenarios above; does not establish agent adherence or external outcomes. |
| Core persistent configuration migration | Not applicable | Core reporting has no persistent configuration. Version-1 inputs remain covered by compatibility tests; this exemption does not cover the optional ledger. |
| Optional session ledger | Required when enabled | Passed targeted schema, status, independent consent, preservation and containment checks. Ledger state never authorizes collection or submission. |
| Required dependency/composition resolution | Not applicable | Catalog `requires` is empty; optional GitHub and ledger behavior are assessed separately. |
| Declared Windows/Linux/macOS coverage | Required | Blocked pending repaired-candidate CI and reconciliation with this bundle identity. Windows targeted/copied results are available. |
| Copied CLI bundle outside repository | Required | Passed local synthetic checks and persistent copied-bundle regression; unrelated fixture settings preserved. |
| Clean native Codex and Claude Code profiles | Required | Blocked: CLI copies and synthetic agent fields do not prove native instruction loading or client behavior. |
| Installation/update preservation | Required | Blocked for final candidate: local fixture preservation is supporting evidence; candidate-specific consumer CI and native profile reconciliation remain. |
| Independent forward acceptance | Required | Blocked as a complete gate: two independently executed synthetic scenarios plus repaired rerun are recorded, but native client/version and external outcome evidence remain incomplete. |
| Required external service | Not applicable | GitHub is an optional integration, not a required dependency. |
| Advertised GitHub submission outcome | Required by this skill assessment | Blocked: no approved current-candidate external submission observed. Local drafts and mocked transport tests do not close this row. Existing reports may be reused only when reporter identity and outcome can be reconciled. |
| Development trigger evaluation | Required | Blocked: corpus presence and helper success are not an evaluation result. |
| Immutable release holdout | Required at release | Blocked until release workflow; locked cases were not inspected or used for tuning. |
| Published archive audit and smoke | Required at release | Blocked until actual versioned artifacts exist. |
| Promotion | Required at release | Deferred: keep `experimental`; set `stable_since` only for the actual release after required gates pass. |

Next: validate the repaired PR on all declared platforms, then reconcile native
client forward evidence and the advertised external-outcome boundary. Obtain
fresh report-specific consent before any real collection, and fresh preview
approval before any external submission. Release preparation owns the immutable
holdout, maturity change and published-artifact audit.

## Release decision, 2026-09-29

The user authorized inclusion of the CRLF repair in 1.26.0 while deferring
native-client and real report acceptance to colleagues after release. This
does not promote the skill: `experimental` remains unchanged. PR #145 passed
all ten GitHub checks and was merged as
`fd618d24132d8b2901a4ad999b0ce1688586e9fc`.

A subsequent Codex CLI 0.147.0 fixture run loaded the selected candidate, but
the execution policy rejected helper execution and report creation; the write
error explicitly identified a read-only sandbox. No report was created or
submitted. The nine candidate files retained their recorded raw hashes. Global
skills remained visible, so this was not a clean-profile acceptance result.
Claude Code acceptance was explicitly deferred by the user. Local raw records
remain outside the repository.

After release, request bounded colleague observations for both native clients,
record the actual installed release and artifact provenance, and distinguish
local preview success from an observed GitHub submission. Obtain separate
report-specific collection and submission approvals. Do not turn existing
historical issues into evidence of an unidentified reporter build.

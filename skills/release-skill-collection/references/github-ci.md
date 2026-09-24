# CI-assisted release checks

Use this mode only when the project's `verify-before-push` configuration
explicitly declares trusted GitHub workflow/job mappings. It is intended for
the final integrated commit: a successful pull-request run or another SHA
with an identical tree cannot substitute for it. Default local verification
and legacy release evidence remain supported.

1. Synchronize the clean primary branch. Run the collection's canonical
   `skills/verify-before-push/scripts/verify_before_push.py run --project-root .
   --source github-ci`. This obtains a version-3 receipt; it does not run the
   mapped tests locally. Missing, incomplete or unsuccessful CI fails closed.
2. Run `release_collection.py check --project-root . --tag vX.Y.Z
   --source github-ci --output-root <empty-directory-outside-repository>`.
   The helper verifies the receipt through GitHub, accepts `collection-full`,
   builds both release archives and verifies their checksums locally. It
   verifies the same receipt again after construction and rejects a changed SHA.
3. Set the `local_release_check` gate's `source` to `github-ci` and embed that
   complete JSON result as `check_report`. Preserve its `report_sha256`; compute
   the enclosing gate and evidence digests as usual. `verify-evidence` checks
   the report's subject, full/build/checksum results and receipt binding and
   revalidates the CI receipt. A bare `source` or `passed` flag is insufficient.
4. Record consumer coverage and supported-platform coverage from the accepted
   CI observations, retaining run IDs, attempts and job identities. Keep the
   independent review and locked model-backed holdout. Tag, publish and audit
   through the usual workflow, including every asset's attestation.

Keep the original receipt and check report with the release evidence. A later
failed or pending rerun invalidates acceptance; an API error cannot authorize
publication. To use the local alternative, explicitly run the ordinary local
checks instead of altering a receipt. The CI-assisted gate currently requires
the checked commit to remain checked out for revalidation; preserve historical
evidence and use a matching clean checkout if a later audit needs that gate.

Report which tests were accepted from CI, which local artifact operations ran,
and elapsed time. Compare against an observed previous full local run; do not
claim a measured saving from an estimate alone. No change to workflows or
required coverage is implied by choosing this source.

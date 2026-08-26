# Unchanged feature bootstrap CI

Use this procedure only for the first remote publication of a feature ref that
still points to the freshly verified base commit. It reduces duplicate CI work;
it never weakens the pipeline required for an implementation commit.

## Configure each repository explicitly

Add `bootstrap_ci` only where the repository's approved SCM adapter implements
one of the supported mechanisms:

```json
{
  "name": "application",
  "path": "application",
  "base_ref": "origin/development",
  "require_clean": true,
  "require_upstream_current": true,
  "bootstrap_ci": {
    "policy": "suppress-unchanged",
    "adapter": "gitlab-scm",
    "mechanism": "gitlab-ci-skip-push-option",
    "fallback": "run-pipeline",
    "evidence_required": true
  }
}
```

The named adapter must declare `scm.suppress-bootstrap-pipeline`. Omitting the
block preserves the conservative behavior: publish normally and require the
resulting pipeline. Never infer a provider from a remote URL.

Before suppression, prove all of the following with fresh observations:

- local `HEAD`, the configured base ref, and its tracked upstream are the same
  immutable commit;
- the worktree is clean and no edit has occurred;
- the remote feature ref does not exist;
- the suppression mechanism is declared by the project and supported by the
  configured adapter.

Do not create an empty commit, alter a commit message, add a tag, or permanently
exclude the feature branch from CI. Those approaches either change the planned
base identity, create unrelated resources, or also suppress later real changes.

## GitLab CI

For `gitlab-ci-skip-push-option`, publish the unchanged ref with Git's push
option rather than modifying the commit:

```shell
git push -o ci.skip <remote> HEAD:refs/heads/<feature-ref>
```

`ci.skip` applies to the branch pipeline for that push. It does not skip merge
request pipelines or external CI/CD integrations. Do not add
`integrations.skip_ci` unless that separate integration is explicitly in scope
and the project contract authorizes suppressing it.

Retain evidence of the resulting remote ref and the provider-observed skipped
branch-pipeline disposition. If the provider or a pipeline execution policy
does not honor the option, wait for the resulting pipeline and require it to
pass; record `bootstrap-ci-fallback-passed` instead of claiming suppression.

## GitHub Actions

GitHub has no equivalent per-push skip option that leaves the shared base commit
unchanged. For `github-actions-unchanged-ref-guard`, keep one lightweight guard
job and make expensive jobs depend on its output. Configure the repository
variable `FEATURE_BASE_BRANCH` to the branch named by this repository's
`base_ref` (for example, `development` for `origin/development`). The guard must
check both that the push created the ref and that its SHA equals the freshly
fetched configured base SHA. Missing configuration or failed observation must
run heavy jobs:

```yaml
jobs:
  bootstrap-classifier:
    runs-on: ubuntu-latest
    outputs:
      run_heavy: ${{ steps.classify.outputs.run_heavy }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - id: classify
        shell: bash
        env:
          BASE_BRANCH: ${{ vars.FEATURE_BASE_BRANCH }}
          REF_CREATED: ${{ github.event.created }}
        run: |
          run_heavy=true
          if [[ -n "${BASE_BRANCH}" ]] \
            && git check-ref-format --branch "${BASE_BRANCH}" >/dev/null \
            && git fetch --no-tags origin \
            "refs/heads/${BASE_BRANCH}:refs/remotes/origin/${BASE_BRANCH}"; then
            base_sha="$(git rev-parse "refs/remotes/origin/${BASE_BRANCH}")"
            if [[ "${REF_CREATED}" == "true" && "${GITHUB_SHA}" == "${base_sha}" ]]; then
              run_heavy=false
            fi
          fi
          echo "run_heavy=${run_heavy}" >> "${GITHUB_OUTPUT}"

  tests:
    needs: bootstrap-classifier
    if: needs.bootstrap-classifier.outputs.run_heavy == 'true'
    # Keep the repository's ordinary test steps here.
```

Every expensive job must depend on the classifier or an equivalent reusable
workflow result. The classifier itself is the observable check run. A later
push has `created != true`, so the implementation pipeline runs even when a
developer changes only documentation or configuration.

If the guard is absent, malformed, stale, or cannot prove the exact base SHA,
publish normally and require the pipeline to pass.

## Record the feature-prepared checkpoint

For every repository with `bootstrap_ci`, set the `ref` subject role to exactly
one observed disposition:

- `bootstrap-ci-suppressed`: the declared mechanism was honored and no heavy
  bootstrap jobs ran;
- `bootstrap-ci-fallback-passed`: suppression was unavailable or not honored,
  and the resulting pipeline completed successfully.

Bind the retained evidence to the remote ref, exact base commit, provider
observation, plan, and configuration digests. A request receipt, intended push
option, skipped local command, or absence of a visible result is not proof.

The later `feature-published` and `feature-pipeline` checkpoints remain bound to
the implementation commit and always require their ordinary full evidence.

Provider references:

- [GitLab push options](https://docs.gitlab.com/topics/git/commit/#push-options)
- [GitHub Actions push events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#push)

---
name: execute-configured-gitflow-releases
description: "Plan, execute, and verify a standard or hotfix release through project-declared GitFlow branch roles and gates. Use when a repository has a persistent development line, protected production line, and an explicit GitFlow release contract. Do not use for trunk-based delivery, an undeclared branch model, generic push verification, or releases of this skill collection."
---

# Execute Configured GitFlow Releases

Use project-declared branch roles and gates as the source of truth. Never infer
`development`, `production`, or hotfix roles from conventional branch names.
Compose with `$synchronize-git-repositories` before planning and
`$verify-before-push` for commit-bound local checks. Use
`$coordinate-code-documentation-repositories` when canonical release
documentation lives in a separate repository.

## Resolve the release contract

1. Inspect project instructions for the release model, protected-branch policy,
   review path, deployment system, and required evidence.
2. If no contract is installed, prepare a version-1 document matching
   [`schemas/config.schema.json`](schemas/config.schema.json) and configure it:

   ```shell
   python <skill-root>/scripts/gitflow_release.py configure \
     --project-root <project-root> --config-source <config.json>
   ```

3. Run `status --json`. Stop if the configured remote or persistent branch
   roles cannot be resolved. A production branch must be declared protected.
4. Use `migrate --json` after updating the skill. Reject unknown newer
   configuration instead of guessing.

The contract declares role names, not preferred literals: projects may use any
valid branch names. Gate names identify evidence supplied by project-owned
checks; this skill does not hard-code CI, hosting, review, or deployment
providers.

Completion criterion: the development and production remote identities,
hotfix namespace, default-route policy, common gates, and route-specific gates
are unambiguous.

## Freeze a route plan

Synchronize the repository and finish the intended source changes before
planning. Prepare a route input matching
[`schemas/route-input.schema.json`](schemas/route-input.schema.json), then run:

```shell
python <skill-root>/scripts/gitflow_release.py plan \
  --project-root <project-root> --input <route-input.json> \
  --output <release-plan.json> --json
```

Keep the plan outside the repository. It binds the source commit, remote
development and production identities, route, target, configuration, and exact
gate set.

Standard route:

- requires the configured development branch as source;
- targets the protected production branch;
- may be selected by an explicit request or a declared default.

Hotfix route:

- always requires explicit hotfix intent;
- requires a source under the configured hotfix namespace;
- verifies that the production identity is an ancestor of the source;
- targets production first and requires later reintegration into development.

Do not use a default to reinterpret an ambiguous request as a hotfix. A dirty,
behind, diverged, detached, or untracked source blocks the plan. An unpublished
source commit is reported and must be published through its authorized route
before review completion.

Completion criterion: the digest-bound plan has no blockers and names one
unambiguous route, source, target, source SHA, remote identities, and gate set.

## Execute only authorized mutations

Read [references/routes-and-evidence.md](references/routes-and-evidence.md)
before executing a route.

1. Run every common and route-specific gate and retain evidence bound to the
   planned source commit. Missing, stale, damaged, failing, or commit-mismatched
   evidence blocks publication.
2. Publish the source and use the project-approved reviewed path to production.
   Never push directly to protected production, bypass review, force-push, or
   rewrite history.
3. Verify the resulting remote production commit and deployment evidence.
4. For a hotfix, create or update the approved reintegration change targeting
   the configured development line. Do not silently merge, rebase, reset, or
   cherry-pick to repair divergence.
5. Obtain authorization at each external mutation boundary. A request to plan,
   verify, push, create a review, merge, deploy, tag, or delete a branch does
   not silently authorize the others.

Do not delete temporary branches until the project-specific cleanup policy can
prove their changes are represented upstream.

## Verify the remote outcome

Prepare a document matching
[`schemas/verification-input.schema.json`](schemas/verification-input.schema.json)
with gate evidence, review evidence, the remote production commit, deployment
evidence, and reintegration evidence. Then run:

```shell
python <skill-root>/scripts/gitflow_release.py verify \
  --project-root <project-root> --plan <release-plan.json> \
  --input <verification-input.json> --json
```

Verification reads local remote-tracking refs but performs no fetch. Synchronize
immediately before it. The result fails unless:

- all and only planned gates passed for the planned source commit;
- review source and target match the route;
- the declared production commit equals the current remote production identity;
- required deployment evidence passed for that production commit;
- a hotfix was reintegrated into the current remote development identity.

An explicitly blocked hotfix reintegration is an honest blocker, not a
successful release result. Report production publication separately from full
hotfix completion.

Completion criterion: standard releases have verified production and
deployment identities; hotfixes additionally have verified reintegration into
development. Otherwise report the exact incomplete state.

## Safety boundaries

- Never infer branch roles, protected-branch behavior, default routes, or gates.
- Never repair dirty or divergent Git state automatically.
- Never mark evidence optional merely because it is unavailable or failing.
- Keep secrets, credentials, internal URLs, customer data, and raw logs out of
  plans and verification inputs.
- The helper writes only explicit configuration and external plan output;
  `status`, `plan`, and `verify` do not alter Git or external systems.

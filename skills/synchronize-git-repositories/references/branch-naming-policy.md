# Branch naming preference and preflight

Use this workflow on first interactive setup and before choosing or publishing
a new task branch. The helper never creates, renames or publishes branches.
Its settings apply to workflows using this skill, not every operation performed
by the application. Existing application and project instructions remain
authoritative. Do not write native global instructions or project naming rules
as a side effect of storing a preference.

## Offer a choice without changing behavior

Run the helper from the actual loaded skill copy:

```shell
python <skill-root>/scripts/branch_policy.py status --agent codex
```

Use `--agent claude-code` for Claude Code. The applications have separate private
settings. `--config-root <directory>` is available for an explicit alternative
or isolated acceptance tests; use the same root for every command in that run.
Do not put private settings or contextual evidence in a committed project file.

When no preference is configured, ask in the conversation which source should
provide names, explaining the detected project rule and examples:

1. Current application default, such as `codex/<description>` when that is the
   actual applicable instruction.
2. This collection: `feature/`, `bugfix/`, `release/`, `hotfix/` by task kind.
3. A specifically identified other skill or collection and its shown templates.
4. The project's own declared naming rule.
5. The user's explicitly supplied global naming rule for this application.

Represent this as two settings: whether to honor an applicable project policy,
and the fallback when no such policy applies. Recommend honoring project policy
and preserving application behavior as the fallback. A mandatory project rule
still applies even when optional project preference is disabled. Preferences
cannot displace higher-priority instructions.

Installation/update `--yes` is not this answer. Without an answer do not save a
preference or insert collection naming defaults. Continue an authorized task
when its actual naming rule is already clear. Third-party marketplace installers
cannot run this conversation; perform it on the first use of this updated skill.
An ordinary subsequent update reads the saved choice and does not ask again.

## Save only the reviewed choice

Prepare a private choice file, for example:

```json
{
  "schema_version": 1,
  "honor_project_policy": true,
  "fallback": "collection"
}
```

First obtain the review plan without writes:

```shell
python <skill-root>/scripts/branch_policy.py configure --agent codex --choice-file <choice.json>
```

Show the proposed source, templates and any previous/new difference to the user.
After their explicit choice, apply that exact plan using its digest:

```shell
python <skill-root>/scripts/branch_policy.py configure --agent codex --choice-file <choice.json> --expected-digest <plan-digest> --confirm
```

Use `fallback: "application"` to return to application defaults. This changes
future skill decisions only. Existing branches and existing project rules remain
untouched. A stale plan requires a fresh preview, not a blind retry.

For `external-skill` or `user-global`, also identify `provider.identity` and
`provider.template_source`, an explicit local JSON source with `schema_version`,
`identity`, `revision` and `templates`. The four template keys are `feature`,
`bugfix`, `release`, `hotfix`, each with a `{slug}` placeholder. Do not invent
templates by mechanically parsing free-form instructions. If the provider has
only prose, read it and ask the user to confirm a faithful structured snapshot
and concrete provenance, or report that automatic configuration is unsupported.

The saved choice retains the accepted snapshot/revision across updates. A new
provider revision is offered for confirmation; it is not silently adopted.
Missing or ambiguous selected providers cannot cause fallback to this collection.

## Resolve from actual instructions

Read applicable instructions and the current status before every new branch.
Create a private context document for `resolve`. Supply:

- `schema_version: 1`, `agent`, `task_kind` and a concrete `slug`;
- `application_rule`: source, priority, instruction evidence, four templates
  and whether that instruction permits user choice, or explicit `null` when
  the application declares no naming rule;
- optional `project_rule` and `explicit_user_rule`, with the same provenance;
- `binding_rule` for the highest-priority mandatory naming constraint, including
  a mandatory project rule; a preference cannot override this constraint;
- `urgent_production_fix: true` only for an explicitly requested urgent
  production fix using `task_kind: "hotfix"`.

Rule priorities are declared by the caller from the actual instruction hierarchy
(smaller numbers mean higher priority). This is not automatic discovery of
instructions. The helper validates the declared resolution; it cannot prove
that the caller read every instruction or that a copied excerpt is authoritative.
Resolve ambiguous applicability before writing the context. Never label a rule
as optional merely to obtain a preferred result.

Keep a binding rule's actual priority: a stronger application default may
explicitly delegate the choice through `allows_user_choice: true`. A stronger
non-delegating rule or an equal-priority conflict makes that binding context
inconsistent. Before any preference is saved, an existing optional project rule
can apply when the application expressly permits this choice. A saved
`honor_project_policy: false` disables that optional override, not mandatory
project instructions. A higher-priority explicit user rule is evaluated by its
actual priority rather than by a lower-priority default's permission flag.

Do not invent application templates merely to fill the context. With
`application_rule: null`, an applicable project/binding/explicit rule or an
accepted concrete fallback can still resolve the name. A fallback selected
without an application rule reports `priority: null` rather than an invented
instruction priority. If no usable rule exists and the user has not chosen a
concrete fallback, resolve that missing information before publication. An
explicit null records observed absence, not permission to ignore instructions.

```shell
python <skill-root>/scripts/branch_policy.py resolve --context <context.json> --output <decision.json>
```

Report the proposed name, task kind, effective source/priority and the reason
for any mismatch with another default. Do not equate an installed plugin's
version with the loaded local skill's version. The result identifies actual
artifact hashes separately from caller-reported collection metadata.

Immediately before the first authorized publication, re-read relevant rules
and run:

```shell
python <skill-root>/scripts/branch_policy.py check --context <context.json> --decision <decision.json> --branch <exact-final-name>
```

Changed instructions require a new context. Changed preference, artifact,
provider observations or proposed name invalidate the old decision. This check
does not replace Git freshness, verification evidence, base-role resolution or
authorization to publish. It does not run as a global Git hook.

## Acceptance boundaries

| Context | Expected result |
| --- | --- |
| Actual app default `codex/`, collection offers `bugfix/`, no choice | Preserve the application default; explain the lower-priority alternative. |
| App permits user choice; user explicitly chooses `bugfix/` | Use the permitted choice and identify its source. |
| Mandatory higher-priority naming rule | Preserve the constraint; reject conflicting explicit choices. |
| Optional project policy and confirmed project override | Apply the project template; otherwise use the accepted fallback. |
| No answer on install/update | No private naming configuration or new project naming defaults. |
| Provider changes without confirmation | Keep the accepted snapshot and show the proposed change. |
| Provider missing, malformed or ambiguous | Report unresolved policy; do not manufacture a verified name. |
| Final branch differs from the saved resolution | Stop before first publication and resolve the actual proposal. |

Test both applications using an isolated config root and a copied skill folder.
Forward acceptance should inspect the instructions actually loaded and the
reported decision, rather than treating helper unit tests as proof of agent
instruction adherence.

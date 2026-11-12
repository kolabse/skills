---
name: develop-with-test-first-evidence
description: "Implement new testable behavior or behavioral fixes with observed red-green evidence or explicitly configured final verification. Select automatically for such implementation work, and when the user requests TDD or project policy requires it. Exclude diagnosis-only requests, after-the-fact coverage, tests-only work, and documentation, formatting, or low-impact edits without behavioral change."
---

# Develop with Test-First Evidence

Use observed red-to-green transitions by default. An explicit project policy may select final verification instead. Announce the selected workflow once before production edits. This skill does not impose a universal new-test requirement on reversible, low-impact edits without behavioral change.

## Select the project workflow

Before implementation, inspect the project's `.agents/kolabse/project-policy.json`
and any explicitly selected profile through the shared `verify-before-push`
runtime. If no policy exists, keep the test-first workflow below. If a policy
is present, follow [policy-aware evidence](references/policy-evidence.md): record
its explicit mode decision before implementation and honor its execution source.
Invalid, unsupported or unavailable policy/runtime inputs cannot select legacy
behavior. An execution prohibition also applies to diagnostics and retries.
Resolve conflicting explicit user requirements or project rules before selecting
a mode; a final-verification declaration does not silently waive an explicit
user request for TDD.

For `final_verification`, preserve coverage and declared final checks; do not
require a RED run or claim test-first chronology. Follow the final-verification
reference instead of the RED/GREEN cycle below. Policy changes and late mode
selection stay explicit in decision history; they do not create earlier evidence.

## Establish the test boundary

Identify the smallest observable behavior, the authoritative focused test command, and the relevant broader suite. Record pre-existing failures before editing. If the harness cannot run, report an incomplete or blocked cycle and the missing prerequisite. Honor actual user or project test-first requirements before continuing implementation; do not invent additional approval requirements or call unexecuted tests successful.

## Run one red-green-refactor cycle

1. Select or add a focused test that expresses the intended behavior. An existing diagnostic test qualifies if its intended-behavior failure was observed before production edits; do not duplicate equivalent coverage.
2. Run it before implementing the behavior. Require a nonzero result caused by the intended missing or incorrect behavior—not syntax, environment, dependency, discovery, or unrelated failures.
3. Before editing production code, preserve the pre-change source identity, focused test revision or digest, argv, exit code, and why the failure demonstrates the behavior gap. Classify only that result as `intended_behavior`. Immediately before the fix, show a short red receipt with the command, exit code, and intended failure.
4. Implement the smallest production change that satisfies the behavior.
5. Rerun the same focused command with unchanged focused assertions to observe green. If those assertions must change before green, establish red for the revised test before changing behavior further; retain comparison proof of the test revision or digest.
6. Refactor only while tests remain green; rerun the focused command if refactoring changes its inputs. Run the relevant broader suite and bind both green results to the unchanged final result. Attach its immutable commit or worktree identity after implementation. Both must exit zero for a successful cycle. Begin another cycle for another behavior.

Do not manufacture red, roll back user work to obtain it, or count harness failures as behavioral evidence. If the test passes before implementation, classify it as characterization or existing coverage and decide whether the requested behavior already exists. Tests added after implementation are after-the-fact coverage; replaying an old revision afterward does not prove test-first chronology. Do not claim TDD evidence from memory.

For durable evidence, read [references/evidence-contract.md](references/evidence-contract.md), prepare a document matching `schemas/evidence.schema.json`, calculate its binding with `scripts/evidence.py digest --input <evidence.json>`, place that value in `evidence_digest`, and run `scripts/evidence.py validate --input <evidence.json>`. Both commands are read-only.

When a shared policy is present, the v1 format check alone is insufficient:
use `scripts/evidence.py accept` with the selected project context and the
policy-bound record described in [policy-aware evidence](references/policy-evidence.md).
This validates recorded observations without executing checks or authorizing
push, merge or lifecycle transitions.

Finish with a concise receipt: red, focused green, broader result, immutable final subject, and evidence reference and digest when produced. Report unavailable checks and failures explicitly, outside any successful evidence record.

Completion criterion for test-first mode: each behavior in the cycle has an intended-behavior red observation followed by unchanged focused assertions passing and final focused and broader green results. Preserve pre-change observation identity separately from the final subject; durable evidence is digest-bound to that final subject. For explicitly configured final verification, report the actual final observations and accepted context separately, without claiming RED/GREEN chronology. Missing or failed checks remain visible.

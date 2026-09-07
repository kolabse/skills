---
name: develop-with-test-first-evidence
description: "Implement new testable behavior or behavioral fixes through recorded red-green-refactor cycles. Select automatically for such implementation work, and when the user requests TDD or project policy requires it. Exclude diagnosis-only requests, after-the-fact coverage, tests-only work, and documentation, formatting, or low-impact edits without behavioral change."
---

# Develop with Test-First Evidence

Make each behavior change traceable to an observed red-to-green transition. Announce this skill once before production edits. It does not impose a universal new-test requirement on reversible, low-impact edits without behavioral change.

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

Finish with a concise receipt: red, focused green, broader result, immutable final subject, and evidence reference and digest when produced. Report unavailable checks and failures explicitly, outside any successful evidence record.

Completion criterion: each behavior in the cycle has an intended-behavior red observation followed by unchanged focused assertions passing and final focused and broader green results. Preserve pre-change observation identity separately from the final subject; durable evidence is digest-bound to that final subject.

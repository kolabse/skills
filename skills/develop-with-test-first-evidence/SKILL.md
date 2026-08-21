---
name: develop-with-test-first-evidence
description: "Implement behavior through test-first red-green-refactor cycles with recorded evidence that the new test failed for the intended reason before it passed. Use when the user requests TDD, test-first development, or project policy mandates it; do not use for ordinary after-the-fact test additions."
---

# Develop with Test-First Evidence

Make each behavior change traceable to an observed red-to-green transition.

## Establish the test boundary

Identify the smallest observable behavior, the authoritative focused test command, and the relevant broader suite. Record pre-existing failures before editing. If the harness cannot run, stop rather than pretending a test-first cycle occurred.

## Run one red-green-refactor cycle

1. Add one focused test that expresses the intended behavior.
2. Run it before implementing the behavior. Require a nonzero result caused by the intended missing or incorrect behavior—not syntax, environment, dependency, or unrelated failures.
3. Record the argv, exit code, concise result, immutable final subject identity, and why the failure demonstrates the intended behavior gap. Classify only that result as `intended_behavior`; environment, setup, dependency, discovery, syntax, and unrelated failures invalidate the red evidence.
4. Implement the smallest production change that satisfies the behavior.
5. Rerun the focused test, then the relevant broader suite. Both must exit zero and be recorded against the same immutable final commit or worktree identity.
6. Refactor only while tests remain green. Begin another cycle for another behavior.

Do not break unrelated code to manufacture red evidence. If the new test passes before implementation, classify it as characterization or existing coverage and decide whether the requested behavior already exists. Do not claim TDD evidence from memory.

For durable evidence, read [references/evidence-contract.md](references/evidence-contract.md), prepare a document matching `schemas/evidence.schema.json`, calculate its binding with `scripts/evidence.py digest --input <evidence.json>`, place that value in `evidence_digest`, and run `scripts/evidence.py validate --input <evidence.json>`. Both commands are read-only.

Completion criterion: every changed behavior has an intended-behavior red observation followed by focused and broader green results, the evidence is digest-bound to an immutable final subject, and pre-existing or remaining failures are reported outside the successful evidence record.

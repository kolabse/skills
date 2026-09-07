---
name: diagnose-software-defects
description: "Investigate reported software errors, unexpected behavior, regressions, crashes, or flaky tests to explain their cause, including requests to fix a problem whose cause is unknown. Use for direct failure reports as well as explicit diagnosis requests; exclude implementing an established fix, copyediting error messages, and reviewing a PR."
---

# Diagnose Software Defects

Separate observations from hypotheses and diagnosis from implementation. Announce this skill once when it activates and give compact observations as the investigation progresses: symptom and expectation, reproduction, hypotheses and supporting or contradicting evidence, then cause or uncertainty.

## Bound the symptom

Restate the observed behavior, expected behavior, environment, relevant versions, and success condition. Preserve failing artifacts and identify evidence that is unavailable or potentially stale.

## Investigate causality

1. Reproduce the symptom with the smallest safe case, or document a bounded non-reproduction.
2. Localize the failure using logs, tests, state comparisons, configuration, and history relevant to the symptom.
3. Form multiple plausible hypotheses when evidence permits and test them with reversible or read-only probes.
4. Trace the strongest supported causal chain and affected scope. Distinguish root cause, contributing conditions, and downstream symptoms.

Do not mutate production during diagnosis, remove evidence, reveal credentials, or apply a speculative fix. Do not claim causation from correlation. If reproduction is impossible, report what was attempted, confidence, and missing evidence; never invent a cause or an execution result.

## Report the diagnosis

For diagnosis-only requests, provide candidate fixes and a verification plan without implementation. A request to fix the reported problem already authorizes correction after diagnosis: continue within that scope without asking for redundant permission. For a testable behavioral correction, use the available test-first workflow and preserve a diagnostic failing test as its red observation when suitable.

Report the supported cause or remaining uncertainty, evidence and affected scope, and any correction made. After an authorized correction, rerun the original reproduction and relevant checks and report their actual results, including remaining failures. If blocked from running them, say so rather than claiming resolution.

Completion criterion: the result explains what is known, how it was tested, what remains uncertain, and what observation would verify resolution.

---
name: diagnose-software-defects
description: "Investigate a software failure, regression, crash, incorrect result, or flaky test to produce an evidence-backed causal explanation or ranked hypotheses. Use when the requested outcome is diagnosis; do not use when the user only asks to implement a known fix."
---

# Diagnose Software Defects

Separate observations from hypotheses and diagnosis from implementation.

## Bound the symptom

Restate the observed behavior, expected behavior, environment, relevant versions, and success condition. Preserve failing artifacts and identify evidence that is unavailable or potentially stale.

## Investigate causality

1. Reproduce the symptom with the smallest safe case, or document a bounded non-reproduction.
2. Localize the failure using logs, tests, state comparisons, configuration, and history relevant to the symptom.
3. Form multiple plausible hypotheses when evidence permits and test them with reversible or read-only probes.
4. Trace the strongest supported causal chain and affected scope. Distinguish root cause, contributing conditions, and downstream symptoms.

Do not mutate production, remove evidence, reveal credentials, or apply a speculative fix. Do not claim causation from correlation. If reproduction is impossible, label confidence and missing evidence.

## Report the diagnosis

Provide the reproduction or non-reproduction result, evidence, root cause or ranked hypotheses, blast radius, and a verification plan for candidate fixes. Implement only when the request separately authorizes a fix.

Completion criterion: the result explains what is known, how it was tested, what remains uncertain, and what observation would verify resolution.

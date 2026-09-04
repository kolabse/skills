# Stabilization checklist

Use this checklist before changing `discover-skill-candidates` from
experimental to stable.

Complete the collection-wide
[experimental skill stabilization checklist](../../../docs/skill-stabilization-checklist.md)
as well as the skill-specific gates below. These gates add candidate-intake and
portability coverage; they do not replace any shared gate.

## Deterministic acceptance

Require the full unit suite to prove bounded rule and opt-in evidence discovery,
symlink and size limits, Git provenance, observation confirmation, chat and
handoff sanitization, observation-only promotion limits, secret rejection,
deterministic scoring, catalog deduplication, contribution digest binding,
portability filtering, and atomic output outside the analyzed project.

Exercise a fixture that represents a contributor repository separate from this
collection. Export a recommended or investigate candidate, copy only the
portable package to a clean maintainer environment, and validate it without
access to the contributor rules or scored report.

## Independent forward test

Use at least two repositories whose rules were not used to design the scorer.
For each repository:

1. Ask an independent agent to inventory and rank candidates without revealing
   expected candidates.
2. Review false positives, false negatives, overlap decisions, and rejected
   policy-only rules.
3. Export one user-approved package and submit it through the public candidate
   intake issue form.
4. Validate the attachment in a clean checkout and record only sanitized
   package digests, classifications, and pass/fail outcomes.
5. Confirm that the maintainer can hand the validated brief to
   `$skill-creator` without receiving raw rules, paths, URLs, or private data.

Do not tune the skill from the active release holdout. Keep forward-test
prompts and results with review evidence rather than embedding contributor
rules in the repository.

## Promotion gate

Keep the skill experimental until deterministic acceptance passes on every
supported platform, two independent forward tests pass, the public intake path
has accepted and independently validated a real package, copied-install smoke
passes, and a new immutable release holdout covers the stable trigger surface.

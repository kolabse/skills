# Candidate rubric

Use this reference while converting rule blocks into candidate input for the
deterministic scorer.

## Qualification questions

A useful skill candidate normally answers yes to most of these questions:

1. Does the rule describe an outcome that will recur across tasks or a family
   of projects?
2. Does reaching that outcome require at least two ordered decisions or steps?
3. Would a future agent otherwise need to rediscover tool usage, validation,
   failure handling, or a safety boundary?
4. Can the workflow expose a clear completion criterion?
5. Can important behavior be checked with fixtures, schemas, simulations, or
   deterministic helper scripts?
6. Is the behavior stable enough to maintain independently from one project's
   code?

## Disqualifiers

Use one or more exact values in `disqualifiers` when applicable:

- `existing-skill`: an existing skill already owns the outcome;
- `policy-only`: the block states organization, security, or access policy;
- `single-command`: the block is only a command or trivial reminder;
- `project-specific`: the behavior depends on one repository's private names,
  layout, or business rules;
- `sensitive`: the workflow would require stored secrets or private payloads;
- `volatile`: the procedure changes too frequently for a reusable contract;
- `not-testable`: no honest completion criterion or validation surface exists.

Do not disguise a disqualifier to increase a score. Prefer extending an
existing skill when the missing behavior shares its trigger and safety model.
Prefer composition when existing skills already own the individual steps.

## Scored evidence

The helper derives a maximum score of 20:

- distinct source blocks: 1-3;
- portability scope: 0-3;
- workflow depth: 0-3;
- trigger clarity: 1-2;
- stability: 0-2;
- deterministic automation opportunity: 0-2;
- testability: 1-2;
- explicit safety boundaries: 1-2;
- reusable script/reference resources: 0-1.

Existing-skill similarity applies a penalty. Any disqualifier or duplicate
candidate forces `reject` regardless of the raw score.

- `recommended`: 13 or more after penalties;
- `investigate`: 9-12;
- `reject`: 8 or less, any disqualifier, or duplicate/identical existing skill.

Scores organize review; they do not prove product value or authorization to
create a skill.

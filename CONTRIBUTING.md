# Contributing skills

This repository is the canonical home for reusable kolabse skills. Keep each
skill focused, portable, attributable, and independently installable.

## Before adding a skill

1. Identify the canonical source. Decide whether this repository will own the
   skill or mirror another source.
2. Establish the right to redistribute every copied instruction, script,
   reference, and asset. Original contributions are accepted under the
   repository's Apache-2.0 license unless explicitly marked otherwise. Preserve
   third-party license files, copyright notices, attribution, and modification
   notices; record their SPDX expression in the catalog. Do not publish
   third-party material with an unresolved license.
3. Search existing descriptions for overlapping triggers. Extend an existing
   skill when the workflow has the same purpose; add a new skill when it has an
   independently useful trigger and completion criterion.
4. Choose a lowercase, verb-led, hyphenated name of at most 63 characters.

Completion criterion: ownership, provenance, license, scope, and skill name are
known before files are copied.

## Add or migrate the skill

1. Synchronize both source and destination repositories without overwriting
   local work.
2. Create `skills/<skill-name>/SKILL.md`. Keep only `name` and `description` in
   its YAML frontmatter, and make the folder name match `name`.
3. Put deterministic helpers in `scripts/`, agent-facing detail in
   `references/`, output material in `assets/`, and optional UI metadata in
   `agents/openai.yaml`. Keep project configuration outside the skill folder.
4. Write imperative steps with checkable completion criteria. Keep the body
   below 500 lines; disclose branch-specific detail through direct references.
5. Add one entry to `skill-catalog.json`:
   - `name` and repository-relative `path`;
   - `status`: `experimental`, `stable`, or `deprecated`;
   - GitHub handles in `maintainers`;
   - supported `platforms`;
   - SPDX expression in `license`;
   - provenance kind, source, previous names, and canonical repository.
6. Add the skill to the README catalog with its purpose, installation notes,
   and required first-run action.
7. Add tests for deterministic scripts and realistic prompts that should and
   should not trigger the skill. Store at least three positive and three nearby
   negative cases in `evals/<skill-name>.json`, and reference that file from
   `skill-catalog.json` as `trigger_evals`.

For a migrated skill, preserve its history in the catalog even after this
repository becomes canonical. For a vendored skill, record an immutable source
revision, keep its license and notices in the skill folder, and keep upstream
changes separate from local patches. Confirm license compatibility before
combining third-party content with Apache-2.0 content.

Completion criterion: a reader can determine where the skill came from, who
owns it, how it is licensed, where it runs, and how to validate it.

## Validate the change

Run:

```shell
python scripts/validate_skills.py
python -m unittest discover -s tests -v
npx skills@1.5.22 add . --list
```

Exercise the trigger corpus against an actual agent, including the skill's
first-run path. Structural CI checks keep the corpus complete, but do not
substitute for observing model invocation. Include the prompts and observed
result in the pull request.

For collection-wide trigger evaluation, prepare a blind suite and score the
selector observations:

```shell
python scripts/trigger_evals.py prepare --output .trigger-evals/suite.json
python scripts/trigger_evals.py score \
  --predictions .trigger-evals/predictions.json \
  --json-output .trigger-evals/report.json \
  --markdown-output .trigger-evals/report.md
```

Selectors may choose multiple skills or none. Do not expose the source eval
files, expected labels, author reasons, suspected failures, or prior reports to
the selector. Record provider/model identity in the prediction metadata, keep
raw predictions with the review evidence, and inspect each false positive and
false negative before changing a description. A higher score is not sufficient
reason to broaden a trigger when that would make nearby workflows ambiguous.

Completion criterion: every command passes on each supported operating system,
and the pull request checklist contains evidence for the affected skill.

## Protect the release chain

- Pin every external GitHub Action to a full commit SHA and retain its release
  version in a comment. Let Dependabot propose reviewed SHA updates.
- Grant each workflow only its required `GITHUB_TOKEN` permissions.
- Build release archives through `scripts/build_release.py`; verify
  `SHA256SUMS` before uploading assets.
- Publish GitHub artifact attestations for every release asset and verify them
  with `gh attestation verify <artifact> --repo kolabse/skills`.
- Never replace an existing release asset. A repeated workflow run must verify
  that the published bytes are identical or fail.
- Keep version tags immutable. Publish a correction as a new version instead
  of moving an existing tag or replacing its source commit.

Completion criterion: the tag resolves to the reviewed commit, the uploaded
assets match `SHA256SUMS`, and workflow dependencies are immutable references.

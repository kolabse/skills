---
name: synchronize-team-skills
description: "Declare a shared kolabse skill set in project documentation and compare or align project installations for Codex and Claude Code. Use when a team wants reproducible project skills, onboarding parity, version-drift diagnosis, or installation from a reviewed team manifest. Do not use to synchronize user secrets, global preferences, or arbitrary third-party tools."
---

# Synchronize Team Skills

Treat the reviewed project document as the team requirement and local skill
folders as observed state. Never infer team policy from one workstation without
an explicit request to change the document.

## Resolve the team document

1. Read project instructions and documentation links. Prefer an already
   declared `team-agent-skills.md`.
2. When no path is declared, run the read-only status helper. It accepts one
   unambiguous existing `docs`, `documentation`, or `doc` directory:

   ```shell
   python <skill-root>/scripts/team_skills.py status \
     --project-root <project-root> --json
   ```

3. If documentation is missing, ambiguous, or kept in another repository, ask
   the user for the existing documentation root. Do not create a documentation
   location by convention.
4. Parse only the managed JSON block described by
   [`schemas/team-skills.schema.json`](schemas/team-skills.schema.json). Treat
   surrounding prose as human documentation, not executable configuration.

Completion criterion: the exact reviewed document and its manifest digest are
known without scanning unrelated repositories.

## Inspect before changing anything

Use `status` to compare every declared skill with the project-scoped Codex and
Claude Code layouts. Report:

- missing, current, outdated, newer-than-required, and unverified installations;
- the observed collection version and provenance metadata;
- additional verified kolabse skills, which remain preserved;
- project copies that can shadow a newer global or plugin installation.

Do not equate installation with availability in an already open agent task.
Recommend a new task after an installation changes. Do not inspect or copy
tokens, user configuration, plugin authentication, or global preferences.

Completion criterion: the report separates documented requirements, observed
project installations, preserved extras, and state that cannot be verified.

## Create or revise the team requirement

Create a first document only after the documentation root and desired set are
approved:

```shell
python <skill-root>/scripts/team_skills.py configure \
  --project-root <project-root> \
  --documentation-root <documentation-root> \
  --collection-version <version> \
  --agent codex --agent claude-code \
  --skill synchronize-team-skills \
  --skill synchronize-git-repositories \
  --skill <another-skill> --json
```

The helper always requires `synchronize-team-skills` and
`synchronize-git-repositories` in the manifest so a new team member receives
the bootstrap and its freshness dependency together. It fixes `source` to
`kolabse/skills`, project scope, and `extras_policy: preserve`. It preserves
unmanaged document content and refuses malformed or nested managed markers.

Changing the documented set is a project documentation change. Review and
publish it through the project's normal Git workflow. Never silently rewrite
the team set from local installations; prepare a proposed list for review when
the user asks to derive policy from one workstation.

Completion criterion: the human-readable document and managed manifest agree,
contain no machine paths or secrets, and are ready for ordinary code review.

## Plan and apply alignment

1. Synchronize the documentation repository with
   `$synchronize-git-repositories` in Codex or
   `/synchronize-git-repositories` in Claude Code.
2. Build a read-only, digest-bound plan:

   ```shell
   python <skill-root>/scripts/team_skills.py plan \
     --project-root <project-root> --json
   ```

3. Review missing or outdated skills, unverified-name collisions, agent
   targets, preserved extras, pinned collection version, and exact installer
   argument arrays.
4. Apply only after explicit approval, using the plan's manifest digest:

   ```shell
   python <skill-root>/scripts/team_skills.py apply \
     --project-root <project-root> \
     --expected-manifest-sha256 <plan-value> \
     --expected-plan-sha256 <plan-value> --yes --json
   ```

5. Stop if the document or observed installation plan changed after review, a
   declared path has unverified provenance, `npx` is unavailable, or an
   installer fails. Never delete an extra skill, downgrade a newer project copy,
   change global installations, or force an overwrite.
6. Re-run `status`. Report observable remaining drift and ask the user to start
   a new agent task when files changed.

The helper invokes the pinned `skills` CLI without a shell and installs only
the declared names from the pinned collection release into each declared
project agent layout. Skill configuration remains outside installed folders
and is not copied into the document.

Completion criterion: every declared project installation is verified at the
documented collection version, extras remain intact, and no success is claimed
from installer exit status alone.

# Git workflow defaults

These are fallback conventions, not permission to replace a project's branch
model. Resolve applicable user instructions, repository rules (including linked
contribution guides), and configured lifecycle/release contracts first. Explicit
policy wins independently for each prefix, base/target role, and commit format.
If sources disagree, stop and resolve the conflict; do not silently rewrite
configuration or treat a tool's generic `codex/` suggestion as project policy.

## Branch selection before the first edit

| Task | Default prefix | Base role | Completion target |
| --- | --- | --- | --- |
| New feature or ordinary task | `feature/` | development | development |
| Bug found during development | `bugfix/` | development | development |
| Release preparation and stabilization | `release/` | development | production, then return release fixes to development |
| Explicit urgent production repair | `hotfix/` | production | production, then development |

Use a short task slug, optionally including the issue number, for example
`feature/123-user-auth` or `bugfix/login-crash`. A documentation, test, or
maintenance task can use `feature/` without being a `feat` commit. Branch kind
and commit type are independent; never infer an urgent production operation
from the word "fix" alone.

`develop` and `main` are examples of development and production roles, not
names to impose. Reuse declared `dev`, `development`, `production`, or other
roles. For a trunk-based project use the existing primary base/target for
ordinary work; do not create a second persistent branch. If GitFlow roles are
unknown, ask before creating or publishing a branch. Existing direct
development-to-production release contracts remain valid overrides.

Publish the unchanged verified base SHA under the selected task branch before
editing and track that branch's own remote ref. Use only declared bootstrap-CI
suppression; do not add skip-CI commit messages, tags, or empty commits. Keep
review, push verification, deployment evidence, and proved cleanup gates.

## Commit messages

Unless the project declares another format, write `type: summary` or
`type(scope): summary`, with a concise description of the actual change:

- `feat`: new user-facing functionality;
- `fix`: corrected behavior;
- `refactor`: internal restructuring without changing behavior;
- `docs`: documentation;
- `test`: tests;
- `chore`: maintenance, dependencies, build or tooling configuration.

An optional `!` may mark a breaking change; describe the incompatibility in the
body. Preserve explicit project extensions or alternate formats. Check the
proposed commit and squash/MR title before publication; never rewrite existing
history just to make old messages match these defaults. The configuration
helper installs agent rules, not Git hooks or a server-side commit validator.

## Installation and update

The synchronization helper's `bootstrap` plans without writes and applies only
with `--apply --yes`. `configure` is its explicit setup alternative. Both are
idempotent and preserve custom managed blocks and unrelated rules. The separate
`git-workflow-defaults` block is explicitly conditional, so an existing project
convention remains effective without unreliable parsing of free-form prose.

Project-scoped managed updates bootstrap the installed synchronization helper
when synchronization, lifecycle, or GitFlow release skills are selected.
Direct third-party installers cannot run collection post-install hooks: the
installing agent must invoke bootstrap. Global/plugin installations have no
project scope; perform setup on first use in each authorized project instead
of scanning or changing unrelated projects. Report defaults added, custom rules
preserved, and any blocked setup. Re-read rules before choosing each branch.

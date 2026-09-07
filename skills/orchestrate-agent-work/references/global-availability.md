# Global availability and invocation

## Install once, use across projects

Install or activate the collection globally through the agent's supported
installation route. Follow the collection's
[installation instructions](https://github.com/kolabse/skills#install-skills).
Do not require a project manifest, a project-local skill copy, an `AGENTS.md`
activation entry, or a configuration bootstrap merely to expose this skill.
Its configuration contract is stateless (`format: none`).

In a new task, a request such as “Use two subagents to inspect the API and tests
independently, then reconcile their findings” qualifies without naming the
skill. A request with many steps but no authorization to delegate does not.
Codex metadata explicitly permits implicit invocation; other agents use their
native skill-selection mechanism and the shared description. Eligibility is
not a guarantee that every model run will select the skill.

## Check the effective source

1. Open a fresh task in a project without a local copy or activation entry.
2. Inspect the agent's effective skill inventory. Record the skill's resolved
   name (which may have a plugin namespace), path, scope, and enabled state.
   If the agent exposes no inventory, report discovery as unverified.
3. Inspect `collection-metadata.json` beside that exact `SKILL.md` for the
   declared collection, source, and version. Compare the instruction digest
   when versions match but contents may differ. Metadata alone does not prove
   that the agent loaded those instructions.
4. Submit a bounded request explicitly requiring subagents, without naming the
   skill. Confirm that the agent selects and reads this workflow before
   coordinating assignments. Retain the observed path and the outcome; file
   presence or a list entry alone is not invocation evidence.

For multiple copies, use the collection manager's bounded source inspection
from a collection checkout, supplying only the roots being investigated:

```shell
python scripts/manage_installed_skills.py doctor --project-path <project-root> --agent codex --inspect-sources --skill-root <user-skills-root> --plugin-root <selected-plugin-root> --json
```

Omit an unused source option; use `--agent claude-code` for that consumer. The
report distinguishes paths, declared versions, instruction hashes, and copy
conflicts. It cannot infer the effective copy from directory order. Match its
paths against the agent observation. Never silently copy, delete, or update a
skill to resolve an ambiguous source.

## Respect explicit disable settings

An applicable project instruction may explicitly prohibit this workflow or
subagents. Follow it according to the instruction hierarchy, even when the
global skill remains visible. Do not add a collection-specific enable/disable
configuration file: there is no project activation contract to maintain.

Where the agent supports native per-skill disabling, use its documented
settings and verify their effective behavior in a fresh task. For local Codex
skills, the documented user configuration uses an exact `SKILL.md` path:

```toml
[[skills.config]]
path = "/absolute/path/to/orchestrate-agent-work/SKILL.md"
enabled = false
```

This example belongs in the user's Codex configuration; it is not a portable
project setting. Project config support, trust requirements, and plugin
controls depend on the host. Do not assume that placing the same setting in a
project file disables a plugin or a global skill. Check the host's effective
inventory and a fresh invocation; report an ignored or unsupported setting
instead of claiming suppression. Do not change trust or user settings merely
to test discovery.

See the host documentation for [Codex skill controls](https://developers.openai.com/codex/skills)
and [configuration layers](https://developers.openai.com/codex/config-basic).

## Evidence boundaries

The collection's global consumer smoke installs exact copied payloads into a
temporary user home for both Codex and Claude Code, with an empty consumer
project. It verifies file equality and the absence of project activation
artifacts. It does not start an agent or prove model selection. Local-source
global installation with the pinned installer creates no global lock file;
payload comparison supplies the smoke check's integrity evidence.

Record native inventory and invocation observations separately, naming the
agent version, installation route, selected source, and any disable mechanism
actually tested. If a host lacks subagent tools, report that capability limit
without inventing successful delegated work.

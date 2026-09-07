# Test-first evidence contract

Version 1 contains exactly `schema_version`, `behavior`, `subject`, `red`, `green`, and `evidence_digest`. Commands are argv arrays, never shell strings.

`subject` binds evidence to the immutable final result. A commit identity is a lowercase 40- or 64-character object ID. An uncommitted worktree identity is `sha256:<hex>`, calculated from a project-appropriate deterministic manifest of every relevant tracked and untracked input. The validator checks its shape but cannot reconstruct a project-specific manifest.

Capture the pre-change source identity and focused test revision or digest with the red observation before production edits. Retain these and command/assertion comparison proof in a companion observation log, outside the strict version 1 envelope. Attach `subject` only after implementation and final validation; it identifies the result, not the source on which red ran. An old-revision replay performed afterward cannot establish that testing preceded implementation.

`red` must be nonzero with `failure_class: intended_behavior`; its reason explains how the observation demonstrates the missing requirement. Environment, setup, dependency, discovery, syntax, and unrelated failures are invalid. `green.focused` and `green.broader` must both exit zero against the final subject.

The binding is SHA-256 over UTF-8 JSON after removing `evidence_digest` and serializing with sorted keys, no insignificant whitespace, and unescaped Unicode:

```shell
python scripts/evidence.py digest --input <evidence.json>
python scripts/evidence.py validate --input <evidence.json>
```

Both commands are read-only. `digest` prints the expected value; `validate` checks exact structure and binding. Neither proves chronology, unchanged tests or assertions, narrative truth, or subject provenance. Retain actual observations and comparison proof for those claims. Failed or unavailable focused or broader checks belong in an incomplete-cycle report, not a successful version 1 record.

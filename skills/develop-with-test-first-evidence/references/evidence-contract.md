# Test-first evidence contract

Version 1 contains exactly `schema_version`, `behavior`, `subject`, `red`, `green`, and `evidence_digest`. Commands are argv arrays, never shell strings.

`subject` binds evidence to the immutable final result. A commit identity is a lowercase 40- or 64-character object ID. An uncommitted worktree identity is `sha256:<hex>`, calculated from a project-appropriate deterministic manifest of every relevant tracked and untracked input. The validator checks its shape but cannot reconstruct a project-specific manifest.

`red` must be nonzero with `failure_class: intended_behavior`; its reason explains how the observation demonstrates the missing requirement. Environment, setup, dependency, discovery, syntax, and unrelated failures are invalid. `green.focused` and `green.broader` must both exit zero against the final subject.

The binding is SHA-256 over UTF-8 JSON after removing `evidence_digest` and serializing with sorted keys, no insignificant whitespace, and unescaped Unicode:

```shell
python scripts/evidence.py digest --input <evidence.json>
python scripts/evidence.py validate --input <evidence.json>
```

Both commands are read-only. `digest` prints the expected value; `validate` checks exact structure and binding. Neither proves the narrative or subject provenance.

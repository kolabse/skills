---
name: maintain-project-digest
description: "Create and maintain a project documentation digest of completed user-visible changes, grouped by category under today's date. Use when the user asks for a digest, daily change summary, or nontechnical record of what changed for users. Do not use for technical work logs, release notes for a specific release, commit history, or planned work."
---

# Maintain Project Digest

Maintain one concise, user-facing digest in the project's documentation. Treat
it as the final daily view of completed product changes, not as an engineering
activity log.

## Resolve the digest location

1. Inspect project instructions and existing documentation links first.
2. Run the read-only locator when no path is declared:

   ```shell
   python <skill-root>/scripts/project_digest.py status --project-root <project-root> --json
   ```

3. Use an existing unambiguous `docs`, `documentation`, or `doc` directory.
   Never create or choose a documentation location merely by convention.
4. If no location is found, several locations are plausible, or documentation
   is kept in another repository, ask which directory or repository to use.
   An explicitly approved documentation directory may be outside the code
   repository. It must already exist.
5. Use `project-digest.md` unless the project already declares another digest
   filename.

Completion criterion: the documentation root and exact digest path are known
without guessing across repositories.

## Select changes

Include only completed, evidence-backed changes that affect users, operators,
administrators, or people integrating with the system. Use the current task,
reviewed diffs, accepted changes, and available project records as evidence.
Do not turn plans, experiments, failed attempts, internal refactoring without
an observable effect, or unverified claims into digest entries.

Choose one category per entry:

- `new` — **Доработки**: a new user-visible capability;
- `improved` — **Улучшения**: a better existing experience, including notable
  performance or accessibility improvements;
- `fixed` — **Исправления**: behavior that now works as intended;
- `security` — **Безопасность**: a user-relevant protection or risk reduction,
  without disclosing exploitable detail;
- `docs` — **Документация**: clearer or newly available user documentation;
- `changed` — **Важные изменения**: changed behavior, compatibility,
  deprecation, removal, or a new limitation users must account for.

Omit empty categories. Prefer **Важные изменения** over hiding a breaking or
restrictive change inside an improvement.

Write each entry as one short completed outcome in language a product user can
understand. Name the affected area and practical result when evidence supports
them. Avoid commit hashes, filenames, implementation jargon, ticket-only
descriptions, promotional claims, and invented benefits. Combine related
implementation steps into one outcome; split unrelated user effects.

## Update today's digest

1. Prepare a UTF-8 JSON input matching
   [`schemas/changes.schema.json`](schemas/changes.schema.json). Keep this
   transient input outside the repository when practical and remove it after
   the update; it is not project documentation.
2. Build a read-only plan:

   ```shell
   python <skill-root>/scripts/project_digest.py plan \
     --project-root <project-root> \
     --documentation-root <documentation-root> \
     --input <changes.json> \
     --json
   ```

3. Review the preview for factual wording, category choice, duplicate meaning,
   sensitive detail, and the resolved local date. The generated structure is:

   ```markdown
   # Дайджест проекта

   ## [2026-10-23]

   ### Доработки

   - Добавлен список категорий товара.
   ```

4. Apply the plan with its `expected_sha256` value:

   ```shell
   python <skill-root>/scripts/project_digest.py apply \
     --project-root <project-root> \
     --documentation-root <documentation-root> \
     --input <changes.json> \
     --expected-sha256 <plan-value> \
     --json
   ```

5. If apply reports stale content or an active lock, do not overwrite it.
   Re-read, re-plan, and merge the intended entries with the latest today's
   section. Escalate a persistent or abandoned lock instead of deleting it by
   assumption.
6. Review the resulting diff. Report entries that were added and entries that
   were already present.

The helper inserts the newest date first, modifies only today's section,
deduplicates identical normalized entries, serializes cooperating writers with
a lock file, verifies the planned content hash, and replaces the digest
atomically. It rejects historical dates and unfamiliar structures instead of
rewriting them. Historical correction or backfill is outside the ordinary
workflow and requires a separate explicit user request and careful manual
review.

Completion criterion: today's section contains every supported completed
change exactly once, earlier dated sections are byte-for-byte unchanged, and
the digest remains understandable without engineering context.

## Keep sensitive and technical detail out

- Do not record credentials, private data, internal URLs, exploit steps, or
  confidential customer details.
- Describe security outcomes at the level needed by affected users.
- Do not copy raw logs, terminal output, stack traces, or private reasoning.
- Use `$maintain-work-log` separately when the project needs operational
  decisions, diagnostics, commands, verification evidence, or blockers.

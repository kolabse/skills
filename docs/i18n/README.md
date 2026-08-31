# Documentation localization roadmap

English is the canonical source. Translations cover the public README,
contribution guide, support, privacy policy, and terms of use; skill instructions,
technical references, and the changelog remain in English.

## Available languages

The authoritative document mappings are in [locales.json](locales.json).

- English (canonical)
- Russian (`ru`)
- Spanish (`es`)
- French (`fr`)
- German (`de`)
- Brazilian Portuguese (`pt-BR`)
- Japanese (`ja`)
- Italian (`it`)
- Korean (`ko`)
- Simplified Chinese (`zh-CN`)
- Turkish (`tr`)

## Planned languages

- Polish (`pl`)
- Ukrainian (`uk`)

These are backlog items, not available translations or release commitments.
Add them to the locale manifest and language navigation only when all five
documents are complete and validated. Keep English commands and technical
identifiers unchanged and preserve safety boundaries in every translation.

## Revision tracking

The existing 50 translations have baseline revision records in
[translation-status.json](translation-status.json). Run
`python scripts/translation_freshness.py status --strict --json` from the
repository root to find changed English sections or translations needing review.
Baseline/aligned does not mean semantic quality was independently verified.
After reviewing one document, generate an exact-hash-bound `record` proposal;
do not regenerate the baseline to clear stale translations. See the
[freshness workflow](../collection-reliability.md#translation-revision-freshness).

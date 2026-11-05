# Project documentation workflow candidates and reference generator

Contribution source material for [issue #165](https://github.com/kolabse/skills/issues/165). This branch is an intake handoff for maintainer review; it does not install or implement a skill and is not intended to be merged as a collection release.

## Candidate packages

| Package | Intended outcome |
| --- | --- |
| [author-operational-documentation.json](author-operational-documentation.json) | Write and revise operational procedures while preserving technical meaning |
| [restructure-project-documentation.json](restructure-project-documentation.json) | Inventory and migrate documentation while preserving audience boundaries, links and consumers |
| [assess-project-documentation-package.json](assess-project-documentation-package.json) | Assess the concrete documentation needed for operation, recovery and handover |
| [build-source-bound-documentation-site.json](build-source-bound-documentation-site.json) | Generate a static derivative with revision-bound source links and artifact provenance |

All four packages were exported with discover-skill-candidates and accepted by validate-contribution. Each carries its own source-evidence hashes, examples, proposed tests, limitations, explicit contributor attestations and package digest. Private inventory, original rule files and the scored discovery report are not included.

## Reference generator

[documentation-generator-reference.zip](documentation-generator-reference.zip) contains the approved 27-file source-only extraction: renderer, frontend, pinned dependency declarations, synthetic documentation and unit fixtures, Apache-2.0 license, modification notice, dependency metadata and file hashes.

It contains no original project documentation, branding, private addresses, real source allowlist, credentials or deployment configuration. Read the archive README for assumptions and known limitations. This extracted generator has not been executed, installed, built or deployed; collection publication checks do not establish that its renderer works unchanged. A later consumer must arrange an authorized cloud build and browser acceptance separately.

The contributor confirmed the right to share the original material under Apache-2.0 and reviewed the disclosed content. Third-party dependency licenses remain separate. No third-party dependency source or generated assets are vendored.

## Integrity

Verify the immutable revision and [SHA256SUMS](SHA256SUMS) before reuse. The archive SHA-256 is `f72ce70542b6233360527f182a3a486df014a8021d7144e209a439073787a8bd`.

The local .gitattributes disables line-ending conversion for this directory so the reviewed artifact bytes and SHA256SUMS remain consistent on Windows and Unix.

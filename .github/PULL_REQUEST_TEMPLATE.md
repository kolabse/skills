## Skill change

- Skill(s):
- Change type: new / migrated / updated / deprecated
- Canonical source:
- License:

## Candidate tracking

- Source Issue or reason none applies:
- [ ] The pull request body contains `Closes #<issue-number>`, or explicitly
      explains why the source Issue must remain open.

## Validation

- [ ] `skill-catalog.json` records provenance, license, maintainers, platforms,
      and status.
- [ ] README catalog and first-run instructions are current.
- [ ] Project-specific configuration and credentials stay outside the skill.
- [ ] Deterministic scripts have automated tests.
- [ ] Positive trigger prompt:
- [ ] Nearby negative trigger prompt:
- [ ] Blind trigger-eval observations and selector identity:
- [ ] First-run prompt or reason it is not applicable:
- [ ] `python scripts/validate_skills.py`
- [ ] `python -m unittest discover -s tests -v`
- [ ] `npx skills@1.5.22 add . --list`

## Evidence

Summarize results, supported operating systems exercised, and any unresolved
compatibility or licensing decision.

After merge, verify the linked Issue's actual state. If GitHub did not close it
as intended, close it as completed with links to this pull request and the
release when available.

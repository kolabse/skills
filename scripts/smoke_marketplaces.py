from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from validate_skills import validate_marketplace_manifests  # noqa: E402


def smoke(repository: Path) -> dict[str, object]:
    repository = repository.resolve()
    errors = validate_marketplace_manifests(repository)
    manifests = {
        "codex": repository / ".codex-plugin/plugin.json",
        "claude-code": repository / ".claude-plugin/plugin.json",
    }
    versions: dict[str, str] = {}
    for consumer, path in manifests.items():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
            errors.append(f"{path}: could not load plugin payload: {error}")
            continue
        if not isinstance(payload, dict) or payload.get("name") != "kolabse-skills":
            errors.append(f"{path}: plugin payload name must be 'kolabse-skills'")
            continue
        version = payload.get("version")
        if isinstance(version, str):
            versions[consumer] = version
        else:
            errors.append(f"{path}: plugin payload version is required")

    if len(set(versions.values())) > 1:
        errors.append("Codex and Claude Code plugin payload versions differ")
    skills = sorted(
        path.parent.name for path in (repository / "skills").glob("*/SKILL.md")
    )
    if not skills:
        errors.append(f"{repository / 'skills'}: no installable skills found")
    schemas = {
        "codex": repository / "schemas/codex-marketplace.schema.json",
        "claude-code": repository / "schemas/claude-marketplace.schema.json",
    }
    for consumer, path in schemas.items():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
            errors.append(
                f"{path}: could not load {consumer} marketplace schema: {error}"
            )
            continue
        if not isinstance(payload, dict) or payload.get("type") != "object":
            errors.append(f"{path}: marketplace schema root must describe an object")

    return {
        "ok": not errors,
        "marketplace": "kolabse",
        "plugin": "kolabse-skills",
        "versions": versions,
        "skill_count": len(skills),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-test the Git marketplace payloads for Codex and Claude Code."
    )
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = smoke(args.repository)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["ok"]:
        print(
            "Validated Git marketplace payloads for Codex and Claude Code "
            f"with {result['skill_count']} skill(s)."
        )
    else:
        for error in result["errors"]:
            print(f"ERROR: {error}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

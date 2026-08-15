from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def canonical_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_catalog(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("catalog root must be an object")
    return value


def resolve(catalog: dict[str, Any], name: str, enabled: set[str]) -> dict[str, Any]:
    compositions = {
        item["name"]: item
        for item in catalog.get("compositions", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    if name not in compositions:
        raise ValueError(f"unknown composition: {name}")
    composition = compositions[name]
    optional = list(composition.get("optional_steps", []))
    unknown = enabled - set(optional)
    if unknown:
        raise ValueError(f"not optional in {name}: {', '.join(sorted(unknown))}")
    required = list(composition.get("required_steps", []))
    steps = [
        *({"skill": skill, "required": True} for skill in required),
        *({"skill": skill, "required": False} for skill in optional if skill in enabled),
    ]
    result = {"schema_version": 1, "composition": name, "steps": steps}
    result["plan_sha256"] = canonical_digest(result)
    return result


def verify_execution(plan: dict[str, Any], evidence: object) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        raise ValueError("composition evidence root must be an object")
    required_fields = {"schema_version", "composition", "plan_sha256", "steps", "evidence_sha256"}
    if set(evidence) != required_fields or evidence.get("schema_version") != 1:
        raise ValueError("composition evidence has an unsupported contract")
    supplied_digest = evidence.get("evidence_sha256")
    unsigned = dict(evidence)
    unsigned.pop("evidence_sha256", None)
    if not isinstance(supplied_digest, str) or supplied_digest != canonical_digest(unsigned):
        raise ValueError("composition evidence digest is missing or invalid")
    if evidence.get("composition") != plan["composition"]:
        raise ValueError("composition evidence names another composition")
    if evidence.get("plan_sha256") != plan["plan_sha256"]:
        raise ValueError("composition evidence is bound to another plan")
    observed = evidence.get("steps")
    if not isinstance(observed, list) or len(observed) != len(plan["steps"]):
        raise ValueError("composition evidence must cover every planned step exactly once")
    failures: list[str] = []
    optional_failures: list[str] = []
    normalized: list[dict[str, Any]] = []
    for expected, item in zip(plan["steps"], observed, strict=True):
        if not isinstance(item, dict) or set(item) != {"skill", "status", "evidence_sha256"}:
            raise ValueError("composition step evidence is malformed")
        if item.get("skill") != expected["skill"]:
            raise ValueError("composition step evidence is out of order")
        status = item.get("status")
        digest = item.get("evidence_sha256")
        if status not in {"passed", "failed", "skipped"}:
            raise ValueError(f"invalid composition step status: {status}")
        if status == "passed" and (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("passed composition steps require a lowercase SHA-256 evidence digest")
        if status != "passed" and digest is not None:
            raise ValueError("failed or skipped composition steps cannot claim evidence")
        if status != "passed":
            (failures if expected["required"] else optional_failures).append(expected["skill"])
        normalized.append({**item, "required": expected["required"]})
    result = {
        "schema_version": 1,
        "mode": "verify-composition",
        "composition": plan["composition"],
        "plan_sha256": plan["plan_sha256"],
        "passed": not failures,
        "required_failures": failures,
        "optional_failures": optional_failures,
        "steps": normalized,
    }
    result["report_sha256"] = canonical_digest(result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve or verify a declared skill composition.")
    parser.add_argument("name")
    parser.add_argument("--enable", action="append", default=[])
    parser.add_argument("--catalog", type=Path, default=ROOT / "skill-catalog.json")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args(argv)
    try:
        plan = resolve(load_catalog(args.catalog), args.name, set(args.enable))
        result = plan
        if args.evidence:
            result = verify_execution(plan, json.loads(args.evidence.read_text(encoding="utf-8")))
        print(json.dumps(result, indent=2))
        return 0 if result.get("passed", True) else 1
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"COMPOSITION_FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

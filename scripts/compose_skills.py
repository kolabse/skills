from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


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
    return {"composition": name, "steps": steps}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve a declared skill composition.")
    parser.add_argument("name")
    parser.add_argument("--enable", action="append", default=[])
    parser.add_argument("--catalog", type=Path, default=ROOT / "skill-catalog.json")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(resolve(load_catalog(args.catalog), args.name, set(args.enable)), indent=2))
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"COMPOSITION_FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

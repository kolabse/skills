from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SCENARIOS = (
    "roundtrip-new-existing",
    "ordered-deltas",
    "title-and-content-conflict",
    "interrupted-upload-retry",
    "paginated-drive-coverage",
    "environment-reconciliation",
    "destination-rule-no-overwrite",
    "tamper-rejection",
    "audit-and-idempotency",
)
OPAQUE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+){1,7}$")
VERSION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+_-]{0,63}$")


class AcceptanceError(ValueError):
    pass


def canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AcceptanceError("acceptance evidence root must be an object")
    return value


def normalize(value: object, *, require_digest: bool) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AcceptanceError("acceptance evidence root must be an object")
    expected = {
        "schema_version",
        "kind",
        "run_id",
        "skill_version",
        "backend",
        "machine_ids",
        "product_versions",
        "scenarios",
    }
    if require_digest:
        expected.add("record_sha256")
    if set(value) != expected:
        raise AcceptanceError("acceptance evidence has missing or unexpected fields")
    if value.get("schema_version") != 1 or value.get("kind") != "sync-project-context-real-device":
        raise AcceptanceError("acceptance evidence has an unsupported contract")
    run_id = value.get("run_id")
    if not isinstance(run_id, str) or not OPAQUE_ID.fullmatch(run_id):
        raise AcceptanceError("run_id must be an opaque lowercase identifier")
    version = value.get("skill_version")
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise AcceptanceError("skill_version is invalid")
    if value.get("backend") != "google-drive":
        raise AcceptanceError("real-device promotion evidence requires google-drive")
    machines = value.get("machine_ids")
    if (
        not isinstance(machines, list)
        or len(machines) != 2
        or len(set(machines)) != 2
        or not all(isinstance(item, str) and OPAQUE_ID.fullmatch(item) for item in machines)
    ):
        raise AcceptanceError("machine_ids must contain two distinct opaque identifiers")
    versions = value.get("product_versions")
    if (
        not isinstance(versions, dict)
        or set(versions) != {"codex", "google-drive-connector"}
        or not all(isinstance(item, str) and VERSION.fullmatch(item) for item in versions.values())
    ):
        raise AcceptanceError("product_versions must contain bounded Codex and connector versions")
    scenarios = value.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != len(SCENARIOS):
        raise AcceptanceError("acceptance evidence must contain every scenario exactly once")
    observed: dict[str, dict[str, Any]] = {}
    for item in scenarios:
        if not isinstance(item, dict) or set(item) != {"name", "passed", "observations"}:
            raise AcceptanceError("acceptance scenario is malformed")
        name = item.get("name")
        observations = item.get("observations")
        if name not in SCENARIOS or name in observed:
            raise AcceptanceError("acceptance scenario is unknown or duplicated")
        if not isinstance(item.get("passed"), bool):
            raise AcceptanceError("acceptance scenario passed must be boolean")
        if (
            not isinstance(observations, dict)
            or not observations
            or not all(
                isinstance(key, str)
                and re.fullmatch(r"[a-z][a-z0-9_]{0,47}", key)
                and isinstance(count, int)
                and not isinstance(count, bool)
                and count >= 0
                for key, count in observations.items()
            )
        ):
            raise AcceptanceError("scenario observations must be non-negative sanitized counts")
        observed[name] = item
    if set(observed) != set(SCENARIOS):
        raise AcceptanceError("acceptance evidence is missing scenarios")
    normalized = dict(value)
    if require_digest:
        supplied = normalized.pop("record_sha256")
        if not isinstance(supplied, str) or supplied != canonical_digest(normalized):
            raise AcceptanceError("acceptance evidence digest is missing or invalid")
        normalized["record_sha256"] = supplied
    return normalized


def seal(value: object) -> dict[str, Any]:
    result = normalize(value, require_digest=False)
    result["record_sha256"] = canonical_digest(result)
    return result


def validate(value: object) -> dict[str, Any]:
    record = normalize(value, require_digest=True)
    failed = [item["name"] for item in record["scenarios"] if not item["passed"]]
    result = {
        "schema_version": 1,
        "mode": "validate-real-device-acceptance",
        "valid": True,
        "passed": not failed,
        "run_id": record["run_id"],
        "skill_version": record["skill_version"],
        "failed_scenarios": failed,
        "record_sha256": record["record_sha256"],
    }
    result["report_sha256"] = canonical_digest(result)
    return result


def verify_promotion(records: list[dict[str, Any]]) -> dict[str, Any]:
    if len(records) != 2:
        raise AcceptanceError("promotion requires exactly two real-device runs")
    validated = [validate(record) for record in records]
    if len({item["run_id"] for item in validated}) != 2:
        raise AcceptanceError("promotion runs must have distinct run_ids")
    if len({item["skill_version"] for item in validated}) != 1:
        raise AcceptanceError("promotion runs must test the same skill version")
    result = {
        "schema_version": 1,
        "mode": "verify-real-device-promotion",
        "passed": all(item["passed"] for item in validated),
        "skill_version": validated[0]["skill_version"],
        "runs": [
            {"run_id": item["run_id"], "record_sha256": item["record_sha256"]}
            for item in validated
        ],
    }
    result["report_sha256"] = canonical_digest(result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seal and verify sanitized real-device acceptance evidence.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("seal", "validate"):
        child = subparsers.add_parser(name)
        child.add_argument("--input", type=Path, required=True)
    promotion = subparsers.add_parser("verify-promotion")
    promotion.add_argument("--evidence", type=Path, action="append", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "seal":
            result = seal(load_object(args.input))
        elif args.command == "validate":
            result = validate(load_object(args.input))
        else:
            result = verify_promotion([load_object(path) for path in args.evidence])
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result.get("passed", True) else 1
    except (AcceptanceError, OSError, UnicodeError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

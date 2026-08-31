"""One fail-fast, argv-only check program for maintainers and CI."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_program(root):
    path = root / "collection-checks.json"
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("check program exceeds size limit")
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key in check program")
            result[key] = value
        return result
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    if not isinstance(value, dict) or set(value) != {"schema_version", "checks", "profiles"} or type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("invalid check program schema")
    checks, profiles = value["checks"], value["profiles"]
    if not isinstance(checks, dict) or not checks or not isinstance(profiles, dict):
        raise ValueError("checks and profiles must be objects")
    for name, check in checks.items():
        if not re.fullmatch(r"[a-z][a-z0-9-]*", name) or not isinstance(check, dict) or set(check) != {"command", "timeout_seconds"}:
            raise ValueError("invalid check definition")
        argv = check["command"]
        if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item or "\x00" in item for item in argv):
            raise ValueError("command must be a nonempty argv array")
        if argv[0] not in {"{python}", "{npx}"}:
            raise ValueError("only explicit Python/npx executables are supported")
        if type(check["timeout_seconds"]) is not int or not 1 <= check["timeout_seconds"] <= 1800:
            raise ValueError("invalid check timeout")
    for name, sequence in profiles.items():
        if not re.fullmatch(r"[a-z][a-z0-9-]*", name) or not isinstance(sequence, list) or not sequence or any(not isinstance(item, str) or item not in checks for item in sequence) or len(sequence) != len(set(sequence)):
            raise ValueError("invalid profile sequence")
    if not profiles.get("preflight") or not profiles.get("full") or profiles["full"][:len(profiles["preflight"])] != profiles["preflight"]:
        raise ValueError("full must start with the complete preflight profile")
    return value


def plan(root, profile):
    program = load_program(root)
    if profile not in program["profiles"]:
        raise ValueError("unknown profile")
    steps = []
    for name in program["profiles"][profile]:
        check = program["checks"][name]
        executable = sys.executable if check["command"][0] == "{python}" else shutil.which("npx")
        if not executable:
            raise ValueError("npx is required for this profile")
        steps.append({"name": name, "command": [executable, *check["command"][1:]], "timeout_seconds": check["timeout_seconds"]})
    return {"schema_version": 1, "profile": profile, "program_sha256": digest(program), "steps": steps}


def run(root, profile, progress=False):
    report = plan(root, profile)
    results = []
    for step in report["steps"]:
        if progress:
            print(f"Running {step['name']}...", flush=True)
        started = time.monotonic()
        try:
            completed = subprocess.run(step["command"], cwd=root, env={**os.environ, "DISABLE_TELEMETRY": "1", "PYTHONUTF8": "1"}, capture_output=True, timeout=step["timeout_seconds"], check=False)
            output = completed.stdout + completed.stderr
            code, reason = completed.returncode, "completed"
        except subprocess.TimeoutExpired:
            code, reason, output = -1, "timeout", b""
        except OSError:
            code, reason, output = -1, "launch-failed", b""
        result = {"name": step["name"], "passed": code == 0, "exit_code": code, "reason": reason, "elapsed_seconds": round(time.monotonic() - started, 3), "output_sha256": hashlib.sha256(output).hexdigest()}
        results.append(result)
        if progress:
            print(f"{step['name']}: {'PASS' if result['passed'] else 'FAIL'} ({result['elapsed_seconds']}s)", flush=True)
            if code:
                # Output is local check output, not retained in the machine report.
                print(output[-12000:].decode("utf-8", errors="replace"), flush=True)
        if code:
            break
    report.update(results=results, passed=len(results) == len(report["steps"]) and all(item["passed"] for item in results))
    return report


def versions(root):
    catalog = json.loads((root / "skill-catalog.json").read_text(encoding="utf-8"))
    expected = catalog["collection_version"]
    values = {}
    for relative in (".codex-plugin/plugin.json", ".claude-plugin/plugin.json"):
        values[relative] = json.loads((root / relative).read_text(encoding="utf-8"))["version"]
    tree = ast.parse((root / "scripts/manage_installed_skills.py").read_text(encoding="utf-8"))
    assignments = [ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "COLLECTION_VERSION" for target in node.targets)]
    if len(assignments) != 1:
        raise ValueError("manager must declare exactly one collection version")
    values["manager"] = assignments[0]
    return {"schema_version": 1, "expected": expected, "versions": values, "passed": all(value == expected for value in values.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "run", "versions"))
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--profile", default="full")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        root = args.project_root.resolve()
        result = versions(root) if args.mode == "versions" else plan(root, args.profile) if args.mode == "plan" else run(root, args.profile, progress=not args.json)
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0 if result.get("passed", True) else 1
    except (OSError, ValueError, KeyError, SyntaxError) as error:
        print(json.dumps({"passed": False, "error": str(error)}, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

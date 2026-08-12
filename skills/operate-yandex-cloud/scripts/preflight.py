from __future__ import annotations

import argparse
import json
from pathlib import Path

from cloud_skill import run_preflight, serializable_results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run read-only Yandex Cloud context checks.")
    parser.add_argument("--project-path", required=True, type=Path)
    parser.add_argument("--scan-path", action="append", type=Path, default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    scan_paths = args.scan_path or [args.project_path]
    checks = run_preflight(args.project_path, scan_paths)
    if args.json:
        print(json.dumps({"checks": serializable_results(checks)}, indent=2))
    else:
        for check in checks:
            print(f"[{check.status.upper():4}] {check.name}: {check.detail}")
    return 1 if any(check.status == "fail" for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cloud_skill import (
    detect_toolsets,
    inspect_tools,
    install_tools,
    serializable_results,
)


def print_table(results) -> None:
    headings = ("TOOL", "TOOLSET", "STATUS", "VERSION", "MINIMUM")
    rows = [
        (item.name, item.toolset, item.status, item.version or "-", item.minimum_version)
        for item in results
    ]
    widths = [max(len(str(row[index])) for row in [headings, *rows]) for index in range(5)]
    print("  ".join(headings[index].ljust(widths[index]) for index in range(5)))
    for row in rows:
        print("  ".join(str(row[index]).ljust(widths[index]) for index in range(5)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Yandex Cloud workflow tools.")
    parser.add_argument("--project-path", required=True, type=Path)
    parser.add_argument("--scan-path", action="append", type=Path, default=[])
    parser.add_argument("--toolset", action="append", default=[])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--install-missing", action="store_true")
    parser.add_argument("--non-interactive", action="store_true")
    args = parser.parse_args()

    scan_paths = args.scan_path or [args.project_path]
    toolsets = detect_toolsets(scan_paths) | set(args.toolset)
    results = inspect_tools(toolsets, include_all=args.all)
    if args.json:
        print(
            json.dumps(
                {"toolsets": sorted(toolsets), "tools": serializable_results(results)},
                indent=2,
            )
        )
    else:
        print(f"Detected toolsets: {', '.join(sorted(toolsets))}")
        print_table(results)

    actionable = [
        item
        for item in results
        if item.status in {"missing", "outdated", "unknown-version", "error"}
    ]
    installable = [item for item in actionable if item.install_supported]
    manual = [item for item in actionable if not item.install_supported]
    if manual and not args.json:
        print("\nManual actions:")
        for item in manual:
            print(f"- {item.name}: {item.guidance}")

    should_install = args.install_missing
    if installable and not args.install_missing and not args.non_interactive:
        answer = input(
            f"\nInstall supported missing/outdated tools ({', '.join(item.name for item in installable)})? [y/N]: "
        )
        should_install = answer.strip().lower() in {"y", "yes"}
    if should_install:
        installation_results = install_tools({item.name for item in installable})
        failed = [result for result in installation_results if result.returncode != 0]
        if failed:
            for result in failed:
                print(f"Installation failed: {' '.join(result.command)}\n{result.output}")
            return 1
        if installation_results:
            print("Tool installation finished. Open a new terminal and run the check again.")

    return 1 if actionable else 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from pathlib import Path

from cloud_skill import configure_project, load_config


def existing_value(project_path: Path, name: str) -> str:
    try:
        return str(getattr(load_config(project_path), name))
    except (FileNotFoundError, ValueError):
        return ""


def ask(label: str, default: str = "", *, required: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{label}{suffix}: ").strip() or default
        if value or not required:
            return value
        print(f"{label} is required.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Configure one project for Yandex Cloud operations."
    )
    parser.add_argument("--project-path", required=True, type=Path)
    parser.add_argument("--cloud-id")
    parser.add_argument("--folder-id")
    parser.add_argument("--yc-profile")
    parser.add_argument("--non-interactive", action="store_true")
    args = parser.parse_args()

    cloud_id = args.cloud_id
    folder_id = args.folder_id
    yc_profile = args.yc_profile
    if not args.non_interactive:
        cloud_id = cloud_id or ask(
            "Yandex Cloud ID",
            existing_value(args.project_path, "cloud_id"),
            required=True,
        )
        if folder_id is None:
            folder_id = ask(
                "Default Folder ID (optional)",
                existing_value(args.project_path, "folder_id"),
            )
        if yc_profile is None:
            yc_profile = ask(
                "yc profile name (optional)",
                existing_value(args.project_path, "yc_profile"),
            )
    elif not cloud_id:
        parser.error("--cloud-id is required with --non-interactive")

    config = configure_project(
        args.project_path,
        cloud_id or "",
        folder_id or "",
        yc_profile or "",
    )
    print(f"Saved shared project configuration for cloud {config.cloud_id}.")
    print("Saved the yc profile to ignored local configuration.")
    print("The global yc profile was not changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cloud_skill import config_path, load_config, save_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate Yandex Cloud project configuration.")
    parser.add_argument("--project-path", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        path = config_path(args.project_path)
        before = path.read_bytes()
        config = load_config(args.project_path)
        save_config(args.project_path, config)
        state = {
            "skill": "operate-yandex-cloud",
            "version": 3,
            "changed": before != path.read_bytes(),
            "config_file": str(path),
        }
        print(json.dumps(state, sort_keys=True) if args.json else f"Configuration is version 3: {path}")
        return 0
    except (FileNotFoundError, OSError, UnicodeError, ValueError) as error:
        print(f"CONFIGURATION_FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

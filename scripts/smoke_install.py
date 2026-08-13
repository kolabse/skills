from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILLS_CLI_VERSION = "1.5.22"


class SmokeError(RuntimeError):
    pass


def file_manifest(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise SmokeError(f"Installed content must be copied, not linked: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def catalog_skills(source: Path) -> list[str]:
    try:
        catalog = json.loads((source / "skill-catalog.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SmokeError(f"Could not read skill catalog: {error}") from error
    entries = catalog.get("skills") if isinstance(catalog, dict) else None
    if not isinstance(entries, list) or not entries:
        raise SmokeError("Skill catalog must contain skills")
    names = [entry.get("name") if isinstance(entry, dict) else None for entry in entries]
    if not all(isinstance(name, str) and name for name in names):
        raise SmokeError("Every catalog skill requires a name")
    return sorted(names)


def verify_installation(source: Path, project: Path, names: list[str]) -> None:
    installed_root = project / ".agents" / "skills"
    if not installed_root.is_dir():
        raise SmokeError(f"Installer did not create {installed_root}")
    installed_names = sorted(path.name for path in installed_root.iterdir() if path.is_dir())
    if installed_names != names:
        raise SmokeError(
            f"Installed skills differ from catalog: expected {names}, got {installed_names}"
        )
    for name in names:
        expected = file_manifest(source / "skills" / name)
        actual = file_manifest(installed_root / name)
        if expected != actual:
            missing = sorted(set(expected) - set(actual))
            unexpected = sorted(set(actual) - set(expected))
            changed = sorted(
                path for path in set(expected) & set(actual) if expected[path] != actual[path]
            )
            raise SmokeError(
                f"Installed {name} differs from source; missing={missing}, "
                f"unexpected={unexpected}, changed={changed}"
            )
    lock_path = project / "skills-lock.json"
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SmokeError(f"Installer lock file is invalid: {error}") from error
    locked = lock.get("skills") if isinstance(lock, dict) else None
    if not isinstance(locked, dict) or sorted(locked) != names:
        raise SmokeError("Installer lock does not contain exactly the catalog skills")
    for name in names:
        digest = locked[name].get("computedHash") if isinstance(locked[name], dict) else None
        if not isinstance(digest, str) or len(digest) != 64:
            raise SmokeError(f"Installer lock has no computed hash for {name}")


def run_smoke(source: Path, npx: str, cli_version: str, timeout: int) -> int:
    names = catalog_skills(source)
    with tempfile.TemporaryDirectory(prefix="kolabse-skills-install-") as directory:
        project = Path(directory)
        environment = os.environ.copy()
        environment["DISABLE_TELEMETRY"] = "1"
        result = subprocess.run(
            [
                npx,
                "--yes",
                f"skills@{cli_version}",
                "add",
                str(source),
                "--skill",
                "*",
                "--agent",
                "codex",
                "--yes",
                "--copy",
            ],
            cwd=project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stdout + "\n" + result.stderr).strip()
            raise SmokeError(f"skills CLI exited with {result.returncode}: {detail[-1000:]}")
        verify_installation(source, project, names)
    print(f"Installed and verified {len(names)} copied skill(s) with skills@{cli_version}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test skills CLI installation.")
    parser.add_argument("--source", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--cli-version", default=SKILLS_CLI_VERSION)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    try:
        if args.timeout <= 0:
            raise SmokeError("timeout must be positive")
        npx = shutil.which("npx")
        if not npx:
            raise SmokeError("npx was not found")
        return run_smoke(args.source.resolve(), npx, args.cli_version, args.timeout)
    except (SmokeError, OSError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

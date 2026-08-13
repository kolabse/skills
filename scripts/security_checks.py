from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTION_PIN = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", re.MULTILINE)
FULL_SHA = re.compile(r"^[^@]+@[0-9a-f]{40}$")
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "Telegram bot token": re.compile(r"\b[0-9]{6,12}:[A-Za-z0-9_-]{30,}\b"),
}
SKIP_DIRECTORIES = {".git", ".trigger-evals", "dist", "__pycache__"}


def tracked_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRECTORIES for part in path.relative_to(root).parts):
            continue
        if path.stat().st_size <= 2 * 1024 * 1024:
            files.append(path)
    return files


def check_secrets(root: Path) -> list[str]:
    errors: list[str] = []
    for path in tracked_source_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"{path}: possible committed {label}")
    return errors


def check_python(root: Path) -> list[str]:
    errors: list[str] = []
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRECTORIES for part in path.relative_to(root).parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError, OSError) as error:
            errors.append(f"{path}: cannot inspect Python: {error}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                    errors.append(f"{path}:{node.lineno}: subprocess shell=True is forbidden")
    return errors


def check_workflows(root: Path) -> list[str]:
    errors: list[str] = []
    workflow_root = root / ".github/workflows"
    for path in [*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml")]:
        text = path.read_text(encoding="utf-8")
        if not re.search(r"(?m)^permissions:\s*$", text):
            errors.append(f"{path}: top-level permissions are required")
        if "write-all" in text:
            errors.append(f"{path}: write-all permissions are forbidden")
        for reference in ACTION_PIN.findall(text):
            if reference.startswith("./"):
                continue
            if not FULL_SHA.fullmatch(reference):
                errors.append(f"{path}: action is not pinned to a full SHA: {reference}")
    return errors


def validate(root: Path) -> list[str]:
    return [*check_secrets(root), *check_python(root), *check_workflows(root)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run dependency-free collection security checks.")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    errors = validate(args.root.resolve())
    if errors:
        for error in errors:
            print(f"SECURITY_ERROR: {error}")
        return 1
    print("Security checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

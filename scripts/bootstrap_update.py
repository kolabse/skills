from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


REPOSITORY = "kolabse/skills"
API_ROOT = f"https://api.github.com/repos/{REPOSITORY}"
TAG_PATTERN = re.compile(r"^v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?$")
SUPPORTED_AGENTS = ("codex", "claude-code")


class BootstrapError(RuntimeError):
    pass


def request_bytes(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "kolabse-skills-bootstrap"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except (OSError, urllib.error.URLError) as error:
        raise BootstrapError(f"could not download {url}: {error}") from error


def resolve_stable_tag(timeout: int) -> str:
    try:
        payload = json.loads(request_bytes(f"{API_ROOT}/releases/latest", timeout))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise BootstrapError("latest release response is invalid JSON") from error
    tag = payload.get("tag_name") if isinstance(payload, dict) else None
    if not isinstance(tag, str) or not TAG_PATTERN.fullmatch(tag):
        raise BootstrapError(f"latest release returned an unsupported tag: {tag!r}")
    return tag


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_checksum(checksums: Path, artifact_name: str) -> str:
    matches: list[str] = []
    for line in checksums.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", line)
        if match and match.group(2) == artifact_name:
            matches.append(match.group(1))
    if len(matches) != 1:
        raise BootstrapError(f"SHA256SUMS must contain exactly one entry for {artifact_name}")
    return matches[0]


def verify_checksum(archive: Path, checksums: Path) -> None:
    expected = expected_checksum(checksums, archive.name)
    actual = sha256_file(archive)
    if actual != expected:
        raise BootstrapError(f"checksum mismatch for {archive.name}: {actual} != {expected}")


def verify_attestation(archive: Path, timeout: int) -> None:
    gh = shutil.which("gh")
    if not gh:
        raise BootstrapError("gh CLI is required to verify release provenance")
    try:
        result = subprocess.run(
            [gh, "attestation", "verify", str(archive), "--repo", REPOSITORY],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise BootstrapError(f"could not verify release provenance: {error}") from error
    if result.returncode != 0:
        detail = (result.stdout + "\n" + result.stderr).strip()
        raise BootstrapError(f"release provenance verification failed: {detail[-1000:]}")


def safe_extract(archive: Path, destination: Path) -> Path:
    with zipfile.ZipFile(archive) as package:
        files = package.infolist()
        if not files:
            raise BootstrapError("release archive is empty")
        for item in files:
            path = PurePosixPath(item.filename)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise BootstrapError(f"unsafe release archive path: {item.filename}")
            mode = item.external_attr >> 16
            if mode and (mode & 0o170000) == 0o120000:
                raise BootstrapError(f"release archive contains a symbolic link: {item.filename}")
        package.extractall(destination)
    managers = list(destination.glob("*/scripts/manage_installed_skills.py"))
    if len(managers) != 1:
        raise BootstrapError("release archive does not contain exactly one collection manager")
    return managers[0]


def forwarded_agent_arguments(arguments: list[str], agent: str) -> list[str]:
    if agent not in SUPPORTED_AGENTS:
        raise BootstrapError(f"unsupported agent {agent!r}")
    forwarded = list(arguments)
    declared: list[str] = []
    for index, value in enumerate(forwarded):
        if value == "--agent":
            if index + 1 >= len(forwarded) or forwarded[index + 1].startswith("-"):
                raise BootstrapError("forwarded --agent requires a value")
            declared.append(forwarded[index + 1])
        elif value.startswith("--agent="):
            declared.append(value.split("=", 1)[1])
    if len(declared) > 1:
        raise BootstrapError("agent selection is ambiguous; pass --agent exactly once")
    if declared and declared[0] != agent:
        raise BootstrapError(
            f"forwarded agent {declared[0]!r} conflicts with bootstrap agent {agent!r}"
        )
    if not declared:
        forwarded.extend(["--agent", agent])
    return forwarded


def run_manager(
    manager: Path,
    command: str,
    arguments: list[str],
    project: Path,
    timeout: int,
    agent: str = "codex",
) -> int:
    python = shutil.which("python") or sys.executable
    forwarded = (
        list(arguments)
        if command == "centralize"
        else forwarded_agent_arguments(arguments, agent)
    )
    if command in {"status", "doctor", "plan", "migrate", "update", "centralize"} and not any(
        value == "--project-path" or value.startswith("--project-path=") for value in forwarded
    ):
        forwarded.extend(["--project-path", str(project.resolve())])
    try:
        executable = (
            manager.with_name("centralize_skill_installations.py")
            if command == "centralize" else manager
        )
        command_argv = (
            [python, str(executable), *forwarded]
            if command == "centralize"
            else [python, str(executable), command, *forwarded]
        )
        result = subprocess.run(
            command_argv,
            cwd=project.resolve(),
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise BootstrapError(f"could not run collection manager: {error}") from error
    return result.returncode


def bootstrap(
    release: str,
    command: str,
    arguments: list[str],
    project: Path,
    timeout: int,
    offline_archive: Path | None = None,
    offline_checksums: Path | None = None,
    allow_unattested_offline: bool = False,
    agent: str = "codex",
) -> int:
    if agent not in SUPPORTED_AGENTS:
        raise BootstrapError(f"unsupported agent {agent!r}")
    if release == "stable":
        if offline_archive:
            match = re.fullmatch(r"kolabse-skills-(v[^/\\]+)\.zip", offline_archive.name)
            if not match or not TAG_PATTERN.fullmatch(match.group(1)):
                raise BootstrapError("could not infer a stable release tag from the offline archive name")
            tag = match.group(1)
        else:
            tag = resolve_stable_tag(timeout)
    elif TAG_PATTERN.fullmatch(release):
        tag = release
    else:
        raise BootstrapError(f"unsupported release selector: {release}")

    with tempfile.TemporaryDirectory(prefix="kolabse-skills-bootstrap-") as directory:
        workspace = Path(directory)
        if offline_archive:
            if not offline_archive.is_file() or not offline_checksums or not offline_checksums.is_file():
                raise BootstrapError("offline mode requires existing --offline-archive and --offline-checksums files")
            archive = workspace / offline_archive.name
            checksums = workspace / "SHA256SUMS"
            shutil.copy2(offline_archive, archive)
            shutil.copy2(offline_checksums, checksums)
        else:
            archive_name = f"kolabse-skills-{tag}.zip"
            base = f"https://github.com/{REPOSITORY}/releases/download/{tag}"
            archive = workspace / archive_name
            checksums = workspace / "SHA256SUMS"
            archive.write_bytes(request_bytes(f"{base}/{archive_name}", timeout))
            checksums.write_bytes(request_bytes(f"{base}/SHA256SUMS", timeout))
        verify_checksum(archive, checksums)
        if not (offline_archive and allow_unattested_offline):
            verify_attestation(archive, timeout)
        manager = safe_extract(archive, workspace / "extracted")
        return run_manager(manager, command, arguments, project, timeout, agent)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a verified kolabse manager from a release.")
    parser.add_argument("--release", default="stable")
    parser.add_argument("--project-path", type=Path, default=Path.cwd())
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--offline-archive", type=Path)
    parser.add_argument("--offline-checksums", type=Path)
    parser.add_argument("--allow-unattested-offline", action="store_true")
    parser.add_argument("--agent", choices=SUPPORTED_AGENTS, default="codex")
    parser.add_argument("command", choices=("status", "doctor", "plan", "migrate", "update", "centralize"))
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        return bootstrap(
            args.release,
            args.command,
            args.arguments,
            args.project_path,
            args.timeout,
            args.offline_archive,
            args.offline_checksums,
            args.allow_unattested_offline,
            args.agent,
        )
    except (BootstrapError, OSError, UnicodeError, zipfile.BadZipFile) as error:
        print(f"BOOTSTRAP_FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Iterable


ROOT_FILES = ("README.md", "LICENSE", "CHANGELOG.md", "skill-catalog.json")
OPTIONAL_PLUGIN_FILES = (".codex-plugin/plugin.json",)
TAG_PATTERN = re.compile(
    r"^v[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?$"
)
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_files(source: Path) -> list[Path]:
    source = source.resolve()
    files: list[Path] = []
    for name in ROOT_FILES:
        path = source / name
        if not path.is_file():
            raise FileNotFoundError(f"Required release file was not found: {path}")
        if path.is_symlink():
            raise ValueError(f"Release input must not be a symbolic link: {path}")
        files.append(path)
    for name in OPTIONAL_PLUGIN_FILES:
        path = source / name
        if path.exists():
            if not path.is_file():
                raise ValueError(f"Release input must be a file: {path}")
            if path.is_symlink():
                raise ValueError(f"Release input must not be a symbolic link: {path}")
            files.append(path)
    skills_root = source / "skills"
    if not skills_root.is_dir():
        raise FileNotFoundError(f"Skills directory was not found: {skills_root}")
    for path in skills_root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Release input must not be a symbolic link: {path}")
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix not in {".pyc", ".pyo"}
        ):
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(source).as_posix())


def source_commit(source: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        check=False,
    )
    if completed.returncode != 0:
        return ""
    commit = completed.stdout.strip()
    status = subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            *ROOT_FILES,
            *OPTIONAL_PLUGIN_FILES,
            "skills",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        check=False,
    )
    if status.returncode != 0:
        return ""
    return f"{commit}-dirty" if status.stdout.strip() else commit


def release_entries(
    source: Path,
    files: Iterable[Path],
    commit: str,
) -> list[tuple[Path, bytes]]:
    entries: list[tuple[Path, bytes]] = []
    use_git_blobs = bool(commit) and not commit.endswith("-dirty")
    for path in files:
        relative = path.relative_to(source)
        if use_git_blobs:
            completed = subprocess.run(
                ["git", "-C", str(source), "show", f"{commit}:{relative.as_posix()}"],
                capture_output=True,
                timeout=10,
                check=False,
            )
            if completed.returncode != 0:
                detail = completed.stderr.decode("utf-8", errors="replace").strip()
                raise ValueError(f"Could not read Git blob for {relative}: {detail}")
            content = completed.stdout
        else:
            content = path.read_bytes()
        entries.append((relative, content))
    return entries


def write_zip(
    destination: Path,
    prefix: str,
    entries: Iterable[tuple[Path, bytes]],
) -> None:
    with zipfile.ZipFile(
        destination,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for relative, content in entries:
            info = zipfile.ZipInfo(
                f"{prefix}/{relative.as_posix()}",
                date_time=ZIP_TIMESTAMP,
            )
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content, compresslevel=9)


def write_tar_gz(
    destination: Path,
    prefix: str,
    entries: Iterable[tuple[Path, bytes]],
) -> None:
    with destination.open("wb") as raw_output:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw_output,
            compresslevel=9,
            mtime=0,
        ) as compressed:
            with tarfile.open(
                fileobj=compressed,
                mode="w",
                format=tarfile.USTAR_FORMAT,
            ) as archive:
                for relative, content in entries:
                    info = tarfile.TarInfo(f"{prefix}/{relative.as_posix()}")
                    info.size = len(content)
                    info.mode = 0o644
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    archive.addfile(info, fileobj=io.BytesIO(content))


def build_release(source: Path, tag: str, output: Path) -> list[Path]:
    if not TAG_PATTERN.fullmatch(tag):
        raise ValueError(f"Unsupported release tag: {tag}")
    source = source.resolve()
    output.mkdir(parents=True, exist_ok=True)
    files = release_files(source)
    commit = source_commit(source)
    entries = release_entries(source, files, commit)
    prefix = f"kolabse-skills-{tag}"
    zip_path = output / f"{prefix}.zip"
    tar_path = output / f"{prefix}.tar.gz"
    write_zip(zip_path, prefix, entries)
    write_tar_gz(tar_path, prefix, entries)

    artifacts = [zip_path, tar_path]
    manifest_path = output / "release-manifest.json"
    manifest = {
        "schema_version": 1,
        "release": tag,
        "source_commit": commit,
        "artifacts": [
            {
                "name": path.name,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in artifacts
        ],
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    checksummed = [*artifacts, manifest_path]
    checksum_path = output / "SHA256SUMS"
    checksum_path.write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in checksummed),
        encoding="utf-8",
        newline="\n",
    )
    return [*checksummed, checksum_path]


def verify_checksums(checksum_path: Path) -> None:
    checksum_path = checksum_path.resolve()
    seen: set[str] = set()
    lines = checksum_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("Checksum file is empty")
    for line_number, line in enumerate(lines, 1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", line)
        if not match:
            raise ValueError(f"Invalid checksum line {line_number}: {line}")
        expected, name = match.groups()
        if name in seen:
            raise ValueError(f"Duplicate checksum entry: {name}")
        seen.add(name)
        artifact = checksum_path.parent / name
        if not artifact.is_file():
            raise FileNotFoundError(f"Checksummed file was not found: {artifact}")
        actual = sha256_file(artifact)
        if actual != expected:
            raise ValueError(f"Checksum mismatch for {name}: {actual} != {expected}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build or verify deterministic kolabse skill release artifacts."
    )
    parser.add_argument("--source", type=Path)
    parser.add_argument("--tag")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()

    try:
        if args.verify:
            if any(value is not None for value in (args.source, args.tag, args.output)):
                parser.error("--verify cannot be combined with build arguments")
            verify_checksums(args.verify)
            print(f"Verified checksums from {args.verify}.")
            return 0
        if args.source is None or args.tag is None or args.output is None:
            parser.error("--source, --tag, and --output are required when building")
        artifacts = build_release(args.source, args.tag, args.output)
        for path in artifacts:
            print(path)
        return 0
    except (FileNotFoundError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

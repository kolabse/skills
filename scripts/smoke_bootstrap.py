from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from bootstrap_update import bootstrap  # noqa: E402
from build_release import build_release  # noqa: E402


class SmokeError(RuntimeError):
    pass


def directory_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def run_smoke(source: Path, tag: str, timeout: int) -> None:
    with tempfile.TemporaryDirectory(prefix="kolabse-bootstrap-smoke-") as directory:
        root = Path(directory)
        project = root / "consumer"
        installed = project / ".agents/skills/verify-before-push"
        installed.parent.mkdir(parents=True)
        shutil.copytree(source / "skills/verify-before-push", installed)
        (project / "skills-lock.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "skills": {
                        "verify-before-push": {
                            "source": "kolabse/skills",
                            "sourceType": "github",
                            "computedHash": "0" * 64,
                        }
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        before = directory_digest(project)
        dist = root / "dist"
        build_release(source, tag, dist)
        archive = dist / f"kolabse-skills-{tag}.zip"
        result = bootstrap(
            tag,
            "plan",
            ["--json"],
            project,
            timeout,
            archive,
            dist / "SHA256SUMS",
            allow_unattested_offline=True,
        )
        if result != 0:
            raise SmokeError(f"bootstrap manager returned {result}")
        if directory_digest(project) != before:
            raise SmokeError("read-only bootstrap plan changed the consumer project")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the standalone release bootstrap.")
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--tag", default="v1.9.0")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    try:
        run_smoke(args.source.resolve(), args.tag, args.timeout)
        print("Standalone bootstrap plan passed without mutating the consumer fixture.")
        return 0
    except (OSError, SmokeError, ValueError) as error:
        print(f"BOOTSTRAP_SMOKE_FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

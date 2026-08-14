from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import context_sync


def namespace(**values: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "config_path": None,
        "json": True,
        "merge_heads": False,
        "checkpoint_id": None,
        "stream_id": None,
        "all_streams": False,
        "snapshot_kind": "auto",
        "snapshot_root": None,
    }
    defaults.update(values)
    return argparse.Namespace(**defaults)


def git(path: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *arguments],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def create_repository(path: Path, remote: str) -> None:
    path.mkdir(parents=True)
    git(path, "init", "--initial-branch=main")
    git(path, "config", "user.name", "Context Acceptance")
    git(path, "config", "user.email", "context-acceptance@example.invalid")
    (path / "tracked.txt").write_text("acceptance fixture\n", encoding="utf-8")
    git(path, "add", "tracked.txt")
    git(path, "commit", "-m", "acceptance fixture")
    git(path, "remote", "add", "origin", remote)


def run_acceptance(stream_count: int = 12) -> dict[str, Any]:
    if stream_count < 2 or stream_count > 100:
        raise ValueError("stream_count must be between 2 and 100")
    with tempfile.TemporaryDirectory(prefix="context-sync-acceptance-") as directory:
        root = Path(directory)
        project_a = root / "machine-a-project"
        project_b = root / "machine-b-project"
        config_a = root / "machine-a-config.json"
        config_b = root / "machine-b-config.json"
        storage = root / "shared-storage"
        payload = root / "payload.json"
        remote = "https://example.invalid/acceptance/project.git"
        create_repository(project_a, remote)
        create_repository(project_b, remote)
        for project, config in ((project_a, config_a), (project_b, config_b)):
            context_sync.command_configure(
                namespace(
                    project_path=str(project),
                    config_path=str(config),
                    backend="local-folder",
                    storage_root=str(storage),
                    project_id="proj-two-machine-acceptance",
                    mode="metadata-only",
                    acknowledge_storage_policy=True,
                )
            )

        checkpoints: list[str] = []
        for index in range(stream_count):
            stream_id = f"stream-{index + 1:032x}"
            title = f"Acceptance stream {index + 1}"
            payload.write_text(
                json.dumps(
                    {
                        "chat_title": title,
                        "summary": f"Created baseline {index + 1} on machine A.",
                        "decisions": ["Keep the acceptance sequence deterministic."],
                    }
                ),
                encoding="utf-8",
            )
            baseline = context_sync.command_capture(
                namespace(
                    project_path=str(project_a),
                    config_path=str(config_a),
                    input=str(payload),
                    stdin=False,
                    stream_id=stream_id,
                )
            )
            restored_b = context_sync.command_restore(
                namespace(
                    project_path=str(project_b),
                    config_path=str(config_b),
                    stream_id=stream_id,
                )
            )
            if restored_b["history_count"] != 1 or restored_b["chat_title"] != title:
                raise RuntimeError("machine B did not restore the exact baseline")
            payload.write_text(
                json.dumps(
                    {
                        "chat_title": title,
                        "summary": f"Appended delta {index + 1} on machine B.",
                        "verifications": ["Two-machine delta was observed."],
                    }
                ),
                encoding="utf-8",
            )
            delta = context_sync.command_capture(
                namespace(
                    project_path=str(project_b),
                    config_path=str(config_b),
                    input=str(payload),
                    stdin=False,
                    stream_id=stream_id,
                )
            )
            restored_a = context_sync.command_restore(
                namespace(
                    project_path=str(project_a),
                    config_path=str(config_a),
                    stream_id=stream_id,
                )
            )
            repeated = context_sync.command_restore(
                namespace(
                    project_path=str(project_a),
                    config_path=str(config_a),
                    stream_id=stream_id,
                )
            )
            if restored_a != repeated or restored_a["history_count"] != 2:
                raise RuntimeError("restore is not idempotent after a cross-machine delta")
            checkpoints.extend([baseline["checkpoint_id"], delta["checkpoint_id"]])

        status_a = context_sync.command_status(
            namespace(project_path=str(project_a), config_path=str(config_a))
        )
        audit_a = context_sync.command_audit(
            namespace(project_path=str(project_a), config_path=str(config_a))
        )
        audit_b = context_sync.command_audit(
            namespace(project_path=str(project_b), config_path=str(config_b))
        )
        if status_a["stream_count"] != stream_count or status_a["has_conflict"]:
            raise RuntimeError("final stream inventory is incomplete or conflicted")
        if not audit_a["ok"] or not audit_b["ok"]:
            raise RuntimeError("final audit failed on one of the simulated machines")
        if len(checkpoints) != len(set(checkpoints)):
            raise RuntimeError("checkpoint identifiers were reused")
        return {
            "schema_version": 1,
            "passed": True,
            "machines": 2,
            "streams": stream_count,
            "checkpoints": len(checkpoints),
            "conflicts": 0,
            "invariants": [
                "exact-title-restore",
                "ordered-baseline-and-delta",
                "idempotent-repeated-restore",
                "unique-checkpoint-identifiers",
                "valid-audit-on-both-machines",
            ],
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the dependency-free two-machine context synchronization acceptance."
    )
    parser.add_argument("--streams", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run_acceptance(args.streams)
    except (ValueError, RuntimeError, context_sync.ContextSyncError) as error:
        if args.json:
            print(json.dumps({"schema_version": 1, "passed": False, "error": str(error)}))
        else:
            print(f"Acceptance failed: {error}")
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"Acceptance passed: {result['machines']} machines, "
            f"{result['streams']} streams, {result['checkpoints']} checkpoints"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

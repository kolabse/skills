from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS_CLI_VERSION = "1.5.22"
BASELINE_TAG = "v1.0.0"
sys.path.insert(0, str(ROOT / "scripts"))
from manage_installed_skills import doctor, migrate, update_skills  # noqa: E402
from smoke_install import catalog_skills  # noqa: E402


class UpgradeError(RuntimeError):
    pass


def run(command: list[str], cwd: Path, timeout: int, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise UpgradeError(
            f"Command failed ({result.returncode}): {' '.join(command)}: "
            f"{(result.stdout + result.stderr)[-1500:]}"
        )
    return result.stdout


def configure_identity(git: str, project: Path, timeout: int) -> None:
    run([git, "init"], project, timeout)
    run([git, "config", "user.name", "Upgrade Test"], project, timeout)
    run([git, "config", "user.email", "upgrade@example.test"], project, timeout)
    (project / "tracked.txt").write_text("fixture\n", encoding="utf-8")
    run([git, "add", "tracked.txt"], project, timeout)
    run([git, "commit", "-m", "fixture"], project, timeout)


def write_legacy_configuration(project: Path, telegram_path: Path, python: str) -> None:
    verify = project / ".agents/verify-before-push"
    verify.mkdir(parents=True)
    (verify / "config.json").write_text(
        json.dumps(
            {
                "version": 1,
                "repositories": [
                    {
                        "name": "project",
                        "path": ".",
                        "require_clean": False,
                        "require_upstream_current": False,
                    }
                ],
                "checks": [
                    {"name": "fixture", "cwd": ".", "command": [python, "-c", "pass"]}
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    cloud = project / ".agents/operate-yandex-cloud"
    cloud.mkdir(parents=True)
    (cloud / "project.yaml").write_text(
        'version: 1\ncloud_id: "legacy-cloud"\nyc_profile: "legacy-profile"\n',
        encoding="utf-8",
    )
    telegram_path.parent.mkdir(parents=True)
    telegram_path.write_text(
        '{"bot_token":"fixture-token","chat_id":"123"}\n', encoding="utf-8"
    )


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_for_port(port: int, process: subprocess.Popen[bytes]) -> None:
    for _ in range(100):
        if process.poll() is not None:
            raise UpgradeError("local Git fixture server stopped unexpectedly")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)
    raise UpgradeError("local Git fixture server did not start")


def normalized_manifest(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        content = path.read_bytes()
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            content = content.replace(b"\r\n", b"\n")
        result[path.relative_to(root).as_posix()] = hashlib.sha256(content).hexdigest()
    return result


def verify_updated_installation(source: Path, project: Path, names: list[str]) -> None:
    installed = project / ".agents/skills"
    actual_names = sorted(path.name for path in installed.iterdir() if path.is_dir())
    missing_names = sorted(set(names) - set(actual_names))
    if missing_names:
        raise UpgradeError(f"Updated collection skills are missing: {missing_names}")
    for name in names:
        expected = normalized_manifest(source / "skills" / name)
        actual = normalized_manifest(installed / name)
        if expected != actual:
            raise UpgradeError(f"Updated {name} does not match candidate after LF normalization")
    lock = json.loads((project / "skills-lock.json").read_text(encoding="utf-8"))
    entries = lock.get("skills") if isinstance(lock, dict) else None
    if not isinstance(entries, dict) or not set(names).issubset(entries):
        raise UpgradeError("Updated skills lock is missing collection entries")
    for name in names:
        digest = entries[name].get("computedHash") if isinstance(entries[name], dict) else None
        if not isinstance(digest, str) or len(digest) != 64:
            raise UpgradeError(f"Updated lock hash is invalid for {name}")


def run_upgrade(source: Path, baseline: str, cli_version: str, timeout: int) -> None:
    git = shutil.which("git")
    npx = shutil.which("npx")
    python = shutil.which("python") or sys.executable
    if not git or not npx:
        raise UpgradeError("git and npx are required")
    candidate = run([git, "rev-parse", "HEAD"], source, timeout).strip()
    with tempfile.TemporaryDirectory(prefix="kolabse-skills-upgrade-") as directory:
        root = Path(directory)
        remote = root / "source.git"
        project = root / "project"
        telegram = root / "telegram/config.json"
        project.mkdir()
        baseline_commit = run([git, "rev-list", "-n", "1", baseline], source, timeout).strip()
        run([git, "clone", "--bare", str(source), str(remote)], root, timeout)
        run([git, "--git-dir", str(remote), "update-ref", "refs/heads/main", baseline_commit], root, timeout)
        run([git, "--git-dir", str(remote), "symbolic-ref", "HEAD", "refs/heads/main"], root, timeout)
        port = free_port()
        daemon = subprocess.Popen(
            [
                git,
                "daemon",
                "--reuseaddr",
                "--export-all",
                "--base-path-relaxed",
                "--listen=127.0.0.1",
                f"--port={port}",
                f"--base-path={root}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        wait_for_port(port, daemon)
        source_url = f"git://127.0.0.1:{port}/source.git"
        environment = os.environ.copy()
        environment["DISABLE_TELEMETRY"] = "1"
        environment["TELEGRAM_NOTIFY_CONFIG"] = str(telegram)
        try:
            run(
                [
                    npx,
                    "--yes",
                    f"skills@{cli_version}",
                    "add",
                    source_url,
                    "--skill",
                    "*",
                    "--agent",
                    "codex",
                    "--yes",
                    "--copy",
                ],
                project,
                timeout,
                environment,
            )
            lock_path = project / "skills-lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            unrelated_entry = {
                "source": "fixture/unrelated-skills",
                "sourceType": "github",
                "computedHash": "a" * 64,
            }
            lock["skills"]["unrelated-fixture-skill"] = unrelated_entry
            lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
            unrelated_root = project / ".agents/skills/unrelated-fixture-skill"
            unrelated_root.mkdir(parents=True)
            unrelated_file = unrelated_root / "SKILL.md"
            unrelated_file.write_text("fixture must remain unchanged\n", encoding="utf-8")
            configure_identity(git, project, timeout)
            write_legacy_configuration(project, telegram, python)
            run([git, "--git-dir", str(remote), "update-ref", "refs/heads/main", candidate], root, timeout)
            previous_telemetry = os.environ.get("DISABLE_TELEMETRY")
            os.environ["DISABLE_TELEMETRY"] = "1"
            try:
                update_skills(
                    project,
                    [],
                    "project",
                    cli_version,
                    True,
                    timeout,
                    adopt_legacy=True,
                    trusted_development_sources={source_url: source},
                )
            finally:
                if previous_telemetry is None:
                    os.environ.pop("DISABLE_TELEMETRY", None)
                else:
                    os.environ["DISABLE_TELEMETRY"] = previous_telemetry
            updated_lock = json.loads(lock_path.read_text(encoding="utf-8"))
            if updated_lock["skills"].get("unrelated-fixture-skill") != unrelated_entry:
                raise UpgradeError("Collection update changed an unrelated lock entry")
            if unrelated_file.read_text(encoding="utf-8") != "fixture must remain unchanged\n":
                raise UpgradeError("Collection update changed an unrelated installed skill")
            verify_updated_installation(source, project, catalog_skills(source))
            previous_config_env = os.environ.get("TELEGRAM_NOTIFY_CONFIG")
            os.environ["TELEGRAM_NOTIFY_CONFIG"] = str(telegram)
            try:
                migration = migrate(project, True, timeout)
            finally:
                if previous_config_env is None:
                    os.environ.pop("TELEGRAM_NOTIFY_CONFIG", None)
                else:
                    os.environ["TELEGRAM_NOTIFY_CONFIG"] = previous_config_env
        finally:
            daemon.terminate()
            try:
                daemon.wait(timeout=5)
            except subprocess.TimeoutExpired:
                daemon.kill()
                daemon.wait(timeout=5)
        migrated = {item["skill"] for item in migration["migrations"]}
        if migrated != {"verify-before-push", "operate-yandex-cloud", "notify-via-telegram"}:
            raise UpgradeError(f"Unexpected migrated skills: {sorted(migrated)}")
        state = doctor(project, {source_url: source})
        if not state["healthy"]:
            raise UpgradeError(f"Doctor failed after update: {state['problems']}")
        expected_version = json.loads(
            (source / ".codex-plugin/plugin.json").read_text(encoding="utf-8")
        )["version"]
        versions = {item["version"] for item in state["skills"]}
        if versions != {expected_version}:
            raise UpgradeError(f"Installed versions do not match {expected_version}: {versions}")
        if "version: 3" not in (project / ".agents/operate-yandex-cloud/project.yaml").read_text(encoding="utf-8"):
            raise UpgradeError("Yandex Cloud configuration was not migrated to version 3")
        if json.loads(telegram.read_text(encoding="utf-8")).get("version") != 1:
            raise UpgradeError("Telegram configuration was not migrated to version 1")
    print(f"Upgraded all skills from {baseline} to {candidate[:12]} and migrated legacy configuration.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test consumer skill updates.")
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--baseline", default=BASELINE_TAG)
    parser.add_argument("--cli-version", default=SKILLS_CLI_VERSION)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args(argv)
    try:
        run_upgrade(args.source.resolve(), args.baseline, args.cli_version, args.timeout)
        return 0
    except (UpgradeError, OSError, UnicodeError, subprocess.SubprocessError) as error:
        print(f"UPGRADE_FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

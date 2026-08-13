from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "kolabse-skills"
ENTRY = {
    "name": PLUGIN_NAME,
    "source": {"source": "local", "path": f"./plugins/{PLUGIN_NAME}"},
    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
    "category": "Developer Tools",
}


class PluginInstallError(RuntimeError):
    pass


def load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as error:
        raise PluginInstallError(f"{label} is invalid: {path}: {error}") from error
    if not isinstance(value, dict):
        raise PluginInstallError(f"{label} must contain a JSON object: {path}")
    return value


def marketplace_payload(existing: dict[str, Any]) -> dict[str, Any]:
    if not existing:
        existing = {
            "name": "personal",
            "interface": {"displayName": "Personal"},
            "plugins": [],
        }
    name = existing.get("name")
    plugins = existing.get("plugins")
    interface = existing.get("interface")
    if not isinstance(name, str) or not name:
        raise PluginInstallError("marketplace name must be a non-empty string")
    if not isinstance(interface, dict):
        raise PluginInstallError("marketplace interface must be an object")
    if not isinstance(plugins, list) or not all(isinstance(item, dict) for item in plugins):
        raise PluginInstallError("marketplace plugins must be an object list")
    retained = [item for item in plugins if item.get("name") != PLUGIN_NAME]
    return {**existing, "plugins": [*retained, ENTRY]}


def cachebusted_manifest(source: Path) -> tuple[dict[str, Any], str]:
    manifest = load_object(source / ".codex-plugin/plugin.json", "plugin manifest")
    if manifest.get("name") != PLUGIN_NAME:
        raise PluginInstallError(f"plugin manifest name must be {PLUGIN_NAME!r}")
    version = manifest.get("version")
    if not isinstance(version, str) or not version:
        raise PluginInstallError("plugin manifest version is required")
    base = version.split("+", 1)[0]
    stamp = datetime.now(timezone.utc).strftime("local-%Y%m%d-%H%M%S")
    installed_version = f"{base}+codex.{stamp}"
    manifest["version"] = installed_version
    return manifest, installed_version


def safe_replace_directory(source: Path, destination: Path) -> None:
    parent = destination.parent.resolve()
    destination = destination.resolve()
    if destination.parent != parent or destination.name != PLUGIN_NAME:
        raise PluginInstallError(f"unsafe plugin destination: {destination}")
    parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{PLUGIN_NAME}-", dir=parent))
    backup = parent / f".{PLUGIN_NAME}.previous"
    try:
        shutil.copytree(source / ".codex-plugin", stage / ".codex-plugin")
        shutil.copytree(source / "skills", stage / "skills")
        manifest, _ = cachebusted_manifest(source)
        (stage / ".codex-plugin/plugin.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if backup.exists():
            shutil.rmtree(backup)
        if destination.exists():
            os.replace(destination, backup)
        os.replace(stage, destination)
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if not destination.exists() and backup.exists():
            os.replace(backup, destination)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def save_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=".marketplace-", suffix=".json", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def install(source: Path, plugin_parent: Path, marketplace_path: Path) -> dict[str, Any]:
    source = source.resolve()
    destination = plugin_parent.expanduser().resolve() / PLUGIN_NAME
    marketplace_path = marketplace_path.expanduser().resolve()
    payload = marketplace_payload(load_object(marketplace_path, "marketplace"))
    safe_replace_directory(source, destination)
    save_atomic(marketplace_path, payload)
    installed = load_object(destination / ".codex-plugin/plugin.json", "installed plugin manifest")
    return {
        "plugin": PLUGIN_NAME,
        "version": installed["version"],
        "plugin_path": str(destination),
        "marketplace_path": str(marketplace_path),
        "marketplace": payload["name"],
    }


def activate(state: dict[str, Any], timeout: int) -> None:
    codex = shutil.which("codex")
    if not codex:
        raise PluginInstallError("codex CLI is required for --activate")
    command = [codex, "plugin", "add", f"{PLUGIN_NAME}@{state['marketplace']}"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as error:
        raise PluginInstallError(f"could not activate plugin: {error}") from error
    if result.returncode != 0:
        raise PluginInstallError(f"plugin activation failed: {(result.stdout + result.stderr)[-1000:]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install or update the local personal kolabse plugin.")
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--plugin-parent", type=Path, default=Path.home() / "plugins")
    parser.add_argument(
        "--marketplace-path",
        type=Path,
        default=Path.home() / ".agents/plugins/marketplace.json",
    )
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    try:
        state = install(args.source, args.plugin_parent, args.marketplace_path)
        if args.activate:
            activate(state, args.timeout)
        print(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) if args.json else f"Installed {state['plugin']} {state['version']} at {state['plugin_path']}")
        return 0
    except (PluginInstallError, OSError, UnicodeError) as error:
        print(f"PLUGIN_INSTALL_FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

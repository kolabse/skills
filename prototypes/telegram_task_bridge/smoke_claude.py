"""Optional Windows Claude CLI smoke, isolated from user config and Telegram.

Pass --claude a Claude executable and --python an interpreter with requirements
installed. Exercises real CLI user-scope registration/health/removal against the
offline server directly. It does not exercise the Windows controller, scheduler,
Claude model session, authentication, real replies, or Telegram acceptance.
No dependencies are downloaded and no real configuration is changed.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def smoke(claude, python):
    if os.name != "nt":
        raise RuntimeError("This optional smoke is Windows-only.")
    claude, python = Path(claude).resolve(strict=True), Path(python).resolve(strict=True)
    source = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="bridge Claude проверка ") as folder:
        root = Path(folder)
        config = root / "isolated config"
        config.mkdir()
        runtime = root / "runtime с пробелами"
        runtime.mkdir()
        for name in ("server.py", "store.py", "telegram.py", "receiver.py"):
            shutil.copy2(source / name, runtime / name)
        env = os.environ.copy()
        for key in list(env):
            if key.upper().startswith(("CLAUDE_", "ANTHROPIC_", "TELEGRAM_")):
                del env[key]
        env.update(CLAUDE_CONFIG_DIR=str(config), LOCALAPPDATA=str(root / "local"),
                   USERPROFILE=str(root), HOME=str(root),
                   CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")

        def call(*args, success=True):
            result = subprocess.run([str(claude), *args], cwd=root, env=env,
                                    capture_output=True, encoding="utf-8", errors="replace",
                                    timeout=60)
            if (result.returncode == 0) != success:
                raise RuntimeError("Unexpected CLI result for " + " ".join(args[:2]) + ": "
                                   + result.stdout + result.stderr)
            return result.stdout + result.stderr

        def entries():
            return json.loads((config / ".claude.json").read_text(encoding="utf-8"))["mcpServers"]

        version = call("--version").strip()
        name = "telegram-task-bridge"
        server_args = [str(runtime / "server.py"), "serve", "--offline", "--db",
                       str(root / "messages тест.sqlite3"), "--agent", "claude-code"]
        call("mcp", "add", "--scope", "user", "--transport", "stdio", name,
             "--", str(python), *server_args)
        saved = entries()[name]
        assert saved["command"] == str(python) and saved["args"] == server_args
        call("mcp", "add", "--scope", "user", "--transport", "stdio", "unrelated",
             "--", str(python), "-c", "pass")
        before = entries()
        call("mcp", "add", "--scope", "user", "--transport", "stdio", name,
             "--", str(python), "-c", "pass", success=False)
        assert entries() == before, "Duplicate registration modified configuration"
        health = call("mcp", "get", name)
        assert "Connected" in health, "Offline server not connected: " + health
        call("mcp", "remove", name, "--scope", "user")
        remaining = entries()
        assert name not in remaining and remaining["unrelated"] == before["unrelated"]
        return {"claude_version": version, "offline_stdio_connected": True,
                "unicode_space_argv_preserved": True, "duplicate_refused_preserved": True,
                "scoped_removal_preserved_unrelated": True,
                "real_telegram_or_model_session_tested": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude", required=True, help="Absolute Claude CLI executable")
    parser.add_argument("--python", required=True, help="Python with bridge requirements installed")
    args = parser.parse_args()
    print(json.dumps(smoke(args.claude, args.python), indent=2))

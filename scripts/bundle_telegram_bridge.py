"""Copy the reviewed bridge allowlist into the normally updated notification skill."""
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("prototypes/telegram_task_bridge")
TARGET = Path("skills/notify-via-telegram/scripts/task_bridge")
RUNTIME = ("server.py", "store.py", "telegram.py", "receiver.py", "requirements.txt",
           "manage_receiver.ps1", "plugin_control.ps1")
INPUTS = {**{f"runtime/{name}": name for name in RUNTIME},
          "setup.ps1": "plugin_setup.ps1", "installer.py": "installer.py",
          "configure_telegram.ps1": "configure_telegram.ps1"}


def synchronize(root=ROOT, check=False):
    root = Path(root)
    target = root / TARGET
    expected = {name: (root / SOURCE / source).read_bytes().replace(b"\r\n", b"\n")
                for name, source in INPUTS.items()}
    actual = {path.relative_to(target).as_posix() for path in target.rglob("*")
              if path.is_file() and "__pycache__" not in path.parts}
    extra = actual - expected.keys()
    if extra:
        raise ValueError("Unexpected files in the collection bridge bundle: " + ", ".join(sorted(extra)))
    changed = []
    for name, content in expected.items():
        path = target / name
        if not path.is_file() or path.read_bytes().replace(b"\r\n", b"\n") != content:
            changed.append(name)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
    return changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changes = synchronize(check=args.check)
    if changes:
        print(("Outdated: " if args.check else "Updated: ") + ", ".join(changes))
    raise SystemExit(1 if args.check and changes else 0)

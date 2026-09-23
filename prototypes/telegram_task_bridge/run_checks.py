"""Run prototype checks in a fresh environment, without live Telegram state."""
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def main():
    source = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="telegram-bridge-checks-") as folder:
        root = Path(folder)
        venv.create(root / "venv", with_pip=True)
        python = root / "venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                        "-r", str(source / "requirements.txt")], check=True, timeout=300)
        subprocess.run([str(python), "-m", "unittest", "discover", "-s", str(source),
                        "-p", "test_*.py", "-v"], check=True, timeout=180)


if __name__ == "__main__":
    main()

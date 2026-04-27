from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def _script_path() -> Path:
    return Path(__file__).resolve().parent / "assets" / "orca.sh"


def main() -> int:
    script = _script_path()
    if not script.is_file():
        print(f"orca launcher missing: {script}", file=sys.stderr)
        return 1

    bash_path = shutil.which("bash")
    if not bash_path:
        print("orca launcher requires 'bash' in PATH", file=sys.stderr)
        return 1

    try:
        completed = subprocess.run([bash_path, str(script), *sys.argv[1:]], check=False)  # noqa: S603 — intentional passthrough of CLI args to bundled launcher
    except (FileNotFoundError, PermissionError, OSError) as exc:
        print(f"Failed to launch orca: {exc}", file=sys.stderr)
        return 1
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

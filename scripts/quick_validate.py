import os
import pathlib
import subprocess
import sys


root = pathlib.Path(__file__).resolve().parents[1]
explicit = sys.argv[1] if len(sys.argv) > 1 else os.getenv("AD3_QUICK_VALIDATE_PATH")
codex_home = pathlib.Path(os.getenv("CODEX_HOME", pathlib.Path.home() / ".codex"))
tool = pathlib.Path(explicit) if explicit else codex_home / "skills" / ".system" / "skill-creator" / "scripts" / "quick_validate.py"
if not tool.is_file():
    print("quick validator not found; set AD3_QUICK_VALIDATE_PATH, pass its path as the first argument, or set CODEX_HOME.", file=sys.stderr)
    raise SystemExit(2)
raise SystemExit(subprocess.call([sys.executable, str(tool), str(root / "skill" / "ad3-whatsapp-evolution")]))

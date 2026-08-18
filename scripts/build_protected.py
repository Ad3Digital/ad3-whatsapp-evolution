"""Build-only helper: PyInstaller and cryptography are intentionally optional development dependencies."""
import argparse, pathlib, subprocess, sys
p=argparse.ArgumentParser();p.add_argument('--public-key',required=True);a=p.parse_args(); key=pathlib.Path(a.public_key).read_text(encoding='utf8'); target=pathlib.Path('src/ad3_evolution/_embedded_key.py')
try:
 target.write_text('PUBLIC_KEY_PEM='+repr(key)+'\n',encoding='utf8')
 raise SystemExit(subprocess.call([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--name','ad3-evolution','--paths','src','src/ad3_evolution/protected_entry.py']))
finally:
 if target.exists(): target.unlink()

"""PyInstaller entrypoint; public key is injected at protected build time, never private material."""
import pathlib, sys, argparse
from ad3_evolution.runtime import require_license
from ad3_evolution.cli import main
try: from ad3_evolution._embedded_key import PUBLIC_KEY_PEM
except ImportError: raise SystemExit("protected runtime has no embedded public key")
if len(sys.argv)>1 and sys.argv[1]=='verify-package':
 p=argparse.ArgumentParser();p.add_argument('verify-package');p.add_argument('--root',required=True);a=p.parse_args();require_license(PUBLIC_KEY_PEM.encode(),pathlib.Path(a.root).resolve());print('package verified');raise SystemExit(0)
require_license(PUBLIC_KEY_PEM.encode(),pathlib.Path(sys.executable).resolve().parent)
raise SystemExit(main())

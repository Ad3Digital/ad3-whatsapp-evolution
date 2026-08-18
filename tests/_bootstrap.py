import sys
from pathlib import Path
src=str(Path(__file__).resolve().parents[1]/'src')
if src not in sys.path: sys.path.insert(0,src)

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os

@dataclass(frozen=True)
class Config:
    mode: str = "demo"
    base_url: str = "http://127.0.0.1:8080"
    api_key: str = ""
    database: Path = Path("ad3_evolution.sqlite3")
    timeout: float = 10.0

    @classmethod
    def load(cls, mode: str | None = None, state_dir: str | None = None) -> "Config":
        candidates=[Path(os.getenv("AD3_EVOLUTION_CONFIG",""))] if os.getenv("AD3_EVOLUTION_CONFIG") else []
        candidates += [Path(os.sys.executable).resolve().parent/'.env',Path.cwd()/'.env']
        values={}
        for file in candidates:
            if file.is_file():
                for line in file.read_text(encoding="utf8").splitlines():
                    if line and not line.lstrip().startswith("#") and "=" in line:
                        k,v=line.split("=",1); k=k.strip()
                        if k in {"AD3_EVOLUTION_MODE","EVOLUTION_BASE_URL","EVOLUTION_API_KEY","AD3_EVOLUTION_STATE_DIR"}: values.setdefault(k,v.strip().strip('"'))
        base = Path(state_dir or os.getenv("AD3_EVOLUTION_STATE_DIR") or values.get("AD3_EVOLUTION_STATE_DIR") or (Path(os.getenv("LOCALAPPDATA","."))/"AD3Evolution/state"))
        base.mkdir(parents=True, exist_ok=True)
        selected = mode or os.getenv("AD3_EVOLUTION_MODE") or values.get("AD3_EVOLUTION_MODE","demo")
        if selected not in {"demo", "remote", "local"}: raise ValueError("mode must be demo, remote or local")
        url=os.getenv("EVOLUTION_BASE_URL") or values.get("EVOLUTION_BASE_URL", "http://127.0.0.1:8080"); key=os.getenv("EVOLUTION_API_KEY") or values.get("EVOLUTION_API_KEY","")
        if selected in {"remote","local"} and (not url or not key): raise ValueError("remote/local require EVOLUTION_BASE_URL and EVOLUTION_API_KEY in environment or local .env")
        return cls(selected,url,key,base / "state.sqlite3",float(os.getenv("EVOLUTION_TIMEOUT","10")))

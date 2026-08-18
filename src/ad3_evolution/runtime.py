"""Protected builds fail closed unless their adjacent signed manifest verifies."""
from __future__ import annotations
import json, os, pathlib
from .license import verify_manifest, verify_package, LicenseError

def require_license(public_key: bytes, root: pathlib.Path | None=None, dev: bool=False) -> dict:
 if dev and os.getenv("AD3_EVOLUTION_ALLOW_DEV_UNLICENSED") == "1": return {"development":True}
 root=root or pathlib.Path(__file__).resolve().parent
 try:
  manifest=json.loads((root/'LICENSE-MANIFEST.json').read_text(encoding='utf8')); sig=(root/'LICENSE-MANIFEST.sig').read_text(encoding='utf8').strip()
  if not verify_manifest(manifest,sig,public_key): raise LicenseError("invalid")
  verify_package(manifest,root)
  return manifest
 except Exception as e: raise LicenseError("protected runtime requires a valid signed LICENSE-MANIFEST.json") from e

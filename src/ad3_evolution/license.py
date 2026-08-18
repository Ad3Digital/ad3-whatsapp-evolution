from __future__ import annotations
import base64,json,hashlib,pathlib
class LicenseError(RuntimeError): pass
REQUIRED_MANIFEST={"product","name","email","license_id","issued_at","license_terms_version","artifact_hashes"}
EXCLUDED_ARTIFACTS={"LICENSE-MANIFEST.json","LICENSE-MANIFEST.sig","AD3-WATERMARK.json","CHECKSUMS.sha256"}
def sha256_file(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(65536),b''): h.update(block)
 return h.hexdigest()
def safe_relative(name):
 p=pathlib.PurePosixPath(name)
 return (bool(name) and not p.is_absolute() and '..' not in p.parts and
         all(part not in {'', '.'} for part in p.parts) and '\\' not in name and
         ':' not in name and not name.startswith('./') and '/./' not in name and
         not any(ord(char) < 32 for char in name))
def verify_package(manifest:dict, root:pathlib.Path)->bool:
 hashes=manifest.get('artifact_hashes')
 if not isinstance(hashes,dict) or not hashes: raise LicenseError('artifact inventory missing')
 if any(not safe_relative(k) or not isinstance(v,str) or len(v)!=64 for k,v in hashes.items()): raise LicenseError('unsafe artifact inventory')
 actual={k:sha256_file(root/k) for k in hashes if (root/k).is_file()}
 if set(actual)!=set(hashes): raise LicenseError('signed artifact missing')
 if any(actual[k]!=v for k,v in hashes.items()): raise LicenseError('artifact hash differs')
 return True
def verify_manifest(manifest:dict, signature_b64:str, public_pem:bytes)->bool:
 try:
  if not isinstance(manifest,dict) or not REQUIRED_MANIFEST.issubset(manifest) or any(not str(manifest[x]).strip() for x in REQUIRED_MANIFEST-{'artifact_hashes'}): raise LicenseError("license manifest schema invalid")
  if manifest["product"]!="AD3 WhatsApp Evolution": raise LicenseError("license product invalid")
  from cryptography.hazmat.primitives import serialization
  from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
  from .security import canonical
  key=serialization.load_pem_public_key(public_pem); key.verify(base64.b64decode(signature_b64),canonical(manifest).encode()); return True
 except ImportError as e: raise LicenseError("cryptography is required only in protected build/runtime") from e
 except Exception as e: raise LicenseError("license manifest verification failed") from e

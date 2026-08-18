"""Private operator utility. Keys must be supplied as external paths; never package them."""
import argparse,base64,json,pathlib,os,hashlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from ad3_evolution.security import canonical
p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True); g=sub.add_parser('generate'); g.add_argument('--private-out',required=True); g.add_argument('--public-out',required=True); s=sub.add_parser('sign'); s.add_argument('--private-key',required=True); s.add_argument('--manifest',required=True); s.add_argument('--signature-out',required=True); m=sub.add_parser('manifest'); [m.add_argument('--'+x,required=True) for x in ('name','email','license-id','issued-at','terms-version','binary','project-root','out')]; a=p.parse_args()
if a.cmd=='generate':
 if pathlib.Path(a.private_out).exists() or pathlib.Path(a.public_out).exists(): raise SystemExit('refusing to overwrite key material')
 key=Ed25519PrivateKey.generate(); pathlib.Path(a.private_out).write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())); pathlib.Path(a.public_out).write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)); os.chmod(a.private_out,0o600)
elif a.cmd=='sign':
 manifest=json.loads(pathlib.Path(a.manifest).read_text()); required={'product','name','email','license_id','issued_at','license_terms_version'}
 if not required.issubset(manifest): raise SystemExit('manifest schema invalid')
 if pathlib.Path(a.signature_out).exists(): raise SystemExit('refusing to overwrite signature')
 key=serialization.load_pem_private_key(pathlib.Path(a.private_key).read_bytes(),password=None); pathlib.Path(a.signature_out).write_text(base64.b64encode(key.sign(canonical(manifest).encode())).decode())
else:
 out=pathlib.Path(a.out)
 if out.exists(): raise SystemExit('refusing to overwrite manifest')
 root=pathlib.Path(a.project_root); binary=pathlib.Path(a.binary); blocked={'.env','.git','.venv','__pycache__','src','tests','logs','build','dist'}
 files={'ad3-evolution.exe':binary}
 for name in ('LICENSE.md','THIRD_PARTY_NOTICES.md','docs/WEBINAR_GUIDE.md'):
  files[name]=root/name
 for folder in ('skill/ad3-whatsapp-evolution','install','deploy/local'):
  for f in (root/folder).rglob('*'):
   if f.is_file() and not any(x in blocked for x in f.relative_to(root).parts): files[f.relative_to(root).as_posix()]=f
 digest=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
 manifest={'product':'AD3 WhatsApp Evolution','name':a.name,'email':a.email,'license_id':a.license_id,'issued_at':a.issued_at,'license_terms_version':a.terms_version,'artifact_hashes':{k:digest(v) for k,v in sorted(files.items())}}
 out.write_text(json.dumps(manifest,sort_keys=True,ensure_ascii=False),encoding='utf8')

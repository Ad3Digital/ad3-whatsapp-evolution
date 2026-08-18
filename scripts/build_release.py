"""Fail-closed personalized release builder; accepts only external protected binary and signed identity."""
import argparse,hashlib,json,pathlib,zipfile
from ad3_evolution.license import verify_manifest,LicenseError
root=pathlib.Path(__file__).resolve().parents[1]; p=argparse.ArgumentParser()
for x in ('name','email','license-id','binary','manifest','signature','public-key','out'): p.add_argument('--'+x,required=True)
a=p.parse_args(); binary=pathlib.Path(a.binary); manifest_path=pathlib.Path(a.manifest); signature=pathlib.Path(a.signature); public=pathlib.Path(a.public_key)
if not binary.is_file(): raise SystemExit('closed: prebuilt protected binary is required')
try: manifest=json.loads(manifest_path.read_text(encoding='utf8')); ok=verify_manifest(manifest,signature.read_text(encoding='utf8').strip(),public.read_bytes())
except (OSError,ValueError,LicenseError): raise SystemExit('closed: valid signed license is required')
identity={'name':a.name,'email':a.email,'license_id':a.license_id}
if not ok or any(manifest.get(k)!=v for k,v in identity.items()): raise SystemExit('closed: arguments must exactly match signed manifest identity')
blocked={'.env','.git','.venv','__pycache__','src','tests','logs','build','dist'}
def allowed(path): return not any(x in blocked or path.name.endswith(('.db','.sqlite3','.key','.pem','.pyc')) for x in path.parts)
entries=[binary,manifest_path,signature,root/'LICENSE.md',root/'THIRD_PARTY_NOTICES.md',root/'docs/WEBINAR_GUIDE.md']
for folder in ('skill/ad3-whatsapp-evolution','install','deploy/local'):
 entries += [x for x in (root/folder).rglob('*') if x.is_file() and allowed(x.relative_to(root))]
watermark={'licensed_to':identity,'manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
out=pathlib.Path(a.out)
if out.exists(): raise SystemExit('closed: refusing to overwrite release')
out.parent.mkdir(parents=True,exist_ok=True)
payload={'ad3-evolution.exe':binary.read_bytes(),'LICENSE-MANIFEST.json':manifest_path.read_bytes(),'LICENSE-MANIFEST.sig':signature.read_bytes(),'AD3-WATERMARK.json':json.dumps(watermark,ensure_ascii=False,sort_keys=True).encode()}
for f in entries[3:]: payload[f.relative_to(root).as_posix()]=f.read_bytes()
actual={k:hashlib.sha256(v).hexdigest() for k,v in payload.items() if k not in {'LICENSE-MANIFEST.json','LICENSE-MANIFEST.sig','AD3-WATERMARK.json','CHECKSUMS.sha256'}}
if actual != manifest.get('artifact_hashes'): raise SystemExit('closed: signed artifact inventory differs from release')
payload['CHECKSUMS.sha256']='\n'.join(f'{hashlib.sha256(data).hexdigest()}  {name}' for name,data in sorted(payload.items())).encode()
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
 for name,data in payload.items(): z.writestr(name,data)

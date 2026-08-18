import _bootstrap
import json,os,pathlib,subprocess,sys,tempfile,unittest,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]; ENV={**os.environ,'PYTHONPATH':str(ROOT/'src')}
class ReleaseE2E(unittest.TestCase):
 def test_signed_release_and_tamper(self):
  with tempfile.TemporaryDirectory() as d:
   d=pathlib.Path(d); priv,pub=d/'p.pem',d/'u.pem'; manifest=d/'m.json';sig=d/'m.sig'; binary=d/'ad3-evolution.exe';out=d/'release.zip';binary.write_bytes(b'fake')
   self.assertEqual(subprocess.call([sys.executable,str(ROOT/'scripts/license_private.py'),'generate','--private-out',str(priv),'--public-out',str(pub)],env=ENV),0)
   self.assertEqual(subprocess.call([sys.executable,str(ROOT/'scripts/license_private.py'),'manifest','--name','N','--email','n@test','--license-id','L','--issued-at','2026-01-01T00:00:00Z','--terms-version','1','--binary',str(binary),'--project-root',str(ROOT),'--out',str(manifest)],env=ENV),0)
   self.assertEqual(subprocess.call([sys.executable,str(ROOT/'scripts/license_private.py'),'sign','--private-key',str(priv),'--manifest',str(manifest),'--signature-out',str(sig)],env=ENV),0)
   cmd=[sys.executable,str(ROOT/'scripts/build_release.py'),'--name','N','--email','n@test','--license-id','L','--binary',str(binary),'--manifest',str(manifest),'--signature',str(sig),'--public-key',str(pub),'--out',str(out)]
   self.assertEqual(subprocess.call(cmd,env=ENV),0)
   with zipfile.ZipFile(out) as z: names=z.namelist();self.assertIn('CHECKSUMS.sha256',names);self.assertIn('install/Install-AD3Evolution.ps1',names);self.assertFalse(any(n.startswith('src/') or n.endswith('.env') or n.endswith('.pem') for n in names))
   manifest.write_text('{}'); self.assertNotEqual(subprocess.call(cmd[:-1]+[str(d/'bad.zip')],env=ENV),0)

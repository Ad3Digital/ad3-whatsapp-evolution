import hashlib,os,pathlib,subprocess,tempfile,unittest,zipfile

class ReleaseApplySmoke(unittest.TestCase):
 def test_demo_apply_from_real_release(self):
  raw=os.environ.get('AD3_RELEASE_ZIP')
  expected=os.environ.get('AD3_RELEASE_SHA256','').upper()
  if not raw:
   self.skipTest('set AD3_RELEASE_ZIP for the real release installation smoke test')
  archive=pathlib.Path(raw).resolve()
  self.assertTrue(archive.is_file())
  self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest().upper(),expected)
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d); package=root/'package'; target=root/'local/AD3Evolution'; codex=root/'codex'
   with zipfile.ZipFile(archive) as z:z.extractall(package)
   env={**os.environ,'LOCALAPPDATA':str(root/'local'),'USERPROFILE':str(root/'profile'),'CODEX_HOME':str(codex)}
   command=['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(package/'install/Install-AD3Evolution.ps1'),'-Mode','demo','-Apply','-NonInteractive','-PackageRoot',str(package),'-PackageArchive',str(archive),'-ExpectedPackageSha256',expected,'-Destination',str(target)]
   result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=90)
   self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
   self.assertIn('Package installed',result.stdout)
   for name in ('ad3-evolution.exe','AD3-WATERMARK.json','LICENSE.md','THIRD_PARTY_NOTICES.md','CHECKSUMS.sha256','.env'):
    self.assertTrue((target/name).exists(),name)
   self.assertTrue((codex/'skills/ad3-whatsapp-evolution/SKILL.md').exists())

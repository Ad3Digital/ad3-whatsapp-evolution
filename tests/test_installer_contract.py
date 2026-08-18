import os,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]; INSTALL=ROOT/'install/Install-AD3Evolution.ps1'
class InstallerContract(unittest.TestCase):
 def test_diagnose_zero_write(self):
  with tempfile.TemporaryDirectory() as d:
   target=pathlib.Path(d)/'destination'; env={**os.environ,'LOCALAPPDATA':d,'CODEX_HOME':str(pathlib.Path(d)/'codex')}
   p=subprocess.run(['powershell','-NoProfile','-File',str(INSTALL),'-Mode','demo','-Diagnose','-Destination',str(target),'-PackageRoot',str(ROOT)],env=env,capture_output=True,text=True)
   self.assertEqual(p.returncode,0);self.assertFalse(target.exists());self.assertIn('zero writes',p.stdout)
 def test_no_secret_argument_and_resume_guard(self):
  text=INSTALL.read_text();self.assertIn('RemoteApiKey parameter is intentionally refused',text);self.assertIn('TotalHours -gt 24',text);self.assertNotIn('remoteApiKey=$RemoteApiKey',text)
 def test_allowlist_excludes_source(self):
  text=INSTALL.read_text();self.assertIn('$RequiredPackageItems',text);self.assertNotIn("Copy-Item (Join-Path $root '*')",text)
  for item in ('ad3-evolution.exe','AD3-WATERMARK.json','LICENSE.md','THIRD_PARTY_NOTICES.md'):
   self.assertIn(item,text)
 def test_trusted_archive_precedes_executable(self):
  text=INSTALL.read_text();trusted=text.index('Test-TrustedArchive $PackageArchive $ExpectedPackageSha256 $PackageRoot');execute=text.index("& (Join-Path $PackageRoot 'ad3-evolution.exe')")
  self.assertLess(trusted,execute);self.assertIn('Get-FileHash -LiteralPath $archiveFull',text);self.assertNotIn("SetEnvironmentVariable('Path','User')",text)
 def test_webinar_operational_coverage(self):
  guide=(ROOT/'docs/WEBINAR_GUIDE.md').read_text();self.assertGreaterEqual(len(guide.splitlines()),150)
  for term in ('-Diagnose','plan/apply','onboarding','backup','RESTORE','PURGE-VOLUMES','ligado e acordado','Get-FileHash','-ExpectedPackageSha256'):
   self.assertIn(term,guide)

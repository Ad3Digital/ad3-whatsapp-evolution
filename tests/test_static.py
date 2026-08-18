import pathlib, subprocess, sys, unittest, os, py_compile
ROOT=pathlib.Path(__file__).resolve().parents[1]
class StaticTests(unittest.TestCase):
 def test_compose_safe(self):
  x=(ROOT/'deploy/local/compose.yaml').read_text(); self.assertNotIn(':latest',x); self.assertNotIn('0.0.0.0:',x); self.assertNotIn('external: true',x)
 def test_ps_parses(self):
  for p in [ROOT/'install/Install-AD3Evolution.ps1',ROOT/'install/Manage-AD3Evolution.ps1']:
   cmd=['powershell','-NoProfile','-Command',"$t=$null;$e=$null;[System.Management.Automation.Language.Parser]::ParseFile('"+str(p)+"',[ref]$t,[ref]$e);if($e.Count){exit 1}"]
   self.assertEqual(subprocess.call(cmd),0)
 def test_release_fails_closed(self):
   p=subprocess.run([sys.executable,str(ROOT/'scripts/build_release.py'),'--name','A','--email','a@b.test','--license-id','L','--binary','missing','--manifest','missing','--signature','missing','--public-key','missing','--out',str(ROOT/'x.zip')],env={**os.environ,'PYTHONPATH':str(ROOT/'src')},capture_output=True,text=True); self.assertNotEqual(p.returncode,0); self.assertIn('closed',p.stderr+p.stdout)
 def test_all_python_sources_compile(self):
  for source in (ROOT/'src').rglob('*.py'):
   py_compile.compile(str(source),doraise=True)

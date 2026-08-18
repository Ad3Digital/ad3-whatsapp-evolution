import os, pathlib, shutil, subprocess, tempfile, unittest, zipfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
MANAGER=ROOT/'install'/'Manage-AD3Evolution.ps1'
COMPOSE=ROOT/'deploy'/'local'/'compose.yaml'

FAKE_DOCKER=r'''@echo off
setlocal EnableDelayedExpansion
set all=%*
echo %all% | findstr /C:"pg_dump" >nul && (echo -- fake postgres dump& exit /b 0)
echo %all% | findstr /C:" ps -q evolution" >nul && (echo fake-container& exit /b 0)
echo %all% | findstr /C:"compose version" >nul && (echo Docker Compose fake& exit /b 0)
echo %all% | findstr /C:"inspect fake-container" >nul && (echo [{"Mounts":[{"Destination":"/evolution/instances","Name":"fake_instances"}]}]& exit /b 0)
echo %all% | findstr /C:"run --rm" >nul && (
  if not "%AD3_EVOLUTION_BACKUP_TEMP%"=="" echo fake archive>"%AD3_EVOLUTION_BACKUP_TEMP%\instances.tgz"
  for %%A in (%*) do (
    set value=%%~A
    echo !value! | findstr /C:":/out" >nul && (set output=!value:~0,-5!& if not exist "!output!" mkdir "!output!"& echo fake archive>"!output!\instances.tgz")
  )
  exit /b 0
)
exit /b 0
'''

class ManagerFakeDocker(unittest.TestCase):
 def run_manager(self, sandbox, action, *extra):
  env={**os.environ,'PATH':str(sandbox/'bin')+';'+os.environ['PATH']}
  return subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(sandbox/'install'/'Manage-AD3Evolution.ps1'),'-Action',action,*extra],env=env,capture_output=True,text=True)
 def test_doctor_backup_and_guards_without_real_docker(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=pathlib.Path(tmp); (s/'install').mkdir(); (s/'deploy'/'local').mkdir(parents=True); (s/'bin').mkdir()
   shutil.copy2(MANAGER,s/'install'/'Manage-AD3Evolution.ps1'); shutil.copy2(COMPOSE,s/'deploy'/'local'/'compose.yaml'); (s/'.env').write_text('EVOLUTION_API_KEY=x\nPOSTGRES_PASSWORD=x\nREDIS_PASSWORD=x\n'); (s/'bin'/'docker.cmd').write_text(FAKE_DOCKER)
   doctor=self.run_manager(s,'doctor'); self.assertEqual(doctor.returncode,0,doctor.stderr)
   out=s/'backup.zip'; backup=self.run_manager(s,'backup','-BackupFile',str(out)); self.assertEqual(backup.returncode,0,backup.stderr); self.assertTrue(out.is_file())
   with zipfile.ZipFile(out) as z: self.assertIn('postgres.sql',z.namelist()); self.assertIn('instances.tgz',z.namelist()); self.assertNotIn('.env',z.namelist())
   restore=self.run_manager(s,'restore','-BackupFile',str(out)); self.assertNotEqual(restore.returncode,0); self.assertIn('RESTORE',restore.stderr+restore.stdout)
   purge=self.run_manager(s,'uninstall','-Purge'); self.assertNotEqual(purge.returncode,0); self.assertIn('PURGE-VOLUMES',purge.stderr+purge.stdout)

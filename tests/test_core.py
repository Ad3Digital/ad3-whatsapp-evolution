import _bootstrap
import pathlib, tempfile, threading, unittest, base64, sqlite3
from types import SimpleNamespace
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import MagicMock, patch
from ad3_evolution.store import Store, PlanError
from ad3_evolution.service import Service
from ad3_evolution.security import redact, validate_chat_jid
from ad3_evolution.client import EvolutionClient
from ad3_evolution.profiles import ROUTES
from ad3_evolution.license import verify_manifest, safe_relative
from ad3_evolution.cli import main as cli_main, parser

class CoreTests(unittest.TestCase):
 def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.store=Store(pathlib.Path(self.tmp.name)/'x.db'); self.s=Service(self.store,'demo')
 def tearDown(self): self.store.close(); self.tmp.cleanup()
 def test_demo_is_offline(self):
  with patch('urllib.request.urlopen',side_effect=AssertionError('network')): self.assertTrue(self.s.doctor()['ok']); self.assertEqual(len(self.s.instances()),3)
 def test_redaction(self):
  redacted=redact({'api_key':'secret','phone':'5511999999999','base64':'aGVsbG8=','flag':False})
  self.assertNotIn('5511999999999',str(redacted)); self.assertEqual(redacted['base64'],'[REDACTED]'); self.assertFalse(redacted['flag']); self.assertEqual(redact('data:image/png;base64,aGVsbG8='),'[REDACTED]')
 def test_plan_replay_expiry(self):
  p=self.s.plan('group_create',{'instance':'creator','subject':'x'}); self.assertEqual(self.s.apply(p['id'],p['id'])['status'],'created')
  with self.assertRaises(PlanError): self.s.apply(p['id'],p['id'])
  q=self.s.plan('group_create',{'instance':'creator','subject':'x'},ttl=-1)
  with self.assertRaises(PlanError): self.s.apply(q['id'],q['id'])
 def test_blacklist_and_onboarding_guards(self):
  self.store.blacklist('5511999999999')
  with self.assertRaises(PlanError): self.s.plan('onboarding',{'creator_instance':'creator','participant_instances':['client'],'admin_instances':['support'],'client_phone':'5511999999999','group_name':'A','phones':['5511999999999']})
  with self.assertRaises(PlanError): self.s.plan('onboarding',{'creator_instance':'creator','participant_instances':['creator'],'admin_instances':[],'client_phone':'5511888888888','group_name':'A'})
  with self.assertRaises(PlanError): self.s.plan('onboarding',{'creator_instance':'creator','participant_instances':['client'],'admin_instances':['support'],'client_phone':'abc@lid','group_name':'A'})
 def test_blacklist_canonicalizes_phone_aliases(self):
  self.store.blacklist('+5511999999999'); self.assertTrue(self.store.blacklisted('5511999999999@s.whatsapp.net')); self.store.blacklist('5511999999999@s.whatsapp.net',remove=True); self.assertFalse(self.store.blacklisted('+5511999999999'))
 def test_full_demo_onboarding(self):
  p=self.s.plan('onboarding',{'creator_instance':'creator','participant_instances':['client'],'admin_instances':['support'],'client_phone':'5511888888888','group_name':'Cliente','phones':['5511888888888']}); self.assertEqual(self.s.apply(p['id'],p['id'])['status'],'onboarded')
  with self.assertRaises(PlanError): self.s.apply(p['id'],p['id'])
 def test_route_contract(self): self.assertEqual(ROUTES['send_text'][0],'POST'); self.assertEqual(ROUTES['group_leave'][0],'DELETE'); self.assertEqual(ROUTES['invite_revoke'][0],'POST')
 def test_cli_chat_and_group_setup_commands(self):
  chat=parser().parse_args(['chat','messages','--instance','creator','--jid','x@g.us','--limit','4']); self.assertEqual((chat.cmd,chat.chat_cmd,chat.limit),('chat','messages','4'))
  group=parser().parse_args(['group','setup-plan','--instance','creator','--subject','Webinar','--phone','5511888888888','--participant-instance','client','--admin-instance','support','--setting','announcement']); self.assertEqual((group.group_cmd,group.subject,group.setting),('setup-plan','Webinar',['announcement']))
  self.assertEqual(parser().parse_args(['number','check','--instance','creator','--number','5511888888888']).number_cmd,'check')
  self.assertEqual(parser().parse_args(['webhook','set-plan','--instance','creator','--url','https://example.test/hook','--event','MESSAGES_UPSERT']).webhook_cmd,'set-plan')
 def test_cli_message_group_jid_is_not_added_to_phones(self):
  fake_store=MagicMock(); fake_service=MagicMock(); fake_service.plan.return_value={}; config=SimpleNamespace(database=pathlib.Path(self.tmp.name)/'cli.db',mode='demo',base_url='',api_key='',timeout=1)
  with patch('ad3_evolution.cli.Config.load',return_value=config),patch('ad3_evolution.cli.Store',return_value=fake_store),patch('ad3_evolution.cli.Service',return_value=fake_service):
   self.assertEqual(cli_main(['message','plan-text','--instance','creator','--number','x@g.us','--content','ola']),0)
  self.assertEqual(fake_service.plan.call_args.args[1],{'instance':'creator','number':'x@g.us','content':'ola'})
  adopted=parser().parse_args(['group','create','--instance','creator','--subject','Webinar','--existing-jid','x@g.us']); self.assertEqual(adopted.existing_jid,'x@g.us')
 def test_signed_inventory_paths_reject_drive_and_traversal(self):
  self.assertTrue(safe_relative('install/Install-AD3Evolution.ps1'))
  for value in ('../x','C:/x','./x','x\\y','x\x00y'):
   self.assertFalse(safe_relative(value))
 def test_store_encrypts_and_migrates_private_values(self):
  self.store.plan('message_text',{'instance':'creator','number':'5511999999999','content':'mensagem secreta'})
  self.store.save_state('demo-private',{'invite':'convite-privado'})
  raw=(pathlib.Path(self.tmp.name)/'x.db').read_bytes()
  for private in (b'5511999999999',b'mensagem secreta',b'convite-privado'): self.assertNotIn(private,raw)
  self.assertNotIn(b'5511999999999',self.store.db.execute('SELECT group_concat(detail) FROM audit').fetchone()[0].encode())
  legacy=pathlib.Path(self.tmp.name)/'legacy.db'; db=sqlite3.connect(legacy); db.executescript("CREATE TABLE plans(id TEXT PRIMARY KEY,kind TEXT,payload TEXT,hash TEXT,status TEXT,created REAL,expires REAL,result TEXT);CREATE TABLE audit(id INTEGER PRIMARY KEY,event TEXT,detail TEXT,at REAL);CREATE TABLE blacklist(value TEXT PRIMARY KEY);CREATE TABLE demo(key TEXT PRIMARY KEY,value TEXT);CREATE TABLE idempotency(key TEXT PRIMARY KEY,result TEXT);")
  db.execute("INSERT INTO demo VALUES(?,?)",('old','{"phone":"5511999999999"}')); db.execute("INSERT INTO blacklist VALUES(?)",('5511999999999',)); db.execute("INSERT INTO blacklist VALUES(?)",('A'*64,)); db.commit(); db.close()
  migrated=Store(legacy); self.assertEqual(migrated.state('old',{}),{'phone':'5511999999999'}); self.assertTrue(migrated.blacklisted('5511999999999')); self.assertIn('A'*64,[row[0] for row in migrated.db.execute('SELECT value FROM blacklist')]); self.assertNotIn(b'5511999999999',legacy.read_bytes()); migrated.close()
 def test_migration_retries_vacuum_after_a_single_failure(self):
  legacy=pathlib.Path(self.tmp.name)/'vacuum.db'; db=sqlite3.connect(legacy); db.executescript("CREATE TABLE plans(id TEXT PRIMARY KEY,kind TEXT,payload TEXT,hash TEXT,status TEXT,created REAL,expires REAL,result TEXT);CREATE TABLE audit(id INTEGER PRIMARY KEY,event TEXT,detail TEXT,at REAL);CREATE TABLE blacklist(value TEXT PRIMARY KEY);CREATE TABLE demo(key TEXT PRIMARY KEY,value TEXT);CREATE TABLE idempotency(key TEXT PRIMARY KEY,result TEXT);"); db.execute("INSERT INTO blacklist VALUES(?)",('+5511999999999',)); db.commit(); db.close()
  original=Store._vacuum; calls=[]
  def fail_once(instance):
   calls.append(1)
   if len(calls)==1: raise sqlite3.OperationalError('vacuum failed')
   return original(instance)
  with patch.object(Store,'_vacuum',autospec=True,side_effect=fail_once):
   with self.assertRaises(sqlite3.OperationalError): Store(legacy)
   db=sqlite3.connect(legacy); self.assertEqual(db.execute("SELECT value FROM maintenance WHERE key='vacuum_required'").fetchone(),('1',)); db.close()
   migrated=Store(legacy)
  self.assertTrue(migrated.blacklisted('5511999999999@s.whatsapp.net')); self.assertNotIn(b'5511999999999',legacy.read_bytes()); self.assertIsNone(migrated.db.execute("SELECT 1 FROM maintenance WHERE key='vacuum_required'").fetchone()); migrated.close()
 def test_legacy_wal_artifacts_are_checked_after_migration_compaction(self):
  legacy=pathlib.Path(self.tmp.name)/'legacy-wal.db'; writer=sqlite3.connect(legacy); writer.execute('PRAGMA journal_mode=WAL'); writer.executescript("CREATE TABLE plans(id TEXT PRIMARY KEY,kind TEXT,payload TEXT,hash TEXT,status TEXT,created REAL,expires REAL,result TEXT);CREATE TABLE audit(id INTEGER PRIMARY KEY,event TEXT,detail TEXT,at REAL);CREATE TABLE blacklist(value TEXT PRIMARY KEY);CREATE TABLE demo(key TEXT PRIMARY KEY,value TEXT);CREATE TABLE idempotency(key TEXT PRIMARY KEY,result TEXT);"); writer.execute("INSERT INTO blacklist VALUES(?)",('+5511999999999',)); writer.commit()
  self.assertTrue(pathlib.Path(str(legacy)+'-wal').exists())
  migrated=Store(legacy)
  try:
   self.assertIsNone(migrated.db.execute("SELECT 1 FROM maintenance WHERE key='vacuum_required'").fetchone())
   for artifact in (legacy,pathlib.Path(str(legacy)+'-wal'),pathlib.Path(str(legacy)+'-shm')):
    if artifact.exists(): self.assertNotIn(b'5511999999999',artifact.read_bytes())
  finally:
   migrated.close(); writer.close()
 def test_atomic_claim_allows_one_executor(self):
  second=Store(pathlib.Path(self.tmp.name)/'x.db'); first=Store(pathlib.Path(self.tmp.name)/'x.db')
  try:
   a=first.plan('message_text',{'instance':'creator','number':'5511999999999','content':'once','idempotency_key':'same'})
   b=second.plan('message_text',{'instance':'creator','number':'5511999999999','content':'once','idempotency_key':'same'})
   calls=[]; lock=threading.Lock(); start=threading.Barrier(2)
   def run(store, plan):
    start.wait()
    try: store.apply(plan['id'],plan['id'],lambda kind,p: (lock.acquire(),calls.append(kind),lock.release(),{'ok':True})[-1])
    except PlanError: pass
   one=threading.Thread(target=run,args=(first,a)); two=threading.Thread(target=run,args=(second,b)); one.start(); two.start(); one.join(); two.join()
   self.assertEqual(calls,['message_text'])
  finally: first.close(); second.close()
 def test_instance_and_jid_validation(self):
  with self.assertRaises(PlanError): self.s.plan('group_create',{'instance':'bad/name','subject':'x'})
  with self.assertRaises(PlanError): self.s.plan('group_subject',{'instance':'creator','groupJid':'abc@lid','subject':'x'})
  self.assertEqual(validate_chat_jid('5511888888888@s.whatsapp.net'),'5511888888888@s.whatsapp.net'); self.assertEqual(validate_chat_jid('abc@lid'),'abc@lid')
  self.store.save_state('messages',[{'key':{'remoteJid':'5511888888888@s.whatsapp.net'}},{'key':{'remoteJid':'abc@lid'}}]); self.assertEqual(len(self.s.message_history('creator','5511888888888@s.whatsapp.net',20)),1); self.assertEqual(len(self.s.message_history('creator','abc@lid',20)),1)
  with self.assertRaises(ValueError): validate_chat_jid('status@broadcast')
  with self.assertRaises(PlanError): self.s.message_history('creator','status@broadcast',20)
 def test_ephemeral_ed25519_license(self):
  from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
  from cryptography.hazmat.primitives import serialization
  from ad3_evolution.security import canonical
  key=Ed25519PrivateKey.generate(); manifest={'product':'AD3 WhatsApp Evolution','name':'A','email':'a@test','license_id':'test','issued_at':'2026-01-01T00:00:00Z','license_terms_version':'1','artifact_hashes':{'x':'0'*64}}; sig=base64.b64encode(key.sign(canonical(manifest).encode())).decode(); pub=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
  self.assertTrue(verify_manifest(manifest,sig,pub))

class Handler(BaseHTTPRequestHandler):
 def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b'{"ok":true}')
 def log_message(self,*x): pass
class HttpTests(unittest.TestCase):
 def test_fake_server(self):
  srv=HTTPServer(('127.0.0.1',0),Handler); t=threading.Thread(target=srv.serve_forever); t.start()
  try: self.assertTrue(EvolutionClient(f'http://127.0.0.1:{srv.server_port}','key').request('instance_list')['ok'])
  finally: srv.shutdown(); t.join(); srv.server_close()
 def test_post_create_contract_and_qr_redaction(self):
  seen={}
  class H(BaseHTTPRequestHandler):
   def do_POST(self):
    seen.update(path=self.path,method=self.command,key=self.headers.get('apikey'),body=self.rfile.read(int(self.headers['Content-Length'])).decode());self.send_response(200);self.end_headers();self.wfile.write(b'{"qrcode":{"pairingCode":"1234","base64":"data:image/png;base64,YWJj"}}')
   def log_message(self,*x): pass
  srv=HTTPServer(('127.0.0.1',0),H);t=threading.Thread(target=srv.serve_forever);t.start()
  try:
   with tempfile.TemporaryDirectory() as d:
    s=Service(Store(pathlib.Path(d)/'x.db'),'remote',EvolutionClient(f'http://127.0.0.1:{srv.server_port}','secret'));p=s.plan('instance_create',{'instance':'new','qr_file':str(pathlib.Path(d)/'qr.png')});r=s.apply(p['id'],p['id']);self.assertEqual(seen['path'],'/instance/create');self.assertEqual(seen['method'],'POST');self.assertEqual(seen['key'],'secret');self.assertIn('WHATSAPP-BAILEYS',seen['body']);self.assertNotIn('YWJj',str(r));self.assertTrue(pathlib.Path(r['qr_file']).is_file());s.store.close()
  finally: srv.shutdown();t.join();srv.server_close()
 def test_catalogued_path_params_are_encoded(self):
  seen={}
  class H(BaseHTTPRequestHandler):
   def do_GET(self):
    seen["path"]=self.path;self.send_response(200);self.end_headers();self.wfile.write(b'{"ok":true}')
   def log_message(self,*x): pass
  srv=HTTPServer(('127.0.0.1',0),H);t=threading.Thread(target=srv.serve_forever);t.start()
  try:
   result=EvolutionClient(f'http://127.0.0.1:{srv.server_port}','key').request('openai.fetch','creator',params={'openaiBotId':'bot id'})
   self.assertTrue(result["ok"]);self.assertEqual(seen["path"],"/openai/fetch/bot%20id/creator")
  finally: srv.shutdown();t.join();srv.server_close()
 def test_catalogued_upload_uses_multipart(self):
  seen={}
  class H(BaseHTTPRequestHandler):
   def do_POST(self):
    seen["path"]=self.path;seen["type"]=self.headers["Content-Type"];seen["body"]=self.rfile.read(int(self.headers["Content-Length"]));self.send_response(200);self.end_headers();self.wfile.write(b'{"ok":true}')
   def log_message(self,*x): pass
  srv=HTTPServer(('127.0.0.1',0),H);t=threading.Thread(target=srv.serve_forever);t.start()
  try:
   with tempfile.TemporaryDirectory() as d:
    file=pathlib.Path(d)/"image.bin";file.write_bytes(b"image-bytes")
    result=EvolutionClient(f'http://127.0.0.1:{srv.server_port}','key').request('message.send-media','creator',payload={'number':'5511888888888','mediatype':'image'},file_path=file)
    self.assertTrue(result["ok"]);self.assertEqual(seen["path"],"/message/sendMedia/creator");self.assertTrue(seen["type"].startswith("multipart/form-data; boundary="));self.assertIn(b'name="number"',seen["body"]);self.assertIn(b'image-bytes',seen["body"])
  finally: srv.shutdown();t.join();srv.server_close()

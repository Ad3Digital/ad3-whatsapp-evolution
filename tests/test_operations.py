import _bootstrap
import pathlib,tempfile,unittest
from ad3_evolution.store import Store,PlanError
from ad3_evolution.service import Service
from ad3_evolution.client import EvolutionClient
from ad3_evolution.profiles import API_OPERATIONS, ROUTES, api_catalog

class Recorder:
 def __init__(self): self.calls=[]
 def request(self,op,instance='',payload=None,query=None):
  self.calls.append((op,instance,payload,query))
  if op=='instance_status': return {'state':'open'}
  if op=='instance_list': return [{'name':'creator','phoneNumber':'5511000000001'},{'name':'client','phoneNumber':'5511000000002'},{'name':'support','phoneNumber':'5511000000003'}]
  if op=='whatsapp_validate': return {'numbers':[{'number':'5511888888888','exists':True}]}
  if op=='group_create': return {'success':True,'group':{'id':'x@g.us'}}
  if op=='group_info':
   created=next((x[2] for x in reversed(self.calls) if x[0]=='group_create'),{})
   settings=[x[2].get('action') for x in self.calls if x[0]=='group_settings']
   return {'group':{'id':'x@g.us','subject':created.get('subject','G'),'description':created.get('description',''),'announce':'announcement' in settings,'restrict':'locked' in settings,'participants':[{'phoneNumber':'5511888888888'},{'phoneNumber':'5511000000002'},{'phoneNumber':'5511000000003','role':'admin'}]}}
  return {'ok':True}

class Operations(unittest.TestCase):
 def setUp(self): self.t=tempfile.TemporaryDirectory();self.store=Store(pathlib.Path(self.t.name)/'s.db');self.demo=Service(self.store,'demo')
 def tearDown(self):self.store.close();self.t.cleanup()
 def group(self):
  p=self.demo.plan('group_create',{'instance':'creator','subject':'G','phones':['5511888888888']});return self.demo.apply(p['id'],p['id'])['group_jid']
 def mutate(self,kind,p):
  q=self.demo.plan(kind,p);return self.demo.apply(q['id'],q['id'])
 def test_subject(self): j=self.group();self.mutate('group_subject',{'groupJid':j,'subject':'N'});self.assertEqual(self.demo._group(j)[1]['subject'],'N')
 def test_description(self): j=self.group();self.mutate('group_description',{'groupJid':j,'description':'D'});self.assertEqual(self.demo._group(j)[1]['description'],'D')
 def test_picture(self): j=self.group();self.mutate('group_picture',{'groupJid':j,'picture':'x'});self.assertEqual(self.demo._group(j)[1]['picture'],'x')
 def test_add(self): j=self.group();self.mutate('participants_add',{'groupJid':j,'phones':['5511777777777']});self.assertIn('5511777777777',self.demo._group(j)[1]['participants'])
 def test_remove(self): j=self.group();self.mutate('participants_remove',{'groupJid':j,'phones':['5511888888888']});self.assertNotIn('5511888888888',self.demo._group(j)[1]['participants'])
 def test_promote(self): j=self.group();self.mutate('participants_promote',{'groupJid':j,'phones':['5511888888888']});self.assertIn('5511888888888',self.demo._group(j)[1]['admins'])
 def test_demote(self): j=self.group();self.mutate('participants_promote',{'groupJid':j,'phones':['5511888888888']});self.mutate('participants_demote',{'groupJid':j,'phones':['5511888888888']});self.assertNotIn('5511888888888',self.demo._group(j)[1]['admins'])
 def test_setting(self): j=self.group();self.mutate('group_settings',{'groupJid':j,'setting':'announcement','value':True});self.assertTrue(self.demo._group(j)[1]['settings']['announcement'])
 def test_invite(self): j=self.group();self.mutate('invite_revoke',{'groupJid':j});self.assertEqual(self.demo._group(j)[1]['invite'],'demo-revoked')
 def test_leave(self): j=self.group();self.mutate('group_leave',{'groupJid':j});self.assertEqual(self.demo.store.state('groups',[]),[])
 def test_message(self):
  self.mutate('message_text',{'number':'5511888888888','content':'x'});self.assertEqual(self.store.state('last_message_text',{})['content'],'x')
  group=self.demo.plan('message_text',{'number':'x@g.us','content':'grupo'}); self.assertEqual(self.demo.apply(group['id'],group['id'])['status'],'simulated')
  self.store.blacklist('+5511888888888')
  with self.assertRaises(PlanError): self.demo.plan('message_text',{'number':'5511888888888@s.whatsapp.net','content':'bloqueada'})
 def test_chat_recipient_requires_one_matching_phone_and_photo(self):
  class Contacts:
   def __init__(self): self.phones=['5511888888888@s.whatsapp.net']
   def request(self,op,instance='',payload=None,query=None):
    if op=='chat_list': return [{'id':'chat-12345','profilePicUrl':'https://photo','lastMessage':{'pushName':'Ingrid'}}]
    if op=='chat.find-contacts': return [{'pushName':'Ingrid','profilePicUrl':'https://photo','remoteJid':jid} for jid in self.phones]
    raise AssertionError(op)
  client=Contacts(); service=Service(self.store,'remote',client)
  self.assertEqual(service.recipient_from_chat('aula','chat-12345'),'5511888888888')
  client.phones.append('5511999999999@s.whatsapp.net')
  with self.assertRaises(PlanError): service.recipient_from_chat('aula','chat-12345')
  client.phones=['5511888888888@s.whatsapp.net']
  original=client.request
  def wrong_photo(op,*args,**kwargs):
   result=original(op,*args,**kwargs)
   if op=='chat.find-contacts': result[0]['profilePicUrl']='https://other'
   return result
  client.request=wrong_photo
  with self.assertRaises(PlanError): service.recipient_from_chat('aula','chat-12345')
 def test_webhook(self):
  payload={'instance':'creator','webhook':{'enabled':True,'url':'http://localhost/hook','headers':{},'byEvents':True,'base64':False,'events':['MESSAGES_UPSERT','MESSAGES_UPSERT']}}
  self.mutate('webhook_set',payload); self.assertEqual(self.store.state('last_webhook_set',{})['webhook']['events'],['MESSAGES_UPSERT']); self.assertEqual(self.demo.webhook_info('creator')['origin'],'http://localhost')
  r=Recorder(); remote=Service(self.store,'remote',r); plan=remote.plan('webhook_set',{'instance':'creator','webhook':{'enabled':False,'url':'https://hooks.example.test/h','headers':{},'byEvents':False,'base64':True,'events':['CALL']}}); remote.apply(plan['id'],plan['id']); self.assertEqual(r.calls[-1],('webhook_set','creator',{'webhook':{'enabled':False,'url':'https://hooks.example.test/h','headers':{},'byEvents':False,'base64':True,'events':['CALL']}},None))
  for bad in ({'instance':'creator','webhook':{**payload['webhook'],'url':'http://bad.test/?token=x'}},{'instance':'creator','webhook':{**payload['webhook'],'events':['BAD']}},{'instance':'creator','webhook':{**payload['webhook'],'headers':{'Authorization':'x'}}}):
   with self.assertRaises(PlanError): self.demo.plan('webhook_set',bad)
 def test_read_gates_and_remote_invite_revoke_body(self):
  jid=self.group(); self.assertEqual(len(self.demo.group_participants('creator',jid)),1); self.assertEqual(self.demo.whatsapp_numbers('creator',['5511888888888'])['numbers'][0]['exists'],True); code=self.demo._group(jid)[1]['invite']; self.assertEqual(self.demo.invite_info('creator',code)['jid'],jid)
  with self.assertRaises(PlanError): self.demo.invite_info('creator','https://chat.whatsapp.com/x')
  r=Recorder(); remote=Service(self.store,'remote',r); plan=remote.plan('invite_revoke',{'instance':'creator','groupJid':'x@g.us'}); remote.apply(plan['id'],plan['id']); self.assertEqual(r.calls[-1],('invite_revoke','creator',{'groupJid':'x@g.us'},None))
 def test_remote_number_check_accepts_list_response(self):
  r=Recorder(); r.request=lambda op,*a,**k: [{'number':'5511888888888','exists':True}] if op=='whatsapp_validate' else {'state':'open'}
  result=Service(self.store,'remote',r).whatsapp_numbers('creator',['5511888888888'])
  self.assertEqual(result,[{'number':'5511888888888','exists':True}])
 def test_remote_invite_send_payload(self):
  r=Recorder();s=Service(self.store,'remote',r);p=s.plan('invite_send',{'instance':'creator','groupJid':'x@g.us','description':'Entre','phones':['5511888888888']});s.apply(p['id'],p['id']);self.assertEqual(r.calls[-1],('invite_send','creator',{'groupJid':'x@g.us','description':'Entre','numbers':['5511888888888']},None))
 def test_remote_onboarding_steps(self):
  r=Recorder();s=Service(self.store,'remote',r);p=s.plan('onboarding',{'creator_instance':'creator','participant_instances':['client'],'admin_instances':['support'],'client_phone':'5511888888888','group_name':'G'});s.apply(p['id'],p['id']);self.assertEqual([x[0] for x in r.calls],['instance_status','instance_status','instance_status','instance_list','whatsapp_validate','group_create','participants_add','participants_promote','group_info','instance_status','send_text','invite_get'])
 def test_remote_onboarding_phone_failure(self):
  r=Recorder();r.request=lambda op,*a,**k: {'state':'open'} if op=='instance_status' else ({'numbers':[]} if op=='whatsapp_validate' else {})
  s=Service(self.store,'remote',r);p=s.plan('onboarding',{'creator_instance':'creator','participant_instances':[],'admin_instances':[],'client_phone':'5511888888888','group_name':'G'});
  with self.assertRaises(PlanError):s.apply(p['id'],p['id'])
 def test_group_setup_rejects_owner_fallback_without_phone_number(self):
  r=Recorder(); original=r.request
  def missing_phone(op,*args,**kwargs):
   if op=='instance_list': return [{'name':'creator','phoneNumber':'5511000000001'},{'name':'client','owner':'5511000000002@s.whatsapp.net'},{'name':'support','ownerJid':'5511000000003@s.whatsapp.net'}]
   return original(op,*args,**kwargs)
  r.request=missing_phone; s=Service(self.store,'remote',r); p=s.plan('group_setup',{'instance':'creator','subject':'G','participant_instances':['client'],'admin_instances':['support']})
  with self.assertRaises(PlanError): s.apply(p['id'],p['id'])
  self.assertFalse({'group_create','participants_add','participants_promote'} & {call[0] for call in r.calls})
 def test_onboarding_rejects_owner_fallback_before_group_creation(self):
  r=Recorder(); original=r.request
  def missing_phone(op,*args,**kwargs):
   if op=='instance_list': return [{'name':'creator','phoneNumber':'5511000000001'},{'name':'client','owner':'5511000000002@s.whatsapp.net'},{'name':'support','ownerJid':'5511000000003@s.whatsapp.net'}]
   return original(op,*args,**kwargs)
  r.request=missing_phone; s=Service(self.store,'remote',r); p=s.plan('onboarding',{'creator_instance':'creator','participant_instances':['client'],'admin_instances':['support'],'client_phone':'5511888888888','group_name':'G'})
  with self.assertRaises(PlanError): s.apply(p['id'],p['id'])
  self.assertFalse({'group_create','participants_add','participants_promote'} & {call[0] for call in r.calls})
 def test_known_data_envelopes_are_normalized_for_status_and_instances(self):
  r=Recorder(); original=r.request
  def nested(op,*args,**kwargs):
   if op=='instance_status': return {'data':{'state':'open'}}
   if op=='instance_list': return {'data':{'instances':[{'name':'creator','phoneNumber':'5511000000001'}]}}
   return original(op,*args,**kwargs)
  r.request=nested; s=Service(self.store,'remote',r); self.assertTrue(s._connected('creator')); self.assertEqual(s.instances(),[{'name':'creator','phoneNumber':'5511000000001'}])
 def test_nested_group_create_checkpoints_recoverable_jid_without_plaintext(self):
  r=Recorder(); original=r.request
  def nested_create(op,*args,**kwargs):
   if op=='group_create': return {'data':{'group':{'id':'x@g.us'}}}
   if op=='group_picture': raise RuntimeError('partial failure')
   return original(op,*args,**kwargs)
  r.request=nested_create; s=Service(self.store,'remote',r); p=s.plan('group_setup',{'instance':'creator','subject':'G','phones':['5511888888888'],'picture':'https://example.test/p.png'})
  with self.assertRaises(PlanError): s.apply(p['id'],p['id'])
  self.assertEqual(self.store.plan_status(p['id'])['receipt'],{'group_jid':'x@g.us','phase':'picture'}); raw=self.store.path.read_bytes(); self.assertNotIn(b'5511888888888',raw); self.assertNotIn(b'x@g.us',raw)
 def test_group_create_can_adopt_without_second_creation(self):
  r=Recorder(); original=r.request
  def existing(op,*args,**kwargs):
   if op=='group_info': return {'group':{'id':'x@g.us','subject':'G','participants':[{'phoneNumber':'5511888888888'}]}}
   return original(op,*args,**kwargs)
  r.request=existing; s=Service(self.store,'remote',r); p=s.plan('group_create',{'instance':'creator','subject':'G','existing_jid':'x@g.us','phones':['5511888888888']})
  self.assertEqual(s.apply(p['id'],p['id']),{'group_jid':'x@g.us','status':'reconciled'}); self.assertNotIn('group_create',[call[0] for call in r.calls])
 def test_remote_onboarding_partial_failure_resumes_without_second_create_or_welcome(self):
  r=Recorder(); original=r.request
  def fail_after_create(op,*args,**kwargs):
   if op=='participants_add': raise RuntimeError('transport failure')
   return original(op,*args,**kwargs)
  r.request=fail_after_create; s=Service(self.store,'remote',r); payload={'creator_instance':'creator','participant_instances':['client'],'admin_instances':['support'],'client_phone':'5511888888888','group_name':'G'}
  first=s.plan('onboarding',payload)
  with self.assertRaises(Exception): s.apply(first['id'],first['id'])
  self.assertEqual(self.store.plan_status(first['id'])['receipt'],{'group_jid':'x@g.us','phase':'created'})
  creates=len([call for call in r.calls if call[0]=='group_create'])
  r.request=original
  resumed=s.plan('onboarding',{**payload,'existing_jid':'x@g.us'}); result=s.apply(resumed['id'],resumed['id'])
  self.assertEqual(result,{'group_jid':'x@g.us','status':'reconciled','welcome':'not_sent'})
  self.assertEqual(len([call for call in r.calls if call[0]=='group_create']),creates)
  self.assertNotIn('send_text',[call[0] for call in r.calls])
 def test_chat_reads_use_pinned_post_bodies_without_plans(self):
  r=Recorder();s=Service(self.store,'remote',r)
  s.chat_list('creator',7); self.assertEqual(r.calls[-1],('chat_list','creator',{'take':7},None))
  s.message_history('creator','x@g.us',9); self.assertEqual(r.calls[-1],('message_history','creator',{'where':{'key':{'remoteJid':'x@g.us'}},'take':9},None))
  self.assertEqual(self.store.db.execute('SELECT count(*) FROM plans').fetchone()[0],0)
  for value in (0,101,'bad'):
   with self.assertRaises(PlanError): s.chat_list('creator',value)
  with self.assertRaises(PlanError): s.message_history('creator','',1)
 def test_group_setup_static_validation(self):
  base={'instance':'creator','subject':'G','phones':['5511888888888'],'participant_instances':['client'],'admin_instances':['support'],'settings':['announcement']}
  for payload in ({**base,'subject':''},{**base,'participant_instances':['creator']},{**base,'participant_instances':['client','client']},{**base,'admin_instances':['client']},{**base,'settings':['announcement','not_announcement']},{**base,'phones':['x@lid']},{**base,'phones':['x@g.us']},{**base,'phones':['not-a-phone']},{**base,'phones':['123']}):
   with self.assertRaises(PlanError): self.demo.plan('group_setup',payload)
  self.store.blacklist('5511888888888')
  with self.assertRaises(PlanError): self.demo.plan('group_setup',base)
 def test_group_setup_demo(self):
  p=self.demo.plan('group_setup',{'instance':'creator','subject':'Webinar','description':'D','picture':'https://example.test/p.png','phones':['5511888888888'],'participant_instances':['client'],'admin_instances':['support'],'settings':['announcement','locked']})
  result=self.demo.apply(p['id'],p['id']); self.assertEqual(result['status'],'configured'); self.assertEqual(result['admin_verification'],'simulated')
  group=self.demo._group(result['group_jid'])[1]; self.assertEqual(group['description'],'D'); self.assertEqual(group['picture'],'https://example.test/p.png'); self.assertIn('support',group['admins']); self.assertTrue(group['settings']['locked'])
  normalized=self.demo.plan('group_setup',{'instance':'creator','subject':'Normalizado','phones':['+5511888888888','5511777777777@s.whatsapp.net']}); self.assertEqual(self.store._dec(self.store.db.execute('SELECT payload FROM plans WHERE id=?',(normalized['id'],)).fetchone()[0],'plans',normalized['id'],'payload')['phones'],['5511888888888','5511777777777'])
 def test_remote_group_setup_sequence_and_deduplication(self):
  r=Recorder();s=Service(self.store,'remote',r)
  p=s.plan('group_setup',{'instance':'creator','subject':'Webinar','description':'D','picture':'https://example.test/p.png','phones':['5511888888888','5511888888888'],'participant_instances':['client'],'admin_instances':['support'],'settings':['announcement','locked']})
  result=s.apply(p['id'],p['id']); self.assertEqual(result,{'group_jid':'x@g.us','status':'configured','verified':True,'admin_verification':'roles'})
  self.assertEqual([x[0] for x in r.calls],['instance_status','instance_status','instance_status','instance_list','group_create','group_description','group_picture','participants_promote','group_settings','group_settings','group_info'])
  create=r.calls[4][2]; self.assertEqual(create['participants'],['5511888888888','5511000000002','5511000000003'])
  self.assertEqual(r.calls[7][2],{'groupJid':'x@g.us','action':'promote','participants':['5511000000003']})
  self.assertEqual(r.calls[8][2],{'groupJid':'x@g.us','action':'announcement'})
 def test_remote_group_setup_checks_admin_role_when_available(self):
  r=Recorder(); original=r.request
  def with_roles(op,*args,**kwargs):
   if op=='group_info': return {'group':{'id':'x@g.us','subject':'Webinar','participants':[{'phoneNumber':'5511000000003','role':'admin'}]}}
   return original(op,*args,**kwargs)
  r.request=with_roles; s=Service(self.store,'remote',r); p=s.plan('group_setup',{'instance':'creator','subject':'Webinar','admin_instances':['support']}); self.assertEqual(s.apply(p['id'],p['id'])['admin_verification'],'roles')
  r=Recorder(); original=r.request
  def without_admin_role(op,*args,**kwargs):
   if op=='group_info': return {'group':{'id':'x@g.us','subject':'Webinar 2','participants':[{'phoneNumber':'5511000000003','role':'member'}]}}
   return original(op,*args,**kwargs)
  r.request=without_admin_role; s=Service(self.store,'remote',r); p=s.plan('group_setup',{'instance':'creator','subject':'Webinar 2','admin_instances':['support']})
  with self.assertRaises(PlanError): s.apply(p['id'],p['id'])
 def test_group_setup_partial_failure_is_uncertain_without_replay(self):
  r=Recorder(); original=r.request
  def fail_picture(op,*args,**kwargs):
   if op=='group_picture': raise RuntimeError('transport token=do-not-expose')
   return original(op,*args,**kwargs)
  r.request=fail_picture; s=Service(self.store,'remote',r)
  p=s.plan('group_setup',{'instance':'creator','subject':'Webinar','picture':'https://example.test/p.png','participant_instances':['client'],'admin_instances':['support']})
  with self.assertRaises(PlanError) as caught: s.apply(p['id'],p['id'])
  self.assertIn('plan-status',str(caught.exception)); self.assertEqual(self.store.db.execute('SELECT status FROM plans WHERE id=?',(p['id'],)).fetchone()[0],'uncertain')
  self.assertEqual(self.store.plan_status(p['id'])['receipt'],{'group_jid':'x@g.us','phase':'picture'})
  creates=len([x for x in r.calls if x[0]=='group_create'])
  with self.assertRaises(PlanError): s.apply(p['id'],p['id'])
  self.assertEqual(len([x for x in r.calls if x[0]=='group_create']),creates)
 def test_routes_complete(self):
  for key in ('instance_qr','chat_list','message_history','group_list','group_info','group_participants','invite_info','whatsapp_validate','group_create','group_subject','group_description','group_picture','participants_add','participants_remove','participants_promote','participants_demote','group_settings','invite_get','invite_revoke','group_leave','send_text','send_media','webhook_find','webhook_set'): self.assertIn(key,ROUTES)
  self.assertEqual(ROUTES['invite_revoke'][0],'POST')
 def test_query_encoding(self):
  c=EvolutionClient('http://x','k');
  import ad3_evolution.client as m
  seen={}
  class R:
   def __enter__(self): return self
   def __exit__(self,*x):pass
   def read(self):return b'{}'
  old=m.urlopen;m.urlopen=lambda req,timeout:(seen.update(url=req.full_url),R())[1]
  try:
   c.request('invite_get','real name-1',query={'groupJid':'x@g.us'});self.assertIn('/real%20name-1?',seen['url']);self.assertIn('groupJid=x%40g.us',seen['url'])
   with self.assertRaises(Exception): c.request('invite_get','bad/name')
  finally:m.urlopen=old
 def test_resume_existing_jid_never_creates_again(self):
  r=Recorder(); original=r.request
  def adopted(op,*args,**kwargs):
   if op=='group_info': return {'group':{'id':'x@g.us','subject':'Adotado','participants':[]}}
   return original(op,*args,**kwargs)
  r.request=adopted;s=Service(self.store,'remote',r)
  p=s.plan('group_setup',{'instance':'creator','subject':'Adotado','existing_jid':'x@g.us'})
  s.apply(p['id'],p['id'])
  self.assertNotIn('group_create',[x[0] for x in r.calls])
 def test_adopted_group_setup_requires_every_expected_participant(self):
  r=Recorder(); original=r.request
  def missing_member(op,*args,**kwargs):
   if op=='group_info': return {'group':{'id':'x@g.us','subject':'Adotado','participants':[{'phoneNumber':'5511000000003','role':'admin'}]}}
   return original(op,*args,**kwargs)
  r.request=missing_member; s=Service(self.store,'remote',r); p=s.plan('group_setup',{'instance':'creator','subject':'Adotado','existing_jid':'x@g.us','phones':['5511888888888'],'participant_instances':['client'],'admin_instances':['support']})
  with self.assertRaises(PlanError): s.apply(p['id'],p['id'])
  self.assertEqual(self.store.plan_status(p['id'])['status'],'uncertain'); self.assertNotIn('group_create',[x[0] for x in r.calls])
 def test_adopted_group_setup_preflight_blocks_all_mutations_when_group_is_wrong(self):
  r=Recorder(); original=r.request
  def wrong_group(op,*args,**kwargs):
   if op=='group_info': return {'data':{'group':{'id':'wrong@g.us','subject':'Adotado','participants':[{'phoneNumber':'5511888888888'}]}}}
   return original(op,*args,**kwargs)
  r.request=wrong_group; s=Service(self.store,'remote',r); p=s.plan('group_setup',{'instance':'creator','subject':'Adotado','existing_jid':'x@g.us','phones':['5511888888888'],'description':'D','picture':'https://example.test/p.png','settings':['announcement']})
  with self.assertRaises(PlanError): s.apply(p['id'],p['id'])
  mutations={'group_description','group_picture','participants_promote','group_settings','group_create'}; self.assertFalse(mutations & {call[0] for call in r.calls})
 def test_qr_external_path_fails_before_remote_call(self):
  r=Recorder();s=Service(self.store,'remote',r)
  with self.assertRaises(PlanError): s.plan('instance_create',{'instance':'new','qr_file':str(pathlib.Path(self.t.name).parent/'outside.png')})
  self.assertEqual(r.calls,[])
 def test_manifest_gate_missing(self):
  from ad3_evolution.runtime import require_license
  with self.assertRaises(Exception): require_license(b'bad',pathlib.Path(self.t.name))
 def test_manager_strong_confirms(self):
  text=(pathlib.Path(__file__).resolve().parents[1]/'install/Manage-AD3Evolution.ps1').read_text();self.assertIn("PURGE-VOLUMES",text);self.assertIn("-Confirm RESTORE",text)
 def test_release_excludes_source(self):
  text=(pathlib.Path(__file__).resolve().parents[1]/'scripts/build_release.py').read_text();self.assertIn("'src'",text);self.assertIn('CHECKSUMS.sha256',text)
 def test_full_api_catalog_is_pinned_to_2_3_7(self):
  catalog=api_catalog(); routes={item["id"]:item for item in catalog["operations"]}
  self.assertEqual(catalog["upstream_tag"],"2.3.7"); self.assertEqual(len(API_OPERATIONS),177); self.assertEqual(len(routes),177)
  self.assertEqual(routes["message.send-ptv"]["path"],"/message/sendPtv/{instance}"); self.assertTrue(routes["message.send-ptv"]["upload_file"])
  self.assertEqual(routes["openai.fetch"]["path"],"/openai/fetch/{openaiBotId}/{instance}"); self.assertEqual(routes["kafka.find"]["execution"],"read")
  self.assertEqual(routes["group.accept-invite-code"]["execution"],"plan"); self.assertEqual(routes["chat.get-base64-from-media-message"]["execution"],"download"); self.assertEqual(routes["baileys.get-auth-state"]["execution"],"restricted"); self.assertEqual(len(api_catalog("message.")["operations"]),13)
 def test_generic_api_read_and_plan_use_explicit_catalog(self):
  r=Recorder();s=Service(self.store,'remote',r)
  self.assertEqual(s.api_read("chat.find-contacts","creator",payload={"where":{"id":"x"}}),{"ok":True})
  self.assertEqual(r.calls[-1],("chat.find-contacts","creator",{"where":{"id":"x"}},{}))
  with self.assertRaises(PlanError): s.api_read("message.send-text","creator",payload={"number":"5511888888888","text":"x"})
  with self.assertRaises(PlanError): s.api_plan("baileys.get-auth-state","creator")
  plan=s.api_plan("message.send-poll","creator",payload={"number":"5511888888888","name":"Pergunta","values":["A","B"],"selectableCount":1})
  self.assertEqual(plan["kind"],"api"); self.assertEqual(s.apply(plan["id"],plan["id"]),{"ok":True})
  self.assertEqual(r.calls[-1][0],"message.send-poll"); self.assertEqual(r.calls[-1][1],"creator")
 def test_generic_api_upload_refuses_a_changed_file(self):
  r=Recorder();s=Service(self.store,'remote',r); file=pathlib.Path(self.t.name)/"media.bin"; file.write_bytes(b"before")
  plan=s.api_plan("message.send-media","creator",payload={"number":"5511888888888","mediatype":"image"},file_path=file)
  file.write_bytes(b"after")
  with self.assertRaises(PlanError): s.apply(plan["id"],plan["id"])
  self.assertEqual(r.calls,[]); self.assertEqual(self.store.plan_status(plan["id"])["status"],"uncertain")
 def test_generic_api_media_download_writes_no_base64_to_terminal(self):
  class BinaryClient:
   def __init__(self): self.calls=[]
   def request(self,*args,**kwargs): self.calls.append((args,kwargs)); return {"data":{"base64":"aGVsbG8="}}
  client=BinaryClient();s=Service(self.store,'remote',client); output=pathlib.Path(self.t.name)/"media.bin"
  with self.assertRaises(PlanError): s.api_read("chat.get-base64-from-media-message","creator",payload={"message":{"key":"x"}})
  with self.assertRaises(PlanError): s.api_plan("chat.get-base64-from-media-message","creator",payload={"message":{"key":"x"}})
  result=s.api_download("chat.get-base64-from-media-message","creator",payload={"message":{"key":"x"}},output_file=output)
  self.assertEqual(result["status"],"downloaded"); self.assertEqual(output.read_bytes(),b"hello"); self.assertEqual(client.calls[0][0][0],"chat.get-base64-from-media-message")

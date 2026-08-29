from __future__ import annotations
import base64
import binascii
import hashlib
import re
from pathlib import Path
from urllib.parse import urlsplit

from .store import Store, PlanError
from .client import EvolutionClient
from .profiles import api_operation, api_path_parameters
from .security import digest_text, normalize_phone, validate_chat_jid, validate_group_jid, validate_instance

WEBHOOK_EVENTS={"APPLICATION_STARTUP","QRCODE_UPDATED","MESSAGES_SET","MESSAGES_UPSERT","MESSAGES_EDITED","MESSAGES_UPDATE","MESSAGES_DELETE","SEND_MESSAGE","SEND_MESSAGE_UPDATE","CONTACTS_SET","CONTACTS_UPSERT","CONTACTS_UPDATE","PRESENCE_UPDATE","CHATS_SET","CHATS_UPSERT","CHATS_UPDATE","CHATS_DELETE","GROUPS_UPSERT","GROUP_UPDATE","GROUP_PARTICIPANTS_UPDATE","CONNECTION_UPDATE","LABELS_EDIT","LABELS_ASSOCIATION","CALL","TYPEBOT_START","TYPEBOT_CHANGE_STATUS","REMOVE_INSTANCE","LOGOUT_INSTANCE","INSTANCE_CREATE","INSTANCE_DELETE","STATUS_INSTANCE"}

class Service:
 def __init__(self,store:Store,mode:str,client:EvolutionClient|None=None): self.store,self.mode,self.client=store,mode,client
 def doctor(self): return {"brand":"AD3 Digital","mode":self.mode,"network":"disabled" if self.mode=="demo" else "configured","profile":"evolution-2.3.7","ok":True}
 def api_read(self, operation, instance=None, params=None, payload=None, query=None):
  request=self._api_request(operation,instance,params,payload,query); spec=api_operation(operation)
  if spec.restricted: raise PlanError("operation is restricted because its response contains credentials")
  if spec.download_file: raise PlanError("operation returns media; use api download with --output-file")
  if not spec.read_only: raise PlanError("operation requires an explicit api plan and apply")
  if self.mode=="demo": return {"status":"simulated","operation":operation,"method":spec.method}
  kwargs={"payload":request["payload"],"query":request["query"]}
  if request["params"]: kwargs["params"]=request["params"]
  return self.client.request(operation,request["instance"] or "",**kwargs)
 def api_download(self, operation, instance=None, params=None, payload=None, query=None, output_file=None):
  request=self._api_request(operation,instance,params,payload,query); spec=api_operation(operation)
  if spec.restricted: raise PlanError("operation is restricted because its response contains credentials")
  if not spec.download_file: raise PlanError("operation does not return a downloadable media file")
  if self.mode=="demo": raise PlanError("media download requires a remote or local Evolution instance")
  try: output=Path(output_file).expanduser().resolve()
  except (OSError,TypeError,ValueError): raise PlanError("output file is invalid") from None
  if not output.name or not output.parent.is_dir(): raise PlanError("output directory does not exist")
  kwargs={"payload":request["payload"],"query":request["query"]}
  if request["params"]: kwargs["params"]=request["params"]
  data=self._base64_media(self.client.request(operation,request["instance"] or "",**kwargs))
  try:
   with output.open("xb") as handle: handle.write(data)
  except FileExistsError: raise PlanError("output file already exists") from None
  except OSError: raise PlanError("media file cannot be written") from None
  return {"status":"downloaded","operation":operation,"file":str(output),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
 def _base64_media(self,response):
  values=[]
  def collect(value,name=None):
   if isinstance(value,dict):
    for child_name,child in value.items(): collect(child,child_name)
   elif isinstance(value,list):
    for child in value: collect(child,name)
   elif isinstance(value,str) and (str(name).lower()=="base64" or value.startswith("data:")): values.append(value)
  collect(response)
  if len(values)!=1: raise PlanError("Evolution response did not contain one Base64 media value")
  encoded=values[0]
  if encoded.startswith("data:"):
   header,separator,encoded=encoded.partition(",")
   if not separator or ";base64" not in header.lower(): raise PlanError("Evolution media response is not Base64")
  try: return base64.b64decode(encoded,validate=True)
  except (ValueError,binascii.Error): raise PlanError("Evolution media response is not valid Base64") from None
 def api_plan(self, operation, instance=None, params=None, payload=None, query=None, file_path=None, file_field="file"):
  spec=api_operation(operation)
  if spec.restricted: raise PlanError("operation is restricted because its response contains credentials")
  if spec.download_file: raise PlanError("operation returns media; use api download with --output-file")
  return self.plan("api",self._api_request(operation,instance,params,payload,query,file_path,file_field))
 def _api_request(self, operation, instance, params, payload, query, file_path=None, file_field="file"):
  try: spec=api_operation(operation)
  except ValueError as exc: raise PlanError(str(exc)) from None
  if not all(value is None or isinstance(value,dict) for value in (params,payload,query)): raise PlanError("API params, payload, and query must be JSON objects")
  request={"operation":operation,"instance":instance,"params":dict(params or {}),"payload":dict(payload or {}),"query":dict(query or {})}
  if file_path is not None:
   if not spec.upload_file: raise PlanError("operation does not accept a file upload")
   request["file"]=self._api_file_metadata(file_path,file_field)
  self._validate_api(request)
  return request
 def _api_file_metadata(self, file_path, file_field):
  if not isinstance(file_field,str) or not file_field.strip(): raise PlanError("upload field is invalid")
  try: path=Path(file_path).expanduser().resolve(strict=True)
  except (OSError,TypeError,ValueError): raise PlanError("upload file cannot be read") from None
  if not path.is_file(): raise PlanError("upload file cannot be read")
  return {"path":str(path),"sha256":self._file_digest(path),"size":path.stat().st_size,"field":file_field}
 @staticmethod
 def _file_digest(path):
  digest=hashlib.sha256()
  with Path(path).open("rb") as handle:
   for chunk in iter(lambda:handle.read(1024*1024),b""): digest.update(chunk)
  return digest.hexdigest()
 def _envelope(self,envelope):
  if not isinstance(envelope,dict): raise PlanError("Evolution response is invalid")
  # Evolution 2.3.7 uses only direct bodies or one explicit data wrapper here.
  return envelope["data"] if isinstance(envelope.get("data"),dict) else envelope
 def _items(self,envelope,*keys):
  if isinstance(envelope,list): return envelope
  body=self._envelope(envelope)
  for key in keys:
   if isinstance(body.get(key),list): return body[key]
  if isinstance(body.get("data"),list): return body["data"]
  raise PlanError("Evolution collection response is invalid")
 def instances(self): return self.store.state("instances",[{"name":"creator","state":"open"},{"name":"support","state":"open"},{"name":"client","state":"open"}]) if self.mode=="demo" else self._items(self.client.request("instance_list"),"instances")
 def group_list(self,instance):
  self._instance(instance)
  return self.store.state("groups",[]) if self.mode=="demo" else self._items(self.client.request("group_list",instance,query={"getParticipants":"false"}),"groups")
 def group_info(self,instance,jid):
  self._instance(instance); self._group_jid(jid)
  if self.mode=="demo": return next((group for group in self.store.state("groups",[]) if group.get("jid")==jid),{})
  return self._group_body(self.client.request("group_info",instance,query={"groupJid":jid}))
 def group_participants(self,instance,jid):
  self._instance(instance); self._group_jid(jid)
  if self.mode=="demo":
   _,group=self._group(jid); admins=set(group.get("admins",[]))
   return [{"phoneNumber":value,"admin":value in admins} if isinstance(value,str) and value.isdigit() else {"id":value,"admin":value in admins} for value in group.get("participants",[])]
  return self._items(self.client.request("group_participants",instance,query={"groupJid":jid}),"participants")
 def _invite_code(self,value):
  if not isinstance(value,str) or not re.fullmatch(r"[A-Za-z0-9]{8,128}",value): raise PlanError("invite code is invalid")
  return value
 def invite_info(self,instance,code):
  self._instance(instance); code=self._invite_code(code)
  if self.mode=="demo": return next((group for group in self.store.state("groups",[]) if group.get("invite")==code),{})
  return self._envelope(self.client.request("invite_info",instance,query={"inviteCode":code}))
 def whatsapp_numbers(self,instance,numbers):
  self._instance(instance)
  if not isinstance(numbers,list) or not 1<=len(numbers)<=100: raise PlanError("numbers must contain between 1 and 100 phone numbers")
  values=list(dict.fromkeys(self._normalize_group_phone(value) for value in numbers))
  if self.mode=="demo": return {"numbers":[{"number":value,"exists":not self.store.blacklisted(value)} for value in values]}
  raw=self.client.request("whatsapp_validate",instance,{"numbers":values})
  return raw if isinstance(raw,list) else self._envelope(raw)
 def webhook_info(self,instance):
  self._instance(instance)
  raw=self.store.state("last_webhook_set",{}).get("webhook",{}) if self.mode=="demo" else self._envelope(self.client.request("webhook_find",instance))
  raw=raw.get("webhook",raw) if isinstance(raw,dict) else {}
  return self._webhook_summary(raw)
 def chat_list(self,instance,limit):
  limit=self._read_limit(limit)
  if self.mode=="demo": return self.store.state("chats",[])[:limit]
  self._instance(instance)
  return self.client.request("chat_list",instance,{"take":limit})
 def message_history(self,instance,jid,limit):
  limit=self._read_limit(limit)
  self._instance(instance)
  try: validate_chat_jid(jid)
  except ValueError as exc: raise PlanError(str(exc)) from None
  if self.mode=="demo": return [x for x in self.store.state("messages",[]) if x.get("key",{}).get("remoteJid")==jid][:limit]
  return self.client.request("message_history",instance,{"where":{"key":{"remoteJid":jid}},"take":limit})
 def _read_limit(self,limit):
  try: value=int(limit)
  except (TypeError,ValueError): raise PlanError("limit must be between 1 and 100")
  if not 1<=value<=100: raise PlanError("limit must be between 1 and 100")
  return value
 def _connected(self,name):
  self._instance(name)
  if self.mode=="demo": return any(x.get("name")==name and x.get("state") in ("open","connected") for x in self.instances())
  state=self._envelope(self.client.request("instance_status",name)); return str(state.get("instance",{}).get("state",state.get("state",""))).lower() in ("open","connected")
 def plan(self,kind,payload,ttl=900):
  self._validate_common(kind,payload)
  if kind=="api": self._validate_api(payload)
  if kind in {"instance_create","instance_connect"} and payload.get("qr_file"):
   target=Path(payload["qr_file"]).resolve(); root=self.store.path.parent
   if target.suffix.lower()!='.png' or root not in target.parents: raise PlanError("qr_file must be a PNG inside the local state directory")
  if kind=="onboarding": self._validate_onboarding(payload)
  if kind=="group_setup": self._validate_group_setup(payload)
  if kind=="webhook_set": self._validate_webhook(payload)
  if kind in {"message_text","message_media"} and "number" in payload and "@g.us" not in payload["number"].lower() and self.store.blacklisted(payload["number"]): raise PlanError("target is blacklisted")
  for phone in payload.get("phones",[]):
   if self.store.blacklisted(phone): raise PlanError("target is blacklisted")
  return self.store.plan(kind,payload,ttl)
 def _instance(self,value):
  try: return validate_instance(value)
  except ValueError as exc: raise PlanError(str(exc)) from None
 def _group_jid(self,value):
  try: return validate_group_jid(value)
  except ValueError as exc: raise PlanError(str(exc)) from None
 def _validate_common(self,kind,p):
  for name in ("instance","creator_instance","welcome_instance"):
   if p.get(name) is not None: self._instance(p[name])
  for name in ("participant_instances","admin_instances"):
   if name in p:
    if not isinstance(p[name],list): raise PlanError(f"{name} is invalid")
    for item in p[name]: self._instance(item)
  if "groupJid" in p: self._group_jid(p["groupJid"])
  if p.get("existing_jid") is not None: self._group_jid(p["existing_jid"])
  if "phones" in p:
   if not isinstance(p["phones"],list): raise PlanError("phones are invalid")
   p["phones"]=list(dict.fromkeys(self._normalize_group_phone(phone) for phone in p["phones"]))
  if "number" in p:
   number=p["number"]
   try: p["number"] = self._group_jid(number) if isinstance(number,str) and "@" in number else self._normalize_group_phone(number)
   except PlanError: raise PlanError("message recipient is invalid") from None
 def _validate_api(self,p):
  required_fields={"operation","instance","params","payload","query"}
  allowed_fields=required_fields|{"file"}
  if not isinstance(p,dict) or not required_fields<=set(p) or set(p)-allowed_fields: raise PlanError("API request is invalid")
  try:
   operation=api_operation(p["operation"]); required_params=set(api_path_parameters(p["operation"]))
  except ValueError as exc: raise PlanError(str(exc)) from None
  if "instance" in required_params: self._instance(p["instance"])
  elif p["instance"] is not None: raise PlanError("operation does not accept an instance")
  if not all(isinstance(p[name],dict) and all(isinstance(key,str) for key in p[name]) for name in ("params","payload","query")): raise PlanError("API params, payload, and query must be JSON objects")
  if set(p["params"])!=required_params-{"instance"}: raise PlanError("route parameters do not match operation")
  for value in p["params"].values():
   if not isinstance(value,str) or not value or any(char in value for char in "/\\?#") or any(ord(char)<32 or ord(char)==127 for char in value): raise PlanError("route parameter is invalid")
  file=p.get("file")
  if file is not None:
   if not operation.upload_file or not isinstance(file,dict) or set(file)!={"path","sha256","size","field"}: raise PlanError("upload metadata is invalid")
   if not isinstance(file["path"],str) or not Path(file["path"]).is_absolute() or not re.fullmatch(r"[0-9a-f]{64}",str(file["sha256"])) or not isinstance(file["size"],int) or file["size"]<0 or not isinstance(file["field"],str) or not file["field"].strip(): raise PlanError("upload metadata is invalid")
  self._validate_api_targets(p["payload"])
  self._validate_api_targets(p["query"])
 def _validate_api_targets(self,value,key=None):
  if isinstance(value,dict):
   for child_key,child in value.items(): self._validate_api_targets(child,child_key)
  elif isinstance(value,list):
   for child in value: self._validate_api_targets(child,key)
  elif key in {"number","phone","phoneNumber","phones","numbers","participants","remoteJid"} and isinstance(value,str):
   if value.lower().endswith("@lid"): raise PlanError("@lid identities are read-only and cannot target an API mutation")
   candidate=value.split("@",1)[0] if value.lower().endswith("@s.whatsapp.net") else value
   try: phone=normalize_phone(candidate)
   except ValueError: return
   if self.store.blacklisted(phone): raise PlanError("target is blacklisted")
 def _validate_onboarding(self,p):
  creator=p.get("creator_instance"); members=p.get("participant_instances",[]); admins=p.get("admin_instances",[])
  if not creator or creator in members or creator in admins or set(members)&set(admins) or len(members)!=len(set(members)) or len(admins)!=len(set(admins)): raise PlanError("creator, participant_instances and admin_instances must be mutually separate")
  try: p["client_phone"]=normalize_phone(p.get("client_phone"))
  except ValueError: raise PlanError("client phoneNumber is required; @lid-only identity fails closed") from None
  if not p.get("group_name"): raise PlanError("group_name is required")
  if p.get("existing_jid") is not None: self._group_jid(p["existing_jid"])
 def _validate_group_setup(self,p):
  creator=p.get("instance"); members=p.get("participant_instances",[]); admins=p.get("admin_instances",[]); phones=p.get("phones",[]); settings=p.get("settings",[])
  if not isinstance(creator,str) or not creator.strip(): raise PlanError("instance is required")
  if not isinstance(p.get("subject"),str) or not p["subject"].strip(): raise PlanError("subject is required")
  if not all(isinstance(items,list) for items in (members,admins,phones,settings)): raise PlanError("group setup lists are invalid")
  if creator in members or creator in admins or len(members)!=len(set(members)) or len(admins)!=len(set(admins)) or set(members)&set(admins): raise PlanError("creator, participant_instances and admin_instances must be mutually separate")
  if any(not isinstance(x,str) or not x.strip() for x in [*members,*admins]): raise PlanError("participant and admin instances are required")
  if p.get("existing_jid") is not None: self._group_jid(p["existing_jid"])
  normalized=[]
  for phone in phones:
   value=self._normalize_group_phone(phone)
   if self.store.blacklisted(phone) or self.store.blacklisted(value): raise PlanError("target is blacklisted")
   normalized.append(value)
  p["phones"]=list(dict.fromkeys(normalized))
  allowed={"announcement","not_announcement","locked","unlocked"}
  if any(setting not in allowed for setting in settings): raise PlanError("unsupported group setting")
  if ({"announcement","not_announcement"}<=set(settings)) or ({"locked","unlocked"}<=set(settings)): raise PlanError("contradictory group settings")
 def _normalize_group_phone(self,phone):
  try: return normalize_phone(phone)
  except ValueError as exc: raise PlanError(str(exc)) from None
 def _validate_webhook(self,p):
  if set(p)!={"instance","webhook"} or not isinstance(p.get("webhook"),dict): raise PlanError("webhook plan must contain instance and webhook")
  webhook=p["webhook"]
  if set(webhook)!={"enabled","url","headers","byEvents","base64","events"}: raise PlanError("webhook payload is invalid")
  if not all(isinstance(webhook[name],bool) for name in ("enabled","byEvents","base64")) or not isinstance(webhook["headers"],dict) or webhook["headers"]: raise PlanError("webhook booleans and empty headers are required")
  if not isinstance(webhook["events"],list) or any(event not in WEBHOOK_EVENTS for event in webhook["events"]): raise PlanError("unsupported webhook event")
  webhook["events"]=list(dict.fromkeys(webhook["events"]))
  if not isinstance(webhook["url"],str): raise PlanError("webhook URL is invalid")
  parsed=urlsplit(webhook["url"])
  allowed=parsed.scheme=="https" or (parsed.scheme=="http" and parsed.hostname in {"localhost","127.0.0.1"})
  if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or not allowed: raise PlanError("webhook URL must be HTTPS or local HTTP without credentials, query, or fragment")
 def _webhook_summary(self,raw):
  raw=raw if isinstance(raw,dict) else {}; url=raw.get("url")
  origin=None
  if isinstance(url,str):
   parsed=urlsplit(url)
   if parsed.scheme and parsed.hostname: origin=f"{parsed.scheme}://{parsed.hostname}" + (f":{parsed.port}" if parsed.port else "")
  return {"enabled":bool(raw.get("enabled",False)),"events":[event for event in raw.get("events",[]) if isinstance(event,str)],"byEvents":bool(raw.get("byEvents",False)),"base64":bool(raw.get("base64",False)),"origin":origin,"destination_hash":digest_text(url) if isinstance(url,str) else None}
 def apply(self,plan_id,confirm): return self.store.apply(plan_id,confirm,self._execute)
 def _group(self,jid):
  groups=self.store.state("groups",[]); found=next((g for g in groups if g.get("jid")==jid),None)
  if not found: raise PlanError("demo group not found")
  return groups,found
 def _execute(self,kind,p,checkpoint=None): return self._demo_execute(kind,p,checkpoint) if self.mode=="demo" else self._remote_execute(kind,p,checkpoint)
 def _demo_execute(self,kind,p,checkpoint=None):
  groups=self.store.state("groups",[])
  if kind=="api": return {"status":"simulated","operation":p["operation"],"method":api_operation(p["operation"]).method}
  if kind=="instance_connect":
   items=self.instances(); found=next((x for x in items if x["name"]==p["instance"]),None)
   if not found: raise PlanError("demo instance not found")
   found["state"]="open"; self.store.save_state("instances",items); return {"status":"connected","pairing_code":"demo-qr"}
  if kind=="instance_create":
   items=self.instances()
   if any(x.get("name")==p["instance"] for x in items): raise PlanError("instance already exists; use connect-plan")
   items.append({"name":p["instance"],"state":"connecting"}); self.store.save_state("instances",items); return {"status":"created","instance":p["instance"],"pairing_code":"demo-qr"}
  if kind=="group_create":
   if p.get("existing_jid"):
    _,existing=self._group(p["existing_jid"])
    if existing.get("subject")!=p["subject"] or not set(p.get("phones",[]))<=set(existing.get("participants",[])): raise PlanError("existing group verification failed")
    if checkpoint: checkpoint({"group_jid":p["existing_jid"],"phase":"adopted"})
    return {"group_jid":p["existing_jid"],"status":"reconciled"}
   jid=f"{len(groups)+10000}-demo@g.us"; groups.append({"jid":jid,"subject":p["subject"],"description":"","picture":None,"participants":p.get("phones",[]),"admins":[],"settings":{},"invite":f"demoinvite{len(groups)+1}"}); self.store.save_state("groups",groups)
   if checkpoint: checkpoint({"group_jid":jid,"phase":"created"})
   return {"group_jid":jid,"status":"created"}
  if kind=="group_setup":
   for instance in [p["instance"],*p.get("participant_instances",[]),*p.get("admin_instances",[])]:
    if not self._connected(instance): raise PlanError("instance not connected")
   jid=p.get("existing_jid") or f"{len(groups)+10000}-demo@g.us"; participants=list(dict.fromkeys([*p.get("phones",[]),*p.get("participant_instances",[]),*p.get("admin_instances",[])]))
   if checkpoint: checkpoint({"group_jid":jid,"phase":"created" if not p.get("existing_jid") else "adopted"})
   if p.get("existing_jid"):
    found=next((g for g in groups if g.get("jid")==jid),None)
    if not found: raise PlanError("existing group not found in demo")
    found.update({"subject":p["subject"],"description":p.get("description", ""),"picture":p.get("picture"),"participants":participants,"admins":list(p.get("admin_instances",[])),"settings":{setting:True for setting in dict.fromkeys(p.get("settings",[]))},"status":"configured"}); self.store.save_state("groups",groups); return {"group_jid":jid,"status":"configured","verified":True,"admin_verification":"simulated"}
   item={"jid":jid,"subject":p["subject"],"description":p.get("description", ""),"picture":p.get("picture"),"participants":participants,"admins":list(p.get("admin_instances",[])),"settings":{setting:True for setting in dict.fromkeys(p.get("settings",[]))},"invite":f"demoinvite{len(groups)+1}","status":"configured"}
   groups.append(item); self.store.save_state("groups",groups); return {"group_jid":jid,"status":"configured","verified":True,"admin_verification":"simulated"}
  if kind=="onboarding":
   for instance in [p["creator_instance"],*p.get("participant_instances",[]),*p.get("admin_instances",[])]:
    if not self._connected(instance): raise PlanError(f"instance not connected: {instance}")
   jid=p.get("existing_jid") or f"{len(groups)+10000}-demo@g.us"; item=next((g for g in groups if g.get("jid")==jid),None)
   if item is None:
    item={"jid":jid,"subject":p["group_name"],"description":p.get("description", ""),"picture":p.get("picture"),"participants":[p["client_phone"],*p.get("participant_instances",[])],"admins":p.get("admin_instances",[]),"settings":{},"invite":f"demoinvite{len(groups)+1}","welcome_sent":False,"status":"onboarded"}; groups.append(item)
    if checkpoint: checkpoint({"group_jid":jid,"phase":"created"})
   elif checkpoint: checkpoint({"group_jid":jid,"phase":"adopted"})
   if p.get("existing_jid"): self.store.save_state("groups",groups); return {"group_jid":jid,"invite":item["invite"],"status":"reconciled","welcome":"not_sent"}
   item["welcome_sent"]=True; self.store.save_state("groups",groups); return {"group_jid":jid,"invite":item["invite"],"status":"onboarded","message":"simulated"}
  if kind.startswith("group_") or kind.startswith("participants_") or kind in {"invite_revoke","group_leave"}:
   groups,g=self._group(p["groupJid"])
   if kind=="group_subject": g["subject"]=p["subject"]
   elif kind=="group_description": g["description"]=p["description"]
   elif kind=="group_picture": g["picture"]=p["picture"]
   elif kind=="group_settings": g["settings"][p["setting"]]=p.get("value",True)
   elif kind.startswith("participants_"):
    action=kind.split("_",1)[1]; phones=p["phones"]
    if action=="add": g["participants"]=sorted(set(g["participants"]+phones))
    if action=="remove": g["participants"]=[x for x in g["participants"] if x not in phones]; g["admins"]=[x for x in g["admins"] if x not in phones]
    if action=="promote": g["admins"]=sorted(set(g["admins"]+phones))
    if action=="demote": g["admins"]=[x for x in g["admins"] if x not in phones]
   elif kind=="invite_revoke": g["invite"]="demo-revoked"
   elif kind=="group_leave": groups.remove(g)
   self.store.save_state("groups",groups); return {"status":"simulated","operation":kind}
  if kind in {"message_text","message_media","webhook_set","invite_send"}: self.store.save_state("last_"+kind,p); return {"status":"simulated","operation":kind}
  raise PlanError("unknown planned operation")
 def _remote_execute(self,kind,p,checkpoint=None):
  if kind=="api": return self._remote_api(p)
  if kind=="onboarding": return self._remote_onboarding(p,checkpoint)
  if kind=="group_setup": return self._remote_group_setup(p,checkpoint)
  if kind=="group_create" and p.get("existing_jid"):
   jid=self._group_jid(p["existing_jid"]); info=self._group_body(self.client.request("group_info",p["instance"],query={"groupJid":jid}))
   if self._group_jid_from(info)!=jid or info.get("subject")!=p["subject"]: raise PlanError("existing group verification failed")
   observed={str(x.get("phoneNumber") or x.get("number") or x.get("id") or x.get("jid") or "").replace("+","").split("@")[0] for x in info.get("participants",[]) if isinstance(x,dict)}
   if not set(p.get("phones",[]))<=observed: raise PlanError("existing group participants were not confirmed")
   if checkpoint: checkpoint({"group_jid":jid,"phase":"adopted"})
   return {"group_jid":jid,"status":"reconciled"}
  mapping={"instance_create":"instance_create","instance_connect":"instance_qr","group_create":"group_create","group_subject":"group_subject","group_description":"group_description","group_picture":"group_picture","group_settings":"group_settings","message_text":"send_text","message_media":"send_media","webhook_set":"webhook_set","invite_send":"invite_send"}
  if kind.startswith("participants_"): return self.client.request({"participants_add":"participants_add","participants_remove":"participants_remove","participants_promote":"participants_promote","participants_demote":"participants_demote"}[kind],p["instance"],{"groupJid":p["groupJid"],"action":kind.split("_",1)[1],"participants":p["phones"]})
  if kind=="invite_revoke": return self.client.request(kind,p["instance"],{"groupJid":p["groupJid"]})
  if kind=="group_leave": return self.client.request(kind,p["instance"],query={"groupJid":p["groupJid"]})
  op=mapping.get(kind)
  if not op: raise PlanError("remote operation has no explicit safe route contract")
  body=dict(p)
  if kind=="instance_create": body={"instanceName":p["instance"],"integration":"WHATSAPP-BAILEYS","qrcode":True}
  if kind=="group_create": body={"subject":p["subject"],"participants":p.get("phones",[]),"description":p.get("description","")}
  if kind=="message_text": body={"number":p["number"],"text":p["content"]}
  if kind=="message_media": body={k:v for k,v in {"number":p["number"],"mediatype":p["mediatype"],"media":p["media"],"caption":p.get("caption"),"fileName":p.get("fileName"),"mimetype":p.get("mimetype")}.items() if v is not None}
  if kind=="invite_send": body={"groupJid":p["groupJid"],"description":p.get("description",""),"numbers":p["phones"]}
  if kind=="group_picture": body["image"]=body.pop("picture")
  if kind=="group_settings": body={"groupJid":p["groupJid"],"action":p["setting"]}
  if kind=="webhook_set": body={"webhook":p.get("webhook",p)}
  result=self.client.request(op,p.get("instance",""),body)
  if kind=="group_create":
   jid=self._group_jid_from(result)
   if checkpoint: checkpoint({"group_jid":jid,"phase":"created"})
   return {"group_jid":jid,"status":"created"}
  if kind in {"instance_create","instance_connect"}: return self._sanitize_qr(result,p)
  return result
 def _remote_api(self,p):
  file=p.get("file")
  if file:
   path=Path(file["path"])
   try: unchanged=path.is_file() and path.stat().st_size==file["size"] and self._file_digest(path)==file["sha256"]
   except OSError: unchanged=False
   if not unchanged: raise PlanError("planned upload file changed; create a new plan")
  kwargs={"payload":p["payload"],"query":p["query"]}
  if p["params"]: kwargs["params"]=p["params"]
  if file: kwargs.update({"file_path":path,"file_field":file["field"]})
  return self.client.request(p["operation"],p["instance"] or "",**kwargs)
 def _sanitize_qr(self,result,p):
  qr=result.get("qrcode",{}) if isinstance(result,dict) else {}; pairing=qr.get("pairingCode") or (result.get("pairingCode") if isinstance(result,dict) else None); saved=None
  if qr.get("base64") and p.get("qr_file"):
   target=Path(p["qr_file"]).resolve(); root=self.store.path.parent
   if root not in target.parents: raise PlanError("qr_file must stay inside the local state directory")
   if target.suffix.lower()!='.png': raise PlanError("qr_file must end in .png")
   target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(base64.b64decode(qr["base64"].split(',',1)[-1])); saved=str(target)
  return {"status":"qr_available","instance":p.get("instance"),"pairing_code":pairing,"qr_file":saved}
 def _group_body(self, envelope):
  body=self._envelope(envelope)
  body=body.get("group",body)
  if not isinstance(body,dict): raise PlanError("group response is invalid")
  return body
 def _group_jid_from(self,envelope):
  group=self._group_body(envelope); jid=group.get("id") or group.get("groupJid") or group.get("jid")
  return self._group_jid(jid)
 def _setting_observed(self,info,setting):
  # Evolution 2.3.7 exposes these either as booleans or as action-like strings.
  if setting in {"announcement","not_announcement"}:
   value=info.get("announce",info.get("announcement",info.get("isAnnounce")))
   desired=setting=="announcement"
  else:
   value=info.get("restrict",info.get("locked",info.get("isRestricted")))
   desired=setting=="locked"
  if isinstance(value,str): value=value.lower() in {"true","1","yes","announcement","locked"}
  if not isinstance(value,bool) or value is not desired: raise PlanError("group setup verification did not confirm settings")
 def _verify_group_identity(self,p,jid,expected_participants,info):
  returned=self._group_jid_from(info)
  if returned!=jid: raise PlanError("group setup verification returned another JID")
  if info.get("subject") != p["subject"]: raise PlanError("group setup verification did not confirm subject")
  participants=info.get("participants")
  if not isinstance(participants,list): raise PlanError("group setup verification did not return participants")
  members=[x for x in participants if isinstance(x,dict)]
  observed={str(x.get("phoneNumber") or x.get("number") or x.get("id") or x.get("jid") or "").split("@")[0].lstrip("+") for x in members}
  if not set(expected_participants)<=observed: raise PlanError("group setup verification did not confirm expected participants")
  return members
 def _preflight_group_setup(self,p,jid,expected_participants):
  info=self._group_body(self.client.request("group_info",p["instance"],query={"groupJid":jid}))
  self._verify_group_identity(p,jid,expected_participants,info)
 def _verify_group_setup(self,p,jid,admin_owners,expected_participants):
  info=self._group_body(self.client.request("group_info",p["instance"],query={"groupJid":jid}))
  members=self._verify_group_identity(p,jid,expected_participants,info)
  if p.get("description") and info.get("description") != p["description"]: raise PlanError("group setup verification did not confirm description")
  for setting in dict.fromkeys(p.get("settings",[])): self._setting_observed(info,setting)
  observed={str(x.get("phoneNumber") or x.get("number") or x.get("id") or x.get("jid") or "").split("@")[0].lstrip("+") for x in members}
  if not set(admin_owners)<=observed: raise PlanError("group setup verification did not confirm requested admins")
  role_fields={"admin","isAdmin","is_admin","role","participantRole","participant_role"}
  if admin_owners and not any(any(key in item for key in role_fields) for item in members): raise PlanError("group setup verification did not confirm requested admin role")
  def is_admin(item):
   value=item.get("admin",item.get("isAdmin",item.get("is_admin",False))); role=str(item.get("role",item.get("participantRole",item.get("participant_role","")))).lower()
   return value is True or str(value).lower() in {"admin","superadmin","super_admin"} or role in {"admin","superadmin","super_admin"}
  for phone in admin_owners:
   if not any(str(item.get("phoneNumber") or item.get("number") or item.get("id") or item.get("jid") or "").split("@")[0].lstrip("+")==phone and is_admin(item) for item in members): raise PlanError("group setup verification did not confirm requested admin role")
  return "roles" if admin_owners else "not_applicable"
 def _remote_group_setup(self,p,checkpoint=None):
  creator=p["instance"]
  for name in [creator,*p.get("participant_instances",[]),*p.get("admin_instances",[])]:
   if not self._connected(name): raise PlanError("instance not connected")
  items=self._items(self.client.request("instance_list"),"instances")
  def owner(name):
   item=next((x for x in items if x.get("name")==name or x.get("instanceName")==name),None); phone=(item or {}).get("phoneNumber")
   if not phone: raise PlanError("instance owner phoneNumber unavailable")
   return self._normalize_group_phone(phone)
  participant_owners=[owner(name) for name in p.get("participant_instances",[])]; admin_owners=[owner(name) for name in p.get("admin_instances",[])]
  participants=list(dict.fromkeys([*p.get("phones",[]),*participant_owners,*admin_owners]))
  if p.get("existing_jid"):
   jid=self._group_jid(p["existing_jid"])
   self._preflight_group_setup(p,jid,participants)
   if checkpoint: checkpoint({"group_jid":jid,"phase":"adopted"})
  else:
   created=self.client.request("group_create",creator,{"subject":p["subject"],"participants":participants,"description":p.get("description","")})
   jid=self._group_jid_from(created)
   if checkpoint: checkpoint({"group_jid":jid,"phase":"created"})
  try:
   if p.get("description"):
    if checkpoint: checkpoint({"group_jid":jid,"phase":"description"})
    self.client.request("group_description",creator,{"groupJid":jid,"description":p["description"]})
   if p.get("picture"):
    if checkpoint: checkpoint({"group_jid":jid,"phase":"picture"})
    self.client.request("group_picture",creator,{"groupJid":jid,"image":p["picture"]})
   if admin_owners:
    if checkpoint: checkpoint({"group_jid":jid,"phase":"admins"})
    self.client.request("participants_promote",creator,{"groupJid":jid,"action":"promote","participants":list(dict.fromkeys(admin_owners))})
   for setting in dict.fromkeys(p.get("settings",[])):
    if checkpoint: checkpoint({"group_jid":jid,"phase":"settings"})
    self.client.request("group_settings",creator,{"groupJid":jid,"action":setting})
   if checkpoint: checkpoint({"group_jid":jid,"phase":"verify"})
   admin_verification=self._verify_group_setup(p,jid,admin_owners,participants)
  except Exception as exc:
   raise PlanError("group setup uncertain after creation; use plan-status and resume with --existing-jid") from exc
  return {"group_jid":jid,"status":"configured","verified":True,"admin_verification":admin_verification}
 def _remote_onboarding(self,p,checkpoint=None):
  for name in [p["creator_instance"],*p.get("participant_instances",[]),*p.get("admin_instances",[])]:
   if not self._connected(name): raise PlanError(f"instance not connected: {name}")
  items=self._items(self.client.request("instance_list"),"instances")
  def owner(name):
   item=next((x for x in items if x.get("name")==name or x.get("instanceName")==name),None); phone=(item or {}).get("phoneNumber")
   if not phone: raise PlanError(f"instance owner phoneNumber unavailable: {name}")
   return self._normalize_group_phone(phone)
  additions=[owner(x) for x in p.get("participant_instances",[])]; admins=[owner(x) for x in p.get("admin_instances",[])]
  additions=list(dict.fromkeys(additions+admins)); admins=list(dict.fromkeys(admins))
  creator=p["creator_instance"]; valid=self.client.request("whatsapp_validate",creator,{"numbers":[p["client_phone"]]})
  valid_items=self._items(valid,"numbers")
  if not any((isinstance(x,dict) and x.get("exists",True) and str(x.get("number") or x.get("jid") or "").split("@")[0]==p["client_phone"]) or x==p["client_phone"] for x in valid_items): raise PlanError("client phoneNumber failed WhatsApp validation")
  if p.get("existing_jid"):
   jid=self._group_jid(p["existing_jid"])
   if checkpoint: checkpoint({"group_jid":jid,"phase":"adopted"})
  else:
   created=self.client.request("group_create",creator,{"subject":p["group_name"],"participants":[p["client_phone"]],"description":p.get("description","")}); jid=self._group_jid_from(created)
   if checkpoint: checkpoint({"group_jid":jid,"phase":"created"})
  if p.get("description"): self.client.request("group_description",creator,{"groupJid":jid,"description":p["description"]})
  if p.get("picture"): self.client.request("group_picture",creator,{"groupJid":jid,"image":p["picture"]})
  if additions: self.client.request("participants_add",creator,{"groupJid":jid,"action":"add","participants":additions})
  if admins: self.client.request("participants_promote",creator,{"groupJid":jid,"action":"promote","participants":admins})
  info=self._group_body(self.client.request("group_info",creator,query={"groupJid":jid}))
  if self._group_jid_from(info)!=jid or info.get("subject")!=p["group_name"]: raise PlanError("group setup verification unavailable")
  members=info.get("participants",[])
  observed={str(x.get("phoneNumber") or x.get("number") or x.get("id") or x.get("jid") or "").replace("+","").split("@")[0] for x in members if isinstance(x,dict)}
  expected={p["client_phone"],*additions}
  if not expected<=observed: raise PlanError("participant verification did not confirm expected members; welcome aborted")
  for admin in admins:
   match=next((x for x in members if isinstance(x,dict) and str(x.get("phoneNumber") or x.get("number") or x.get("id") or x.get("jid") or "").replace("+","").split("@")[0]==admin),None)
   role=str((match or {}).get("role",(match or {}).get("participantRole",""))).lower()
   if not match or not ((match.get("admin") is True) or (match.get("isAdmin") is True) or role in {"admin","superadmin","super_admin"}): raise PlanError("admin verification did not confirm requested admins; welcome aborted")
  if p.get("existing_jid"): return {"group_jid":jid,"status":"reconciled","welcome":"not_sent"}
  welcome_instance=p.get("welcome_instance") or (p.get("admin_instances") or [creator])[0]
  if not self._connected(welcome_instance): raise PlanError("welcome instance is not connected")
  self.client.request("send_text",welcome_instance,{"number":jid,"text":p.get("welcome","")}); invite=self.client.request("invite_get",creator,query={"groupJid":jid})
  return {"group_jid":jid,"invite":invite,"status":"onboarded","message":"sent"}

from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

from . import __version__
from .agent_protocol import capabilities, encode_jsonl, run_batch
from .branding import banner, donation_text
from .client import EvolutionClient, EvolutionError
from .config import Config
from .profiles import api_catalog
from .security import redact, safe_error
from .service import Service
from .store import Store, PlanError

def out(value, pretty=False):
 print(json.dumps(redact(value), ensure_ascii=False, sort_keys=True, indent=2 if pretty else None, separators=None if pretty else (",", ":")))

# Assinaturas de mojibake: UTF-8 lido como latin1/cp1252. Pares, nunca letra isolada:
# "A" com til sozinho e legitimo em caixa alta (REUNIAO, PROMOCAO acentuados).
_MOJIBAKE = ("Ã¡","Ã¢","Ã£","Ã§","Ã©","Ãª","Ã­","Ã³","Ã´","Ãµ","Ãº","Ã¼","Â ","Â´","Â¨","Âº","Âª","�")

def read_message(value, file_name):
 """Texto da mensagem por --content, --content-file ou stdin, sempre em UTF-8.

 Passar mensagem em argumento deixa o texto do cliente visivel na lista de processos
 e no historico do shell. stdin e arquivo existem para evitar isso; --content continua
 aceito por compatibilidade. A decodificacao e UTF-8 explicita: `sys.stdin.read()` usa
 a codificacao do sistema e, num PowerShell pt-BR, corrompe texto acentuado antes de
 qualquer chamada de rede.
 """
 if file_name:
  try: text=__import__("pathlib").Path(file_name).read_text(encoding="utf-8-sig")
  except UnicodeDecodeError: raise SystemExit("arquivo de mensagem nao esta em UTF-8")
  except OSError: raise SystemExit("arquivo de mensagem nao pode ser lido")
 elif value is not None:
  text=value
 else:
  if sys.stdin.isatty(): raise SystemExit("informe --content, --content-file ou envie o texto por stdin")
  raw=sys.stdin.buffer.read()
  if raw.startswith(b"\xef\xbb\xbf"): raw=raw[3:]
  try: text=raw.decode("utf-8")
  except UnicodeDecodeError: raise SystemExit("a mensagem nao chegou em UTF-8; no PowerShell defina [Console]::OutputEncoding e $OutputEncoding para UTF8")
 if not text.strip(): raise SystemExit("mensagem vazia")
 achados=[m for m in _MOJIBAKE if m in text]
 if achados: raise SystemExit("mensagem contem mojibake e nao foi enviada: "+", ".join(repr(x) for x in achados))
 return text
def read_json_object(value, file_name, label):
 if value is not None and file_name: raise SystemExit(f"informe somente --{label} ou --{label}-file")
 if file_name:
  try: raw=Path(file_name).read_text(encoding="utf-8-sig")
  except UnicodeDecodeError: raise SystemExit(f"arquivo de {label} nao esta em UTF-8")
  except OSError: raise SystemExit(f"arquivo de {label} nao pode ser lido")
 elif value is not None:
  raw=value
 else:
  return {}
 try: parsed=json.loads(raw)
 except (TypeError,json.JSONDecodeError): raise SystemExit(f"{label} precisa ser um objeto JSON valido")
 if not isinstance(parsed,dict): raise SystemExit(f"{label} precisa ser um objeto JSON")
 return parsed


def read_path_params(values):
 parsed={}
 for raw in values:
  key,separator,value=raw.partition("=")
  if not separator or not value or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*",key): raise SystemExit("parametros de rota usam NOME=VALOR")
  if key in parsed: raise SystemExit("parametro de rota repetido")
  parsed[key]=value
 return parsed


def parser():
 p=argparse.ArgumentParser(prog="ad3-evolution", description="EVOLUTION AD3 DIGITAL | WhatsApp Evolution seguro por planos", epilog="Use 'ad3-evolution donate' para apoiar a ferramenta.")
 p.add_argument("--version", action="version", version=__version__)
 p.add_argument("--pretty", action="store_true", help="formata saídas humanas dos comandos legados")
 p.add_argument("--mode", choices=["demo","remote","local"], default=None); p.add_argument("--state-dir")
 sub=p.add_subparsers(dest="cmd", required=True); sub.add_parser("doctor")
 donate=sub.add_parser("donate", help="mostra Pix de doação offline"); donate.add_argument("--no-color",action="store_true",help="renderiza QR sem ANSI")
 sub.add_parser("capabilities")
 agent=sub.add_parser("agent").add_subparsers(dest="agent_cmd",required=True); batch=agent.add_parser("batch"); batch.add_argument("--input-file")
 apply=sub.add_parser("apply"); apply.add_argument("--plan-id",required=True); apply.add_argument("--confirm",required=True)
 status_plan=sub.add_parser("plan-status"); status_plan.add_argument("--id",required=True)
 inst=sub.add_parser("instance").add_subparsers(dest="instance_cmd",required=True)
 inst.add_parser("list"); status=inst.add_parser("status"); status.add_argument("--instance",required=True); con=inst.add_parser("connect-plan"); con.add_argument("--instance",required=True); con.add_argument("--qr-file"); ic=inst.add_parser("create-plan"); ic.add_argument("--instance",required=True); ic.add_argument("--qr-file")
 chat=sub.add_parser("chat").add_subparsers(dest="chat_cmd",required=True); chat_list=chat.add_parser("list"); chat_list.add_argument("--instance",required=True); chat_list.add_argument("--limit",default=20); chat_messages=chat.add_parser("messages"); chat_messages.add_argument("--instance",required=True); chat_messages.add_argument("--jid",required=True); chat_messages.add_argument("--limit",default=20); recipient=chat.add_parser("recipient"); recipient.add_argument("--instance",required=True); recipient.add_argument("--chat-id",required=True)
 group=sub.add_parser("group").add_subparsers(dest="group_cmd",required=True); gl=group.add_parser("list"); gl.add_argument("--instance",required=True); info=group.add_parser("info"); info.add_argument("--instance",required=True); info.add_argument("--jid",required=True); participants=group.add_parser("participants"); participants.add_argument("--instance",required=True); participants.add_argument("--jid",required=True)
 create=group.add_parser("create"); create.add_argument("--instance",required=True); create.add_argument("--subject",required=True); create.add_argument("--existing-jid"); create.add_argument("--phone",dest="phones",action="append",default=[])
 setup=group.add_parser("setup-plan"); setup.add_argument("--instance",required=True); setup.add_argument("--subject",required=True); setup.add_argument("--description",default=""); setup.add_argument("--picture"); setup.add_argument("--existing-jid"); setup.add_argument("--phone",dest="phones",action="append",default=[]); setup.add_argument("--participant-instance",action="append",default=[]); setup.add_argument("--admin-instance",action="append",default=[]); setup.add_argument("--setting",action="append",default=[])
 update=group.add_parser("update").add_subparsers(dest="update_cmd",required=True)
 for name,field in (("subject","subject"),("description","description"),("picture","picture"),("settings","setting")):
  x=update.add_parser(name); x.add_argument("--instance",required=True); x.add_argument("--jid",required=True); x.add_argument("--value",required=True,choices=["announcement","locked","unlocked","not_announcement"] if name=="settings" else None); x.set_defaults(field=field)
 parts=update.add_parser("participants"); parts.add_argument("--instance",required=True); parts.add_argument("--jid",required=True); parts.add_argument("--action",choices=["add","remove","promote","demote"],required=True); parts.add_argument("--phone",dest="phones",action="append",required=True)
 invite=group.add_parser("invite").add_subparsers(dest="invite_cmd",required=True)
 for name in ("get","revoke","send"):
  x=invite.add_parser(name); x.add_argument("--instance",required=True); x.add_argument("--jid",required=True)
  if name=="send": x.add_argument("--phone",dest="phones",action="append",required=True); x.add_argument("--description",default="Convite do grupo AD3 Digital")
 resolve=invite.add_parser("resolve"); resolve.add_argument("--instance",required=True); resolve.add_argument("--code",required=True)
 leave=group.add_parser("leave"); leave.add_argument("--instance",required=True); leave.add_argument("--jid",required=True)
 msg=sub.add_parser("message").add_subparsers(dest="message_cmd",required=True)
 x=msg.add_parser("plan-text"); x.add_argument("--instance",required=True); target=x.add_mutually_exclusive_group(required=True); target.add_argument("--number"); target.add_argument("--chat-id"); x.add_argument("--content"); x.add_argument("--content-file",dest="content_file")
 x=msg.add_parser("plan-media"); x.add_argument("--instance",required=True); x.add_argument("--number",required=True); x.add_argument("--mediatype",required=True); x.add_argument("--media",required=True); x.add_argument("--caption",default=""); x.add_argument("--file-name"); x.add_argument("--mimetype")
 number=sub.add_parser("number").add_subparsers(dest="number_cmd",required=True); check=number.add_parser("check"); check.add_argument("--instance",required=True); check.add_argument("--number",dest="numbers",action="append",required=True)
 webhook=sub.add_parser("webhook").add_subparsers(dest="webhook_cmd",required=True); get=webhook.add_parser("get"); get.add_argument("--instance",required=True); set_plan=webhook.add_parser("set-plan"); set_plan.add_argument("--instance",required=True); set_plan.add_argument("--url",required=True); set_plan.add_argument("--event",dest="events",action="append",default=[]); set_plan.add_argument("--enabled",action=argparse.BooleanOptionalAction,default=True); set_plan.add_argument("--by-events",dest="by_events",action=argparse.BooleanOptionalAction,default=True); set_plan.add_argument("--base64",action=argparse.BooleanOptionalAction,default=False)
 bl=sub.add_parser("blacklist").add_subparsers(dest="blacklist_cmd",required=True)
 for name in ("add","remove"):
  x=bl.add_parser(name); x.add_argument("--phone",required=True)
 bl.add_parser("list")
 ob=sub.add_parser("onboarding").add_subparsers(dest="onboard_cmd",required=True); op=ob.add_parser("plan"); op.add_argument("--creator-instance",required=True); op.add_argument("--participant-instance",action="append",default=[]); op.add_argument("--admin-instance",action="append",default=[]); op.add_argument("--welcome-instance"); op.add_argument("--client-phone",required=True); op.add_argument("--group-name",required=True); op.add_argument("--description",default=""); op.add_argument("--picture"); op.add_argument("--welcome",default="Bem-vindo à AD3 Digital!"); oa=ob.add_parser("apply"); oa.add_argument("--plan-id",required=True); oa.add_argument("--confirm",required=True)
 op.add_argument("--existing-jid")
 api=sub.add_parser("api",help="acessa o catálogo integral Evolution 2.3.7")
 api_sub=api.add_subparsers(dest="api_cmd",required=True)
 catalog=api_sub.add_parser("catalog",help="lista operações e o modo de execução")
 catalog.add_argument("--prefix",help="filtra IDs pelo prefixo, por exemplo message.")
 def api_request(command):
  command.add_argument("--operation",required=True,help="ID retornado por api catalog")
  command.add_argument("--instance",help="instância quando a rota a exigir")
  command.add_argument("--param",dest="params",action="append",default=[],help="parâmetro de rota NOME=VALOR")
  payload=command.add_mutually_exclusive_group()
  payload.add_argument("--payload",help="objeto JSON; prefira --payload-file para dados sensíveis")
  payload.add_argument("--payload-file",dest="payload_file",help="arquivo JSON UTF-8")
  query=command.add_mutually_exclusive_group()
  query.add_argument("--query",help="objeto JSON de query string")
  query.add_argument("--query-file",dest="query_file",help="arquivo JSON UTF-8")
 api_read=api_sub.add_parser("read",help="executa somente operações catalogadas como leitura")
 api_request(api_read)
 api_download=api_sub.add_parser("download",help="salva mídia Base64 sem expô-la no terminal")
 api_request(api_download)
 api_download.add_argument("--output-file",required=True,help="novo arquivo de destino")
 api_plan=api_sub.add_parser("plan",help="cria plano para qualquer operação catalogada")
 api_request(api_plan)
 api_plan.add_argument("--file",help="arquivo para endpoint multipart compatível")
 api_plan.add_argument("--file-field",default="file",help="campo multipart; padrão: file")
 demo=sub.add_parser("demo").add_subparsers(dest="demo_cmd",required=True); demo.add_parser("reset"); demo.add_parser("status")
 return p

def utf8_stdio():
 """Escreve a saida em UTF-8 mesmo num console Windows em cp1252.

 `out` usa `ensure_ascii=False` para nao transformar acento e emoji em escapes.
 Num PowerShell pt-BR o stdout assume cp1252 e qualquer mensagem com emoji morre
 com UnicodeEncodeError depois da chamada de rede ja ter acontecido - a leitura
 foi feita e o operador nao ve nada. O terminal decide como desenhar; o processo
 nao pode decidir falhar.
 """
 for stream in (sys.stdout, sys.stderr):
  encoding=getattr(stream,"encoding",None) or ""
  if encoding.lower().replace("-","") in {"utf8","utf8sig"}: continue
  try: stream.reconfigure(encoding="utf-8",errors="backslashreplace")
  except (AttributeError,OSError,ValueError): pass

def main(argv=None):
 utf8_stdio()
 raw_argv=list(sys.argv[1:] if argv is None else argv)
 if not raw_argv:
  print(banner()); parser().print_help(); return 0
 if "--help" in raw_argv or "-h" in raw_argv:
  print(banner())
  try: parser().parse_args(raw_argv)
  except SystemExit as exc: return int(exc.code)
  return 0
 pretty_requested="--pretty" in raw_argv
 a=parser().parse_args([value for value in raw_argv if value!="--pretty"]); a.pretty=pretty_requested
 if a.cmd=="donate": print(donation_text(color=not a.no_color)); return 0
 if a.cmd=="capabilities": out(capabilities(),a.pretty); return 0
 if a.cmd=="api" and a.api_cmd=="catalog": out(api_catalog(a.prefix),a.pretty); return 0
 c=Config.load(a.mode,a.state_dir); s=Service(Store(c.database),c.mode,None if c.mode=="demo" else EvolutionClient(c.base_url,c.api_key,c.timeout))
 try:
  if a.cmd=="agent":
   try: raw=Path(a.input_file).read_bytes() if a.input_file else sys.stdin.buffer.read()
   except OSError: print("error: input file cannot be read",file=sys.stderr); return 2
   responses,failed=run_batch(s,raw); sys.stdout.write(encode_jsonl(responses)); return 2 if failed else 0
  if a.cmd=="api":
   params=read_path_params(a.params)
   payload=read_json_object(a.payload,a.payload_file,"payload")
   query=read_json_object(a.query,a.query_file,"query")
   if a.api_cmd=="read": out(s.api_read(a.operation,a.instance,params,payload,query),a.pretty); return 0
   if a.api_cmd=="download": out(s.api_download(a.operation,a.instance,params,payload,query,a.output_file),a.pretty); return 0
   out(s.api_plan(a.operation,a.instance,params,payload,query,a.file,a.file_field),a.pretty); return 0
  if a.cmd=="doctor": out(s.doctor(),a.pretty); return 0
  if a.cmd=="apply": out(s.apply(a.plan_id,a.confirm),a.pretty); return 0
  if a.cmd=="plan-status": out(s.store.plan_status(a.id),a.pretty); return 0
  if a.cmd=="instance":
   if a.instance_cmd=="list": out(s.instances(),a.pretty); return 0
   if a.instance_cmd=="status": out({"instance":a.instance,"connected":s._connected(a.instance)},a.pretty); return 0
   out(s.plan("instance_create" if a.instance_cmd=="create-plan" else "instance_connect",{"instance":a.instance,"qr_file":a.qr_file}),a.pretty); return 0
  if a.cmd=="chat":
   if a.chat_cmd=="list": out(s.chat_list(a.instance,a.limit),a.pretty); return 0
   if a.chat_cmd=="recipient": out({"chat_id":a.chat_id,"phone":s.recipient_from_chat(a.instance,a.chat_id)},a.pretty); return 0
   out(s.message_history(a.instance,a.jid,a.limit),a.pretty); return 0
  if a.cmd=="group":
   if a.group_cmd=="list": out(s.group_list(a.instance),a.pretty); return 0
   if a.group_cmd=="info": out(s.group_info(a.instance,a.jid),a.pretty); return 0
   if a.group_cmd=="participants": out(s.group_participants(a.instance,a.jid),a.pretty); return 0
   if a.group_cmd=="create": out(s.plan("group_create",{"instance":a.instance,"subject":a.subject,"existing_jid":a.existing_jid,"phones":a.phones}),a.pretty); return 0
   if a.group_cmd=="setup-plan": out(s.plan("group_setup",{"instance":a.instance,"subject":a.subject,"description":a.description,"picture":a.picture,"existing_jid":a.existing_jid,"phones":a.phones,"participant_instances":a.participant_instance,"admin_instances":a.admin_instance,"settings":a.setting}),a.pretty); return 0
   if a.group_cmd=="update":
    if a.update_cmd=="participants": out(s.plan("participants_"+a.action,{"instance":a.instance,"groupJid":a.jid,"phones":a.phones,"action":a.action}),a.pretty); return 0
    out(s.plan("group_"+a.update_cmd,{"instance":a.instance,"groupJid":a.jid,a.field:a.value}),a.pretty); return 0
   if a.group_cmd=="invite":
    if a.invite_cmd=="get": s._instance(a.instance); s._group_jid(a.jid); out({"status":"read-only","jid":a.jid} if c.mode=="demo" else s.client.request("invite_get",a.instance,query={"groupJid":a.jid}),a.pretty); return 0
    if a.invite_cmd=="resolve": out(s.invite_info(a.instance,a.code),a.pretty); return 0
    if a.invite_cmd=="send": out(s.plan("invite_send",{"instance":a.instance,"groupJid":a.jid,"description":a.description,"phones":a.phones}),a.pretty); return 0
    out(s.plan("invite_revoke",{"instance":a.instance,"groupJid":a.jid}),a.pretty); return 0
   out(s.plan("group_leave",{"instance":a.instance,"groupJid":a.jid}),a.pretty); return 0
  if a.cmd=="message":
   payload={"instance":a.instance,"number":s.recipient_from_chat(a.instance,a.chat_id) if a.message_cmd=="plan-text" and a.chat_id else a.number}
   if a.message_cmd=="plan-text": payload["content"]=read_message(a.content,a.content_file)
   else: payload.update({"mediatype":a.mediatype,"media":a.media,"caption":a.caption,"fileName":a.file_name,"mimetype":a.mimetype})
   out(s.plan("message_"+a.message_cmd.removeprefix("plan-"),payload),a.pretty); return 0
  if a.cmd=="number": out(s.whatsapp_numbers(a.instance,a.numbers),a.pretty); return 0
  if a.cmd=="webhook":
   if a.webhook_cmd=="get": out(s.webhook_info(a.instance),a.pretty); return 0
   webhook={"enabled":a.enabled,"url":a.url,"headers":{},"byEvents":a.by_events,"base64":a.base64,"events":a.events}
   out(s.plan("webhook_set",{"instance":a.instance,"webhook":webhook}),a.pretty); return 0
  if a.cmd=="blacklist":
   if a.blacklist_cmd=="list": out(s.store.state("blacklist",[]),a.pretty); return 0
   s.store.blacklist(a.phone,a.blacklist_cmd=="remove"); values=s.store.state("blacklist",[]); values=([x for x in values if x!=a.phone] if a.blacklist_cmd=="remove" else sorted(set(values+[a.phone]))); s.store.save_state("blacklist",values); out({"status":a.blacklist_cmd+"ed"},a.pretty); return 0
  if a.cmd=="onboarding":
   if a.onboard_cmd=="apply": out(s.apply(a.plan_id,a.confirm),a.pretty); return 0
   out(s.plan("onboarding",{"creator_instance":a.creator_instance,"participant_instances":a.participant_instance,"admin_instances":a.admin_instance,"welcome_instance":a.welcome_instance,"client_phone":a.client_phone,"group_name":a.group_name,"description":a.description,"picture":a.picture,"existing_jid":a.existing_jid,"welcome":a.welcome,"phones":[a.client_phone]}),a.pretty); return 0
  if a.demo_cmd=="reset": s.store.reset(); out({"status":"reset"},a.pretty); return 0
  out({"instances":s.instances(),"groups":s.store.state("groups",[])},a.pretty); return 0
 except (PlanError, ValueError) as e: print(f"error: {e}",file=sys.stderr); return 2
 # A mensagem de EvolutionError ja passa por safe_error; esconde-la atras de
 # "operation failed safely" so tira do operador a diferenca entre timeout,
 # rota errada e instancia desconectada.
 except EvolutionError as e: print(f"error: {safe_error(e)}",file=sys.stderr); return 1
 except Exception as e: print("error: operation failed safely",file=sys.stderr); return 1
 finally: s.store.close()

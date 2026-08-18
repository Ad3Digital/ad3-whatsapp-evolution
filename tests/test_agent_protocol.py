import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

src = str(Path(__file__).resolve().parents[1] / "src")
if src not in sys.path:
 sys.path.insert(0, src)
from ad3_evolution.agent_protocol import MAX_INPUT_BYTES, capabilities, parse_input, run_batch
from ad3_evolution.cli import main
from ad3_evolution.service import Service
from ad3_evolution.store import Store


class AgentProtocolTests(unittest.TestCase):
 def setUp(self):
  self.temp = tempfile.TemporaryDirectory()
  self.store = Store(Path(self.temp.name) / "state.sqlite3")
  self.service = Service(self.store, "demo")

 def tearDown(self):
  self.store.close()
  self.temp.cleanup()

 def batch(self, value):
  return run_batch(self.service, value if isinstance(value, bytes) else json.dumps(value).encode())

 def test_single_object_array_and_jsonl(self):
  for value in (
   {"id": "one", "op": "doctor", "args": {}},
   [{"id": "one", "op": "doctor", "args": {}}],
   b'{"id":"one","op":"doctor","args":{}}\n{"id":"two","op":"instance.list","args":{}}\n',
  ):
   responses, failed = self.batch(value)
   self.assertFalse(failed)
   self.assertTrue(all(item["ok"] for item in responses))
  self.assertEqual(parse_input(b'{"id":"one","op":"doctor","args":{}}')[0]["id"], "one")

 def test_duplicate_id_unknown_arg_and_mutation_are_refused(self):
  responses, failed = self.batch([
   {"id": "same", "op": "doctor", "args": {}},
   {"id": "same", "op": "doctor", "args": {}},
   {"id": "other", "op": "chat.list", "args": {"instance": "creator", "extra": True}},
   {"id": "mutate", "op": "apply", "args": {}},
  ])
  self.assertTrue(failed)
  self.assertEqual([item["ok"] for item in responses], [True, False, False, False])
  self.assertEqual(responses[1]["error"]["code"], "duplicate_id")
  self.assertEqual(responses[2]["error"]["code"], "unknown_argument")
  self.assertEqual(responses[3]["error"]["code"], "unsupported_operation")

 def test_limit_input_errors_and_continues_after_failure(self):
  responses, failed = self.batch([{"id": str(i), "op": "doctor", "args": {}} for i in range(51)])
  self.assertTrue(failed)
  self.assertEqual(responses[0]["error"]["code"], "batch_too_large")
  responses, failed = self.batch(b"\xff")
  self.assertTrue(failed)
  self.assertEqual(responses[0]["error"]["code"], "invalid_utf8")
  responses, failed = self.batch(b"x" * (MAX_INPUT_BYTES + 1))
  self.assertTrue(failed)
  self.assertEqual(responses[0]["error"]["code"], "input_too_large")
  responses, failed = self.batch([
   {"id": "bad", "op": "group.info", "args": {"instance": "creator", "jid": "bad"}},
   {"id": "good", "op": "doctor", "args": {}},
  ])
  self.assertTrue(failed)
  self.assertFalse(responses[0]["ok"])
  self.assertTrue(responses[1]["ok"])

 def test_summary_view_is_small_and_does_not_expose_phone(self):
  self.store.save_state("messages", [{"key": {"remoteJid": "5511888888888@g.us"}, "body": "secret"}])
  responses, failed = self.batch([
   {"id": "instances", "op": "instance.list", "args": {"view": "summary"}},
   {"id": "messages", "op": "chat.messages", "args": {"instance": "creator", "jid": "5511888888888@g.us", "view": "summary"}},
  ])
  self.assertFalse(failed)
  self.assertEqual(responses[0]["data"]["count"], 3)
  self.assertEqual(responses[0]["data"]["states"], {"open": 3})
  self.assertEqual(responses[0]["data"]["connected"], 3)
  self.assertEqual(responses[1]["data"], {"count": 1})
  self.assertNotIn("5511888888888", json.dumps(responses, ensure_ascii=False))

 def test_instance_summary_prioritizes_real_connection_status(self):
  self.store.save_state("instances", [
   {"name":"one","connectionStatus":"open","state":"closed"},
   {"name":"two","connectionStatus":"closed"},
   {"name":"three","state":"open"},
   {"name":"four"},
  ])
  responses, failed=self.batch({"id":"instances","op":"instance.list","args":{"view":"summary"}})
  self.assertFalse(failed)
  self.assertEqual(responses[0]["data"], {"count":4,"states":{"open":2,"closed":1,"unknown":1},"connected":2,"disconnected":2})

 def test_new_read_operations_are_allowlisted_and_sanitized(self):
  plan=self.service.plan("group_create", {"instance":"creator","subject":"G","phones":["5511888888888"]})
  jid=self.service.apply(plan["id"], plan["id"])["group_jid"]
  code=self.service._group(jid)[1]["invite"]
  with self.assertRaises(Exception): self.service.plan("webhook_set", {"instance":"creator","webhook":{"enabled":True,"url":"https://hooks.example.test/path?private=x","headers":{},"byEvents":True,"base64":False,"events":["MESSAGES_UPSERT"]}})
  good=self.service.plan("webhook_set", {"instance":"creator","webhook":{"enabled":True,"url":"https://hooks.example.test/path","headers":{},"byEvents":True,"base64":False,"events":["MESSAGES_UPSERT"]}})
  self.service.apply(good["id"], good["id"])
  responses, failed=self.batch([
   {"id":"numbers","op":"number.check","args":{"instance":"creator","numbers":["5511888888888"]}},
   {"id":"participants","op":"group.participants","args":{"instance":"creator","jid":jid,"view":"summary"}},
   {"id":"invite","op":"group.invite.resolve","args":{"instance":"creator","code":code}},
   {"id":"webhook","op":"webhook.get","args":{"instance":"creator"}},
  ])
  self.assertFalse(failed)
  self.assertEqual(responses[1]["data"], {"count":1,"admins":0,"phoneNumber":1,"lid":0})
  self.assertEqual(responses[3]["data"]["origin"], "https://hooks.example.test")
  self.assertNotIn("https://hooks.example.test/path", json.dumps(responses))
  self.assertIn("number.check", [item["op"] for item in capabilities()["operations"]])

 def test_capabilities_and_cli_batch_exit_two_on_partial_failure(self):
  self.assertFalse(capabilities()["mutating"])
  self.assertIn("chat.list", [item["op"] for item in capabilities()["operations"]])
  self.assertEqual(capabilities()["legacy_cli"]["scheduling"], "external_wrapper_only")
  request = Path(self.temp.name) / "request.jsonl"
  request.write_text('{"id":"bad","op":"apply","args":{}}\n{"id":"good","op":"doctor","args":{}}\n', encoding="utf-8")
  output = io.StringIO()
  with redirect_stdout(output):
   self.assertEqual(main(["--mode", "demo", "--state-dir", self.temp.name, "agent", "batch", "--input-file", str(request), "--pretty"]), 2)
  lines = [json.loads(line) for line in output.getvalue().splitlines()]
  self.assertEqual(len(lines), 2)
  self.assertFalse(lines[0]["ok"])
  self.assertTrue(lines[1]["ok"])
  output = io.StringIO()
  with redirect_stdout(output):
   self.assertEqual(main(["--mode", "demo", "--state-dir", self.temp.name, "doctor", "--pretty"]), 0)
  self.assertIn("\n", output.getvalue())

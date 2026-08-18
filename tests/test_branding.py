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

from ad3_evolution.branding import PIX_CITY, PIX_KEY, PIX_NAME, PIX_TXID, crc16_ccitt, donation_text, pix_payload, qr_matrix, render_qr
from ad3_evolution.cli import main

EXPECTED_PIX_PAYLOAD="00020126580014br.gov.bcb.pix0136527f144d-ad3b-4ae9-85b9-87a51a8bf0355204000053039865802BR5911AD3 DIGITAL6011FARROUPILHA62070503***63042884"


def independent_crc(value):
 crc=0xFFFF
 for byte in value.encode("ascii"):
  crc ^= byte << 8
  for _ in range(8):
   crc=((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
 return f"{crc:04X}"


def parse_tlv(value):
 fields=[]; index=0
 while index < len(value):
  tag=value[index:index+2]; size=int(value[index+2:index+4]); start=index+4; end=start+size
  fields.append((tag,value[start:end])); index=end
 return fields


class BrandingTests(unittest.TestCase):
 def capture(self, argv):
  output=io.StringIO()
  with redirect_stdout(output):
   result=main(argv)
  return result,output.getvalue()

 def test_pix_payload_has_contract_fields_and_independent_crc(self):
  payload=pix_payload()
  self.assertEqual(payload,EXPECTED_PIX_PAYLOAD)
  self.assertIn(PIX_KEY,payload); self.assertIn(PIX_NAME,payload); self.assertIn(PIX_CITY,payload); self.assertIn(PIX_TXID,payload)
  self.assertEqual(payload[-4:],independent_crc(payload[:-4])); self.assertEqual(payload[-8:-4],"6304")
  self.assertEqual(crc16_ccitt(payload[:-4]),payload[-4:])
  fields=parse_tlv(payload[:-8]); self.assertNotIn("54",[tag for tag,_ in fields]); self.assertIn(("59",PIX_NAME),fields); self.assertIn(("60",PIX_CITY),fields)

 def test_matrix_and_no_color_render_are_stable_with_quiet_zone(self):
  matrix=qr_matrix()
  self.assertTrue(matrix and all(not cell for cell in matrix[0]) and all(not cell for cell in matrix[-1]))
  rendered=render_qr(matrix,color=False)
  self.assertEqual(rendered,render_qr(matrix,color=False)); self.assertNotIn("\x1b",rendered)

 def test_human_commands_do_not_load_config_or_create_state(self):
  with patch("ad3_evolution.cli.Config.load",side_effect=AssertionError("Config must stay unloaded")):
   for argv,needle in (([],"EVOLUTION AD3 DIGITAL"),(["--help"],"donate"),(["donate","--help"],"--no-color"),(["donate","--no-color"],"PIX COPIA E COLA")):
    code,text=self.capture(argv); self.assertEqual(code,0); self.assertIn(needle,text)
  self.assertIn(PIX_KEY,donation_text(color=False))
  code,text=self.capture(["not-a-command","--help"]); self.assertEqual(code,2); self.assertIn("EVOLUTION AD3 DIGITAL",text)

 def test_json_and_jsonl_commands_never_include_brand_or_pix(self):
  with tempfile.TemporaryDirectory() as folder:
   code,text=self.capture(["--mode","demo","--state-dir",folder,"capabilities"])
   self.assertEqual(code,0); self.assertNotIn("EVOLUTION AD3 DIGITAL",text); self.assertNotIn("PIX",text); json.loads(text)
   request=Path(folder)/"batch.jsonl"; request.write_text('{"id":"health","op":"doctor","args":{}}\n',encoding="utf-8")
   code,text=self.capture(["--mode","demo","--state-dir",folder,"agent","batch","--input-file",str(request)])
   self.assertEqual(code,0); self.assertNotIn("EVOLUTION AD3 DIGITAL",text); self.assertNotIn("PIX",text); self.assertEqual(len(text.splitlines()),1); json.loads(text)

 def test_legacy_doctor_stays_json(self):
  with tempfile.TemporaryDirectory() as folder:
   code,text=self.capture(["--mode","demo","--state-dir",folder,"doctor"])
  self.assertEqual(code,0); self.assertTrue(json.loads(text)["ok"]); self.assertNotIn("EVOLUTION AD3 DIGITAL",text)

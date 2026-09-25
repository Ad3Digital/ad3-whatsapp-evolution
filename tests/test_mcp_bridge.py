"""Contract checks without installing the optional MCP dependency."""

import importlib
import sys
import types
import unittest
from unittest.mock import patch


class FakeMCP:
    def __init__(self, *args, **kwargs):
        pass

    def tool(self):
        return lambda function: function


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mcp = types.ModuleType("mcp")
        server = types.ModuleType("mcp.server")
        fastmcp = types.ModuleType("mcp.server.fastmcp")
        fastmcp.FastMCP = FakeMCP
        with patch.dict(sys.modules, {"mcp": mcp, "mcp.server": server,
                                      "mcp.server.fastmcp": fastmcp}):
            cls.bridge = importlib.import_module("mcp_bridge.server")

    def test_planning_uses_content_file_and_does_not_apply(self):
        def fake_run(*args):
            self.assertEqual(args[:4], ("message", "plan-text", "--instance", "aula"))
            self.assertNotIn("Olá", args)
            self.assertEqual(args[-2], "--content-file")
            with open(args[-1], encoding="utf-8") as file:
                self.assertEqual(file.read(), "Olá")
            return {"id": "12345678"}

        with patch.object(self.bridge, "run_cli", side_effect=fake_run) as run:
            self.bridge.plan_text("aula", "5554999999999", "Olá")
            self.assertEqual(run.call_count, 1)

    def test_apply_requires_matching_confirmation(self):
        with patch.object(self.bridge, "run_cli") as run:
            with self.assertRaises(ValueError):
                self.bridge.send_approved_plan("12345678", "outro")
            run.assert_not_called()
            self.bridge.send_approved_plan("12345678", "12345678")
            run.assert_called_once_with("apply", "--plan-id", "12345678",
                                        "--confirm", "12345678")


if __name__ == "__main__":
    unittest.main()

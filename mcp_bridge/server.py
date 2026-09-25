"""Private MCP adapter for the existing ad3-evolution CLI.

Run behind Secure MCP Tunnel in developer mode. Do not expose this unauthenticated
HTTP endpoint directly to the public internet.
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("AD3 Evolution", host="127.0.0.1", port=int(os.getenv("AD3_MCP_PORT", "8765")))
CLI = os.getenv("AD3_EVOLUTION_CLI", "ad3-evolution")
PLAN_ID = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


def run_cli(*args: str, timeout: int = 110) -> object:
    command = [CLI, *args]
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode:
        # The CLI sanitizes its errors. Do not expose process environment or args.
        raise ValueError((result.stderr or "Falha na CLI Evolution").strip()[:500])
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("A CLI não retornou JSON válido") from exc


@mcp.tool()
def list_instances() -> object:
    """List configured WhatsApp instances (read only)."""
    return run_cli("instance", "list")


@mcp.tool()
def list_chats(instance: str, limit: int = 20) -> object:
    """List recent chats for one instance (read only)."""
    if not 1 <= limit <= 50:
        raise ValueError("limit deve estar entre 1 e 50")
    return run_cli("chat", "list", "--instance", instance, "--limit", str(limit))


@mcp.tool()
def read_messages(instance: str, jid: str, limit: int = 20) -> object:
    """Read messages from an explicitly identified chat (read only)."""
    if not 1 <= limit <= 50:
        raise ValueError("limit deve estar entre 1 e 50")
    return run_cli("chat", "messages", "--instance", instance, "--jid", jid, "--limit", str(limit))


@mcp.tool()
def plan_text(instance: str, number: str, content: str) -> object:
    """Prepare a text message. Does not send it. Show recipient and exact text to the user before confirmation."""
    if not content.strip() or len(content) > 10000:
        raise ValueError("Mensagem vazia ou longa demais")
    # Avoid exposing the content in process arguments and logs.
    with tempfile.TemporaryDirectory(prefix="ad3-mcp-") as directory:
        path = Path(directory) / "message.txt"
        path.write_text(content, encoding="utf-8")
        return run_cli("message", "plan-text", "--instance", instance,
                       "--number", number, "--content-file", str(path))


@mcp.tool()
def send_approved_plan(plan_id: str, confirmation: str) -> object:
    """Send a previously reviewed plan only after the user explicitly confirms this exact plan ID."""
    if not PLAN_ID.fullmatch(plan_id) or confirmation != plan_id:
        raise ValueError("É necessária confirmação explícita do ID do plano")
    # Never retry automatically: a failed response may still follow a successful send.
    return run_cli("apply", "--plan-id", plan_id, "--confirm", confirmation)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")

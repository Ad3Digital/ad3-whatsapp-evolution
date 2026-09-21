"""Small, read-only JSON/JSONL protocol for external agent loops.

The protocol deliberately maps each operation to a concrete Service call.  It is
not a generic CLI or RPC bridge: no method names, URLs, imports, or mutations are
accepted from the input.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable

from .client import EvolutionError
from .security import redact, safe_error, validate_chat_jid
from .store import PlanError


SCHEMA = "ad3-evolution.agent/v1"
MAX_BATCH_REQUESTS = 50
MAX_INPUT_BYTES = 1024 * 1024


class ProtocolError(ValueError):
    """A predictable, redaction-safe protocol error."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


_OPERATIONS = {
    "doctor": {},
    "instance.list": {"view": {"type": "view", "required": False, "default": "full"}},
    "instance.status": {"instance": {"type": "string", "required": True}},
    "chat.list": {
        "instance": {"type": "string", "required": True},
        "limit": {"type": "integer", "required": False, "default": 20, "minimum": 1, "maximum": 100},
        "view": {"type": "view", "required": False, "default": "full"},
    },
    "chat.messages": {
        "instance": {"type": "string", "required": True},
        "jid": {"type": "chat_jid", "required": True},
        "limit": {"type": "integer", "required": False, "default": 20, "minimum": 1, "maximum": 100},
        "view": {"type": "view", "required": False, "default": "full"},
    },
    "group.list": {"instance": {"type": "string", "required": True}, "view": {"type": "view", "required": False, "default": "full"}},
    "group.info": {
        "instance": {"type": "string", "required": True},
        "jid": {"type": "group_jid", "required": True},
    },
    "group.participants": {
        "instance": {"type": "string", "required": True},
        "jid": {"type": "group_jid", "required": True},
        "view": {"type": "view", "required": False, "default": "full"},
    },
    "group.invite.resolve": {
        "instance": {"type": "string", "required": True},
        "code": {"type": "invite_code", "required": True},
    },
    "number.check": {"instance": {"type": "string", "required": True}, "numbers": {"type": "phone_list", "required": True}},
    "webhook.get": {"instance": {"type": "string", "required": True}},
    "plan.status": {"id": {"type": "string", "required": True}},
}


def capabilities() -> dict[str, Any]:
    """Return the stable, intentionally compact capability description."""
    return {
        "schema": SCHEMA,
        "profile": "evolution-2.3.7",
        "mutating": False,
        "operations": [
            {"op": name, "args": _OPERATIONS[name]}
            for name in sorted(_OPERATIONS)
        ],
        "legacy_cli": {
            "mutating": True,
            "commands": [
                "instance create-plan|connect-plan",
                "group create|setup-plan|update|invite|leave",
                "message plan-text|plan-media",
                "number check|webhook get|set-plan",
                "onboarding plan|apply",
                "apply|blacklist",
            ],
            "scheduling": "external_wrapper_only",
        },
    }


def parse_input(raw: bytes) -> list[Any]:
    """Parse one object, an array, or newline-delimited JSON objects."""
    if len(raw) > MAX_INPUT_BYTES:
        raise ProtocolError("input_too_large", "input exceeds 1 MiB")
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolError("invalid_utf8", "input must be UTF-8") from exc
    if not text.strip():
        raise ProtocolError("invalid_input", "input is empty")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        values = []
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                values.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ProtocolError("invalid_json", "input must be JSON, JSON array, or JSONL") from exc
        if not values:
            raise ProtocolError("invalid_input", "input is empty")
        return values
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    raise ProtocolError("invalid_input", "input must be an object, array, or JSONL objects")


def _request(value: Any, seen: set[str]) -> tuple[str, str, dict[str, Any]]:
    if not isinstance(value, dict):
        raise ProtocolError("invalid_request", "request must be an object")
    unknown = set(value) - {"id", "op", "args"}
    if unknown:
        raise ProtocolError("unknown_request_field", "request contains an unknown field")
    request_id = value.get("id")
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 200:
        raise ProtocolError("invalid_id", "id must be a non-empty string up to 200 characters")
    if request_id in seen:
        raise ProtocolError("duplicate_id", "id must be unique within a batch")
    seen.add(request_id)
    op = value.get("op")
    if not isinstance(op, str) or op not in _OPERATIONS:
        raise ProtocolError("unsupported_operation", "operation is not allowed")
    args = value.get("args")
    if not isinstance(args, dict):
        raise ProtocolError("invalid_args", "args must be an object")
    spec = _OPERATIONS[op]
    if set(args) - set(spec):
        raise ProtocolError("unknown_argument", "args contains an unknown argument")
    normalized: dict[str, Any] = {}
    for name, rule in spec.items():
        value = args.get(name)
        if value is None:
            if rule.get("required"):
                raise ProtocolError("missing_argument", f"args.{name} is required")
            if "default" in rule:
                normalized[name] = rule["default"]
            continue
        if rule["type"] in {"string", "group_jid", "chat_jid", "invite_code"}:
            if not isinstance(value, str) or not value.strip():
                raise ProtocolError("invalid_argument", f"args.{name} must be a non-empty string")
            if rule["type"] == "chat_jid":
                try: validate_chat_jid(value)
                except ValueError as exc: raise ProtocolError("invalid_argument", f"args.{name} is not a readable chat JID") from exc
            if rule["type"] == "invite_code" and not re.fullmatch(r"[A-Za-z0-9]{8,128}", value):
                raise ProtocolError("invalid_argument", f"args.{name} is not an invite code")
        elif rule["type"] == "integer":
            if isinstance(value, bool) or not isinstance(value, int) or not rule["minimum"] <= value <= rule["maximum"]:
                raise ProtocolError("invalid_argument", f"args.{name} must be an integer between 1 and 100")
        elif rule["type"] == "view":
            if value not in {"full", "summary"}:
                raise ProtocolError("invalid_argument", f"args.{name} must be full or summary")
        elif rule["type"] == "phone_list":
            if not isinstance(value, list) or not 1 <= len(value) <= 100 or any(not isinstance(item, str) or not item.strip() for item in value):
                raise ProtocolError("invalid_argument", f"args.{name} must contain 1 to 100 phone numbers")
        normalized[name] = value
    return request_id, op, normalized


def _execute(service: Any, op: str, args: dict[str, Any]) -> Any:
    if op == "doctor":
        return service.doctor()
    if op == "instance.list":
        items = service.instances()
        if args["view"] == "summary":
            states: dict[str, int] = {}
            connected = 0
            for item in items:
                value = item.get("connectionStatus") if isinstance(item, dict) else None
                if value is None or (isinstance(value, str) and not value.strip()):
                    value = item.get("state") if isinstance(item, dict) else None
                state = str(value).strip() if value is not None and str(value).strip() else "unknown"
                states[state] = states.get(state, 0) + 1
                if state.lower() in {"open", "connected"}:
                    connected += 1
            return {"count": len(items), "states": states, "connected": connected, "disconnected": len(items) - connected}
        return items
    if op == "instance.status":
        return {"instance": args["instance"], "connected": service._connected(args["instance"])}
    if op == "chat.list":
        items = service.chat_list(args["instance"], args["limit"])
        return {"count": len(items)} if args["view"] == "summary" else items
    if op == "chat.messages":
        items = service.message_history(args["instance"], args["jid"], args["limit"])
        return {"count": len(items)} if args["view"] == "summary" else items
    if op == "group.list":
        items = service.group_list(args["instance"])
        return {"count": len(items)} if args["view"] == "summary" else items
    if op == "group.info":
        return service.group_info(args["instance"], args["jid"])
    if op == "group.participants":
        items = service.group_participants(args["instance"], args["jid"])
        if args["view"] == "summary":
            admins=sum(1 for item in items if isinstance(item,dict) and (item.get("admin") is True or str(item.get("role","")).lower() in {"admin","superadmin"}))
            phones=sum(1 for item in items if isinstance(item,dict) and isinstance(item.get("phoneNumber"),str))
            lids=sum(1 for item in items if isinstance(item,dict) and any(isinstance(item.get(key),str) and item[key].lower().endswith("@lid") for key in ("id","jid")))
            return {"count":len(items),"admins":admins,"phoneNumber":phones,"lid":lids}
        return items
    if op == "group.invite.resolve":
        return service.invite_info(args["instance"], args["code"])
    if op == "number.check":
        return service.whatsapp_numbers(args["instance"], args["numbers"])
    if op == "webhook.get":
        return service.webhook_info(args["instance"])
    if op == "plan.status":
        return service.store.plan_status(args["id"])
    raise AssertionError("operation allowlist is incomplete")


def response(request_id: str | None, ok: bool, *, data: Any = None, error: ProtocolError | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"schema": SCHEMA, "id": request_id, "ok": ok}
    if ok:
        value["data"] = data
    else:
        assert error is not None
        value["error"] = {"code": error.code, "message": error.message}
    return redact(value)


def run_batch(service: Any, raw: bytes) -> tuple[list[dict[str, Any]], bool]:
    """Run every independently valid request and report whether any failed."""
    try:
        items = parse_input(raw)
    except ProtocolError as exc:
        return [response(None, False, error=exc)], True
    if len(items) > MAX_BATCH_REQUESTS:
        return [response(None, False, error=ProtocolError("batch_too_large", "batch contains more than 50 requests"))], True
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    failed = False
    for item in items:
        request_id = item.get("id") if isinstance(item, dict) and isinstance(item.get("id"), str) else None
        try:
            request_id, op, args = _request(item, seen)
            results.append(response(request_id, True, data=_execute(service, op, args)))
        except ProtocolError as exc:
            results.append(response(request_id, False, error=exc))
            failed = True
        except (PlanError, ValueError, EvolutionError) as exc:
            results.append(response(request_id, False, error=ProtocolError("operation_failed", safe_error(exc))))
            failed = True
        except Exception:
            results.append(response(request_id, False, error=ProtocolError("operation_failed", "operation failed safely")))
            failed = True
    return results, failed


def encode_jsonl(items: Iterable[dict[str, Any]]) -> str:
    return "".join(json.dumps(redact(item), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for item in items)

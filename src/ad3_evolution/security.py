from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d .()\-]{7,}\d)(?!\d)")
SECRET = re.compile(r"(?i)(apikey|api_key|authorization|token|password|secret)\s*[:=]\s*([^\s,]+)")
_BASE64_DATA_URL = re.compile(r"^data:[^,]*;base64,[A-Za-z0-9+/=_-]+$", re.I)
_LONG_BASE64 = re.compile(r"^[A-Za-z0-9+/=_-]{256,}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_GROUP_JID = re.compile(r"^[^@\s/\\?#]+@g\.us$", re.I)
_INDIVIDUAL_JID = re.compile(r"^\d{10,15}@s\.whatsapp\.net$", re.I)
_LID_JID = re.compile(r"^[^@\s/\\?#]+@lid$", re.I)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def validate_instance(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or _CONTROL.search(value) or any(x in value for x in "/\\?#"):
        raise ValueError("instance is invalid")
    return value.strip()


def validate_group_jid(value: Any) -> str:
    if not isinstance(value, str) or _CONTROL.search(value) or "@lid" in value.lower() or not _GROUP_JID.fullmatch(value):
        raise ValueError("group JID is invalid")
    return value


def validate_chat_jid(value: Any) -> str:
    """Accept only group, individual, or LID JIDs for read-only chat history."""
    if not isinstance(value, str) or _CONTROL.search(value):
        raise ValueError("chat JID is invalid")
    if _GROUP_JID.fullmatch(value) or _INDIVIDUAL_JID.fullmatch(value) or _LID_JID.fullmatch(value):
        return value
    raise ValueError("chat JID is invalid")


def normalize_phone(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("phone is invalid")
    number = value.strip()
    if "@lid" in number.lower() or "@g.us" in number.lower():
        raise ValueError("phone is invalid")
    if number.lower().endswith("@s.whatsapp.net"):
        if not _INDIVIDUAL_JID.fullmatch(number):
            raise ValueError("phone is invalid")
        number = number.split("@", 1)[0]
    if number.startswith("+"):
        number = number[1:]
    if not number.isdigit() or not 10 <= len(number) <= 15:
        raise ValueError("phone is invalid")
    return number


def validate_individual_jid(value: Any) -> str:
    if not isinstance(value, str) or "@lid" in value.lower() or not _INDIVIDUAL_JID.fullmatch(value):
        raise ValueError("individual JID is invalid")
    return value


def private_key(path: Path) -> bytes:
    """Create a local AES-256 key next to the database, never in SQLite."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(path.parent, 0o700)
    if not path.exists():
        key = AESGCM.generate_key(bit_length=256)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        try:
            fd = os.open(path, flags, 0o600)
            try:
                os.write(fd, key)
            finally:
                os.close(fd)
        except FileExistsError:
            # Another process won creation; wait for its complete 32-byte key.
            key = b""
            for _ in range(50):
                try: key = path.read_bytes()
                except FileNotFoundError: pass
                if len(key) == 32: break
                time.sleep(0.01)
    else:
        key = path.read_bytes()
    if len(key) != 32:
        raise RuntimeError("local state encryption key is invalid")
    if os.name != "nt":
        os.chmod(path, 0o600)
    return key


def encrypt(value: Any, key: bytes, aad: str) -> str:
    nonce = os.urandom(12)
    data = AESGCM(key).encrypt(nonce, canonical(value).encode(), aad.encode())
    return "enc:v1:" + base64.urlsafe_b64encode(nonce + data).decode()


def decrypt(value: str | None, key: bytes, aad: str) -> Any:
    if value is None:
        return None
    if not isinstance(value, str) or not value.startswith("enc:v1:"):
        return json.loads(value)  # Legacy plaintext; Store migrates it on open.
    raw = base64.urlsafe_b64decode(value[len("enc:v1:"):].encode())
    return json.loads(AESGCM(key).decrypt(raw[:12], raw[12:], aad.encode()))


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key_text = str(key)
            secret_key = re.search(r"(?i)(key|token|secret|password|authorization)", key_text)
            binary_key = "base64" in key_text.lower() and isinstance(item, str)
            result[key] = "[REDACTED]" if secret_key or binary_key else redact(item)
        return result
    if isinstance(value, list):
        return [redact(item) for item in value]
    if not isinstance(value, str):
        return value
    value = SECRET.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    if _BASE64_DATA_URL.fullmatch(value) or _LONG_BASE64.fullmatch(value):
        return "[REDACTED]"
    return PHONE.sub(lambda match: "***" + re.sub(r"\D", "", match.group(0))[-4:], value)


def redact_audit(value: Any) -> Any:
    # Audits are deliberately metadata-only; values that can identify a target stay out.
    if not isinstance(value, dict):
        return {"type": type(value).__name__}
    allowed = {"plan_id", "kind", "status", "phase", "code", "type", "hash"}
    return {k: str(v)[:80] for k, v in value.items() if k in allowed and v is not None}


def safe_error(exc: Exception) -> str:
    return str(redact(str(exc)))[:500]

from __future__ import annotations

import inspect
import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from .security import canonical, decrypt, digest, digest_text, encrypt, normalize_phone, private_key, redact_audit


class PlanError(RuntimeError):
    pass


class Store:
    def __init__(self, path: Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(self.path.parent, 0o700)
        self.key = private_key(self.path.with_suffix(self.path.suffix + ".key"))
        # Connections are normally process-local; disabling this guard also lets a
        # caller hand each independent Store to a worker thread safely.
        self.db = sqlite3.connect(self.path, timeout=30, isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        if os.name != "nt":
            os.chmod(self.path, 0o600)
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS plans(id TEXT PRIMARY KEY, kind TEXT, payload TEXT, hash TEXT, status TEXT, created REAL, expires REAL, result TEXT);
          CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, event TEXT, detail TEXT, at REAL);
          CREATE TABLE IF NOT EXISTS blacklist(value TEXT PRIMARY KEY);
          CREATE TABLE IF NOT EXISTS demo(key TEXT PRIMARY KEY, value TEXT);
          CREATE TABLE IF NOT EXISTS idempotency(key TEXT PRIMARY KEY, result TEXT, status TEXT DEFAULT 'applied');
          CREATE TABLE IF NOT EXISTS maintenance(key TEXT PRIMARY KEY, value TEXT);
        """)
        columns = {r[1] for r in self.db.execute("PRAGMA table_info(idempotency)")}
        if "status" not in columns:
            self.db.execute("ALTER TABLE idempotency ADD COLUMN status TEXT DEFAULT 'applied'")
        self._migrate_plaintext()

    def _enc(self, value: Any, table: str, row: str, column: str) -> str:
        return encrypt(value, self.key, f"ad3-evolution:{table}:{row}:{column}")

    def _dec(self, value: str | None, table: str, row: str, column: str) -> Any:
        return decrypt(value, self.key, f"ad3-evolution:{table}:{row}:{column}")

    def _blacklist_phone(self, value: str) -> str:
        try:
            return normalize_phone(value)
        except ValueError as exc:
            raise PlanError("blacklist phone is invalid") from exc

    def _legacy_blacklist_digest(self, value: str) -> str:
        if re.fullmatch(r"[0-9a-fA-F]{64}", value):
            return value
        try:
            value = normalize_phone(value)
        except ValueError:
            pass
        return digest_text(value)

    def _vacuum(self) -> None:
        self.db.execute("VACUUM")
        checkpoint = self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if checkpoint is not None and checkpoint[0] != 0:
            raise sqlite3.OperationalError("WAL checkpoint remained busy after plaintext migration")

    def _migrate_plaintext(self) -> None:
        """Encrypt old rows and persist a compaction obligation before commit."""
        pending_vacuum = self.db.execute("SELECT 1 FROM maintenance WHERE key='vacuum_required'").fetchone() is not None
        changed = False
        self.db.execute("BEGIN IMMEDIATE")
        try:
            for row in self.db.execute("SELECT id,payload,result FROM plans").fetchall():
                for column in ("payload", "result"):
                    value = row[column]
                    if value is not None and not value.startswith("enc:v1:"):
                        self.db.execute(f"UPDATE plans SET {column}=? WHERE id=?", (self._enc(json.loads(value), "plans", row["id"], column), row["id"]))
                        changed = True
            for row in self.db.execute("SELECT key,value FROM demo").fetchall():
                if not row["value"].startswith("enc:v1:"):
                    self.db.execute("UPDATE demo SET value=? WHERE key=?", (self._enc(json.loads(row["value"]), "demo", row["key"], "value"), row["key"]))
                    changed = True
            for row in self.db.execute("SELECT key,result FROM idempotency").fetchall():
                if row["result"] is not None and not row["result"].startswith("enc:v1:"):
                    self.db.execute("UPDATE idempotency SET result=? WHERE key=?", (self._enc(json.loads(row["result"]), "idempotency", row["key"], "result"), row["key"]))
                    changed = True
            for row in self.db.execute("SELECT value FROM blacklist").fetchall():
                value = str(row["value"]); hashed = self._legacy_blacklist_digest(value)
                if hashed != value:
                    self.db.execute("INSERT OR IGNORE INTO blacklist(value) VALUES(?)", (hashed,))
                    self.db.execute("DELETE FROM blacklist WHERE value=?", (value,))
                    changed = True
            audit = self.db.execute("UPDATE audit SET detail=? WHERE detail NOT LIKE 'meta:v1:%'", ("meta:v1:" + canonical({"migrated": True}),))
            changed = changed or audit.rowcount > 0
            if changed or pending_vacuum:
                self.db.execute("INSERT OR REPLACE INTO maintenance(key,value) VALUES('vacuum_required','1')")
            self.db.execute("COMMIT")
            if changed or pending_vacuum:
                self._vacuum()
                self.db.execute("DELETE FROM maintenance WHERE key='vacuum_required'")
        except Exception:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            self.db.close()
            raise

    def audit(self, event: str, detail: Any) -> None:
        self.db.execute("INSERT INTO audit(event,detail,at) VALUES(?,?,?)", (event, "meta:v1:" + canonical(redact_audit(detail)), time.time()))

    def plan(self, kind: str, payload: dict, ttl: int = 900) -> dict:
        now = time.time()
        item = {"id": uuid.uuid4().hex, "kind": kind, "payload": payload, "hash": digest(payload), "status": "planned", "created": now, "expires": now + ttl}
        self.db.execute("INSERT INTO plans VALUES(?,?,?,?,?,?,?,NULL)", (item["id"], item["kind"], self._enc(payload, "plans", item["id"], "payload"), item["hash"], item["status"], item["created"], item["expires"]))
        self.audit("plan", {"plan_id": item["id"], "kind": kind, "status": "planned", "hash": item["hash"]})
        return {k: item[k] for k in ("id", "kind", "hash", "expires", "status")}

    def _receipt(self, plan_id: str, receipt: dict) -> None:
        safe = {k: receipt[k] for k in ("group_jid", "phase") if k in receipt}
        if not safe:
            return
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT result FROM plans WHERE id=? AND status='executing'", (plan_id,)).fetchone()
            current = self._dec(row["result"], "plans", plan_id, "result") if row and row["result"] else {}
            current = current if isinstance(current, dict) else {}
            current["receipt"] = safe
            changed = self.db.execute("UPDATE plans SET result=? WHERE id=? AND status='executing'", (self._enc(current, "plans", plan_id, "result"), plan_id)).rowcount
            if changed != 1:
                raise PlanError("plan receipt transition lost")
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def apply(self, plan_id: str, confirm: str, executor: Callable[..., dict]) -> dict:
        if confirm != plan_id:
            raise PlanError("confirmation must equal plan id")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT * FROM plans WHERE id=?", (plan_id,)).fetchone()
            if not row:
                raise PlanError("plan not found")
            if row["status"] != "planned":
                raise PlanError("plan already used, executing, or uncertain; do not replay automatically")
            if row["expires"] < time.time():
                if self.db.execute("UPDATE plans SET status='expired' WHERE id=? AND status='planned'", (plan_id,)).rowcount != 1:
                    raise PlanError("plan transition lost")
                self.db.execute("COMMIT")
                raise PlanError("plan expired")
            payload = self._dec(row["payload"], "plans", plan_id, "payload")
            if not isinstance(payload, dict) or digest(payload) != row["hash"]:
                self.db.execute("UPDATE plans SET status='uncertain' WHERE id=? AND status='planned'", (plan_id,))
                self.db.execute("COMMIT")
                raise PlanError("plan payload integrity check failed")
            if self.db.execute("UPDATE plans SET status='executing' WHERE id=? AND status='planned'", (plan_id,)).rowcount != 1:
                raise PlanError("plan claim lost")
            idem_raw = str(payload.get("idempotency_key", row["kind"] + ":" + row["hash"]))
            idem_key = digest_text(idem_raw)
            existing = self.db.execute("SELECT * FROM idempotency WHERE key=?", (idem_key,)).fetchone()
            if existing is None:
                self.db.execute("INSERT INTO idempotency(key,result,status) VALUES(?,?,?)", (idem_key, None, "executing"))
            elif existing["status"] == "applied" and existing["result"]:
                result = self._dec(existing["result"], "idempotency", idem_key, "result")
                if self.db.execute("UPDATE plans SET status='applied',result=? WHERE id=? AND status='executing'", (self._enc(result, "plans", plan_id, "result"), plan_id)).rowcount != 1:
                    raise PlanError("plan result transition lost")
                self.db.execute("COMMIT")
                return result
            else:
                result = {"status": "uncertain", "error": {"code": "idempotency_reserved", "type": "reservation"}}
                self.db.execute("UPDATE plans SET status='uncertain',result=? WHERE id=? AND status='executing'", (self._enc(result, "plans", plan_id, "result"), plan_id))
                self.db.execute("COMMIT")
                raise PlanError("matching mutation is already reserved; reconcile before retry")
            self.db.execute("COMMIT")
        except Exception:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise
        try:
            checkpoint = lambda receipt: self._receipt(plan_id, receipt)
            result = executor(row["kind"], payload, checkpoint) if len(inspect.signature(executor).parameters) >= 3 else executor(row["kind"], payload)
            self.db.execute("BEGIN IMMEDIATE")
            if self.db.execute("UPDATE idempotency SET result=?,status='applied' WHERE key=? AND status='executing'", (self._enc(result, "idempotency", idem_key, "result"), idem_key)).rowcount != 1:
                raise PlanError("idempotency result transition lost")
            if self.db.execute("UPDATE plans SET status='applied',result=? WHERE id=? AND status='executing'", (self._enc(result, "plans", plan_id, "result"), plan_id)).rowcount != 1:
                raise PlanError("plan result transition lost")
            self.audit("apply", {"plan_id": plan_id, "kind": row["kind"], "status": "applied"})
            self.db.execute("COMMIT")
            return result
        except Exception as exc:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            self.db.execute("BEGIN IMMEDIATE")
            try:
                previous = self.db.execute("SELECT result FROM plans WHERE id=?", (plan_id,)).fetchone()
                detail = self._dec(previous["result"], "plans", plan_id, "result") if previous and previous["result"] else {}
                detail = detail if isinstance(detail, dict) else {}
                detail.update({"status": "uncertain", "error": {"code": "execution_uncertain", "type": type(exc).__name__}})
                self.db.execute("UPDATE idempotency SET status='uncertain' WHERE key=? AND status='executing'", (idem_key,))
                self.db.execute("UPDATE plans SET status='uncertain',result=? WHERE id=? AND status='executing'", (self._enc(detail, "plans", plan_id, "result"), plan_id))
                self.audit("uncertain", {"plan_id": plan_id, "kind": row["kind"], "status": "uncertain", "code": "execution_uncertain", "type": type(exc).__name__})
                self.db.execute("COMMIT")
            except Exception:
                self.db.execute("ROLLBACK")
            raise

    def plan_status(self, plan_id: str) -> dict:
        row = self.db.execute("SELECT id,kind,status,result FROM plans WHERE id=?", (plan_id,)).fetchone()
        if not row:
            raise PlanError("plan not found")
        result = self._dec(row["result"], "plans", plan_id, "result") if row["result"] else {}
        response = {"id": row["id"], "kind": row["kind"], "status": row["status"]}
        if row["status"] == "uncertain" and isinstance(result, dict):
            receipt = result.get("receipt", {})
            response["receipt"] = {k: receipt[k] for k in ("group_jid", "phase") if k in receipt}
        return response

    def blacklist(self, value: str, remove: bool = False) -> None:
        value = digest_text(self._blacklist_phone(value))
        if remove:
            self.db.execute("DELETE FROM blacklist WHERE value=?", (value,))
        else:
            self.db.execute("INSERT OR IGNORE INTO blacklist VALUES(?)", (value,))

    def blacklisted(self, value: str) -> bool:
        return self.db.execute("SELECT 1 FROM blacklist WHERE value=? COLLATE NOCASE", (digest_text(self._blacklist_phone(value)),)).fetchone() is not None

    def state(self, key: str, default: Any) -> Any:
        row = self.db.execute("SELECT value FROM demo WHERE key=?", (key,)).fetchone()
        return self._dec(row["value"], "demo", key, "value") if row else default

    def save_state(self, key: str, value: Any) -> None:
        self.db.execute("INSERT OR REPLACE INTO demo VALUES(?,?)", (key, self._enc(value, "demo", key, "value")))

    def reset(self) -> None:
        self.db.executescript("DELETE FROM plans; DELETE FROM audit; DELETE FROM blacklist; DELETE FROM demo; DELETE FROM idempotency;")

    def close(self) -> None:
        self.db.close()

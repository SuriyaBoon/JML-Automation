from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from .models import JMLRequest, utc_now


class JMLStore:
    def __init__(self, path: str = "runtime/jml.db") -> None:
        self.path = str(Path(path))
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.executescript("""
                PRAGMA foreign_keys = ON;
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS jml_requests (
                    request_id TEXT PRIMARY KEY, request_type TEXT NOT NULL,
                    employee_id TEXT NOT NULL, username TEXT NOT NULL,
                    first_name TEXT NOT NULL, last_name TEXT NOT NULL,
                    department TEXT NOT NULL, old_department TEXT,
                    job_title TEXT, manager_id TEXT NOT NULL,
                    requested_by TEXT NOT NULL, effective_at TEXT NOT NULL,
                    reason TEXT, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL REFERENCES jml_requests(request_id),
                    actor_id TEXT NOT NULL, decision TEXT NOT NULL,
                    reason TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS plans (
                    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL UNIQUE REFERENCES jml_requests(request_id),
                    operations_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS verifications (
                    verification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL REFERENCES jml_requests(request_id),
                    actor_id TEXT NOT NULL, result TEXT NOT NULL,
                    checks_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS executions (
                    execution_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL REFERENCES jml_requests(request_id),
                    actor_id TEXT NOT NULL, dry_run INTEGER NOT NULL,
                    results_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL UNIQUE REFERENCES jml_requests(request_id),
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL, actor_id TEXT NOT NULL,
                    actor_role TEXT NOT NULL, event_type TEXT NOT NULL,
                    details_json TEXT NOT NULL, occurred_at TEXT NOT NULL,
                    previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL UNIQUE
                );
                CREATE INDEX IF NOT EXISTS idx_audit_request ON audit_events(request_id, event_id);
            """)
            db.commit()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def add_request(self, request: JMLRequest) -> None:
        now = utc_now()
        with closing(self._connect()) as db:
            db.execute("""INSERT INTO jml_requests VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                request.request_id, request.request_type, request.employee_id,
                request.username, request.first_name, request.last_name,
                request.department, request.old_department, request.job_title,
                request.manager_id, request.requested_by, request.effective_at,
                request.reason, "submitted", now, now,
            ))
            db.commit()

    def get(self, request_id: str) -> dict[str, Any]:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM jml_requests WHERE request_id = ?", (request_id,)).fetchone()
        if row is None:
            raise KeyError(f"request not found: {request_id}")
        return dict(row)

    def set_status(self, request_id: str, status: str) -> None:
        with closing(self._connect()) as db:
            db.execute("UPDATE jml_requests SET status = ?, updated_at = ? WHERE request_id = ?", (status, utc_now(), request_id))
            db.commit()

    def add_approval(self, request_id: str, actor_id: str, decision: str, reason: str) -> None:
        with closing(self._connect()) as db:
            db.execute("INSERT INTO approvals(request_id, actor_id, decision, reason, created_at) VALUES (?,?,?,?,?)", (request_id, actor_id, decision, reason, utc_now()))
            db.commit()

    def add_plan(self, request_id: str, operations: list[dict[str, Any]]) -> None:
        with closing(self._connect()) as db:
            db.execute("INSERT OR REPLACE INTO plans(request_id, operations_json, created_at) VALUES (?,?,?)", (request_id, json.dumps(operations, sort_keys=True), utc_now()))
            db.commit()

    def get_plan(self, request_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            row = db.execute("SELECT operations_json FROM plans WHERE request_id = ?", (request_id,)).fetchone()
        if row is None:
            raise KeyError(f"plan not found: {request_id}")
        return json.loads(row[0])

    def add_verification(self, request_id: str, actor_id: str, result: str, checks: dict[str, Any]) -> None:
        with closing(self._connect()) as db:
            db.execute("INSERT INTO verifications(request_id, actor_id, result, checks_json, created_at) VALUES (?,?,?,?,?)", (request_id, actor_id, result, json.dumps(checks, sort_keys=True), utc_now()))
            db.commit()

    def add_execution(self, request_id: str, actor_id: str, dry_run: bool, results: list[dict[str, Any]]) -> None:
        with closing(self._connect()) as db:
            db.execute("INSERT INTO executions(request_id, actor_id, dry_run, results_json, created_at) VALUES (?,?,?,?,?)", (request_id, actor_id, int(dry_run), json.dumps(results, sort_keys=True), utc_now()))
            db.commit()

    def last_execution_actor(self, request_id: str) -> str | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT actor_id FROM executions WHERE request_id = ? ORDER BY execution_id DESC LIMIT 1", (request_id,)).fetchone()
        return None if row is None else str(row[0])

    def upsert_ticket(self, ticket_id: str, request_id: str, status: str, summary: str) -> dict[str, Any]:
        now = utc_now()
        with closing(self._connect()) as db:
            db.execute("""INSERT INTO tickets(ticket_id, request_id, status, summary, created_at, updated_at)
                         VALUES (?,?,?,?,?,?)
                         ON CONFLICT(request_id) DO UPDATE SET status=excluded.status, summary=excluded.summary, updated_at=excluded.updated_at""", (ticket_id, request_id, status, summary, now, now))
            db.commit()
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM tickets WHERE request_id = ?", (request_id,)).fetchone()
        return dict(row)

    def audit(self, request_id: str, actor_id: str, actor_role: str, event_type: str, details: dict[str, Any]) -> None:
        with closing(self._connect()) as db:
            previous = db.execute("SELECT event_hash FROM audit_events WHERE request_id = ? ORDER BY event_id DESC LIMIT 1", (request_id,)).fetchone()
            previous_hash = "" if previous is None else previous[0]
            occurred = utc_now()
            body = {"request_id": request_id, "actor_id": actor_id, "actor_role": actor_role, "event_type": event_type, "details": details, "occurred_at": occurred, "previous_hash": previous_hash}
            event_hash = hashlib.sha256((previous_hash + json.dumps(body, sort_keys=True, separators=(",", ":"))).encode()).hexdigest()
            db.execute("INSERT INTO audit_events(request_id, actor_id, actor_role, event_type, details_json, occurred_at, previous_hash, event_hash) VALUES (?,?,?,?,?,?,?,?)", (request_id, actor_id, actor_role, event_type, json.dumps(details, sort_keys=True), occurred, previous_hash, event_hash))
            db.commit()

    def events(self, request_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT * FROM audit_events WHERE request_id = ? ORDER BY event_id", (request_id,)).fetchall()
        return [dict(row) for row in rows]

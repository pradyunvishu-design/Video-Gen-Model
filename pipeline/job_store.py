"""SQLite-backed worker job state with idempotency and restart recovery."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


class JobStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL, stage TEXT NOT NULL,
                    status TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0, payload TEXT NOT NULL,
                    result TEXT, error TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                )
            """)
            connection.execute("UPDATE jobs SET status='queued', updated_at=? WHERE status='running'", (self._now(),))

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create(self, job_id: str, key: str, stage: str, payload: dict) -> tuple[dict, bool]:
        with self._lock, self._connect() as connection:
            existing = connection.execute("SELECT * FROM jobs WHERE idempotency_key=?", (key,)).fetchone()
            if existing:
                return self._row(existing), False
            now = self._now()
            connection.execute(
                "INSERT INTO jobs(id,idempotency_key,stage,status,payload,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (job_id, key, stage, "queued", json.dumps(payload), now, now),
            )
        return self.get(job_id), True

    def update(self, job_id: str, **values: Any) -> dict:
        allowed = {"status", "progress", "result", "error", "cancel_requested"}
        updates = {key: value for key, value in values.items() if key in allowed}
        if "result" in updates and isinstance(updates["result"], (dict, list)):
            updates["result"] = json.dumps(updates["result"], default=str)
        updates["updated_at"] = self._now()
        columns = ",".join(f"{key}=?" for key in updates)
        with self._lock, self._connect() as connection:
            connection.execute(f"UPDATE jobs SET {columns} WHERE id=?", (*updates.values(), job_id))
        return self.get(job_id)

    def get(self, job_id: str) -> dict:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise KeyError(job_id)
        return self._row(row)

    def list_all(self, limit: int = 1000) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 5000)),)
            ).fetchall()
        return [self._row(row) for row in rows]

    @staticmethod
    def _row(row: sqlite3.Row) -> dict:
        value = dict(row)
        value["payload"] = json.loads(value["payload"])
        value["result"] = json.loads(value["result"]) if value.get("result") else None
        value["cancel_requested"] = bool(value["cancel_requested"])
        return value

"""
Database — SQLite persistence layer for EOL test records.

Schema
------
test_records  : one row per test run
step_results  : one row per executed step, FK → test_records

All writes are done synchronously in the calling thread.
SQLite WAL mode is enabled so UI-thread reads do not block writes.

Public API
----------
Database(db_path: str)
    .save_record(record: TestRecord) -> int          # returns row id
    .update_report_path(record_id: int, path: str)
    .query_by_sn(sn: str) -> list[TestRecord]
    .query_recent(n: int) -> list[TestRecord]
"""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime
from typing import Any

from app.engine.models import TestRecord, StepResult, UserRecord


_DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS test_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sn              TEXT    NOT NULL,
    plan_name       TEXT,
    plan_version    TEXT,
    start_time      TEXT,
    end_time        TEXT,
    overall_result  TEXT,
    report_path     TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS step_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id   INTEGER NOT NULL REFERENCES test_records(id) ON DELETE CASCADE,
    seq_name    TEXT,
    step_name   TEXT,
    result      TEXT,
    value_num   REAL,
    value_str   TEXT,
    unit        TEXT,
    message     TEXT,
    duration_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_records_sn     ON test_records(sn);
CREATE INDEX IF NOT EXISTS idx_results_record ON step_results(record_id);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'operator',
    created_at    TEXT    NOT NULL
);
"""


class Database:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._path = db_path
        self._init_schema()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_record(self, record: TestRecord) -> int:
        """Insert *record* and all its step_results.  Returns the new record id."""
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO test_records
                    (sn, plan_name, plan_version, start_time, end_time,
                     overall_result, report_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.sn,
                    record.plan_name,
                    record.plan_version,
                    record.start_time,
                    record.end_time,
                    record.overall_result,
                    getattr(record, "report_path", ""),
                ),
            )
            record_id = cur.lastrowid

            for sr in record.step_results:
                num_val, str_val = self._split_value(sr.value)
                conn.execute(
                    """
                    INSERT INTO step_results
                        (record_id, seq_name, step_name, result,
                         value_num, value_str, unit, message, duration_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record_id,
                        sr.seq_name,
                        sr.step_name,
                        sr.result,
                        num_val,
                        str_val,
                        sr.unit,
                        sr.message,
                        sr.duration_ms,
                    ),
                )
        return record_id

    def update_report_path(self, record_id: int, path: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE test_records SET report_path=? WHERE id=?",
                (path, record_id),
            )

    def query_by_sn(self, sn: str) -> list[TestRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM test_records WHERE sn=? ORDER BY id DESC",
                (sn,),
            ).fetchall()
        return [self._build_record(conn, row) for row in rows]

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    def get_all_users(self) -> list[UserRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, username, role, created_at FROM users ORDER BY id"
            ).fetchall()
        return [UserRecord(id=r["id"], username=r["username"], role=r["role"], created_at=r["created_at"]) for r in rows]

    def add_user(self, username: str, password: str, role: str) -> int:
        ph = self._hash_password(password)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                (username, ph, role, now),
            )
        return cur.lastrowid

    def update_user_password(self, user_id: int, new_password: str) -> None:
        ph = self._hash_password(new_password)
        with self._connect() as conn:
            conn.execute("UPDATE users SET password_hash=? WHERE id=?", (ph, user_id))

    def update_user_role(self, user_id: int, role: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))

    def delete_user(self, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM users WHERE id=?", (user_id,))

    def verify_user(self, username: str, password: str) -> UserRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, role, created_at FROM users WHERE username=?",
                (username,),
            ).fetchone()
        if row is None:
            return None
        if self._check_password(password, row["password_hash"]):
            return UserRecord(id=row["id"], username=row["username"], role=row["role"], created_at=row["created_at"])
        return None

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        h = hashlib.sha256((salt + password).encode()).hexdigest()
        return f"{salt}:{h}"

    @staticmethod
    def _check_password(password: str, stored: str) -> bool:
        try:
            salt, h = stored.split(":", 1)
        except ValueError:
            return False
        return hashlib.sha256((salt + password).encode()).hexdigest() == h

    def query_recent(self, n: int) -> list[TestRecord]:
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM test_records ORDER BY id DESC LIMIT ?",
                (n,),
            ).fetchall()
            return [self._build_record(conn, row) for row in rows]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_DDL)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _build_record(self, conn: sqlite3.Connection, row: sqlite3.Row) -> TestRecord:
        step_rows = conn.execute(
            "SELECT * FROM step_results WHERE record_id=? ORDER BY id",
            (row["id"],),
        ).fetchall()
        step_results = [
            StepResult(
                step_name=sr["step_name"],
                seq_name=sr["seq_name"] or "",
                result=sr["result"],
                value=sr["value_num"] if sr["value_num"] is not None else sr["value_str"],
                unit=sr["unit"] or "",
                message=sr["message"] or "",
                duration_ms=sr["duration_ms"] or 0,
            )
            for sr in step_rows
        ]
        record = TestRecord(
            id=row["id"],
            sn=row["sn"],
            plan_name=row["plan_name"] or "",
            plan_version=row["plan_version"] or "",
            start_time=row["start_time"] or "",
            end_time=row["end_time"] or "",
            overall_result=row["overall_result"] or "",
            step_results=step_results,
        )
        record.report_path = row["report_path"] or ""  # type: ignore[attr-defined]
        return record

    @staticmethod
    def _split_value(value: Any) -> tuple[float | None, str]:
        """Split a value into (numeric, string) for storage."""
        if value is None:
            return (None, "")
        try:
            return (float(value), str(value))
        except (TypeError, ValueError):
            return (None, str(value))

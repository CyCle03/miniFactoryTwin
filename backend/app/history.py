import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import MachineEvent, ProductResult


class HistoryRepository:
    def __init__(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS events (
                  id INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE,
                  session_id TEXT NOT NULL, timestamp TEXT NOT NULL,
                  event_type TEXT NOT NULL, severity TEXT NOT NULL,
                  message TEXT NOT NULL, product_id INTEGER, metadata TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_time ON events(timestamp DESC);
                CREATE TABLE IF NOT EXISTS production (
                  id INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE,
                  session_id TEXT NOT NULL, product_id INTEGER NOT NULL,
                  result TEXT NOT NULL CHECK(result IN ('GOOD','REJECT')),
                  started_at TEXT NOT NULL, inspected_at TEXT NOT NULL,
                  completed_at TEXT NOT NULL, cycle_time_seconds REAL NOT NULL,
                  created_at TEXT NOT NULL,
                  UNIQUE(session_id, product_id)
                );
                CREATE INDEX IF NOT EXISTS idx_production_time ON production(completed_at DESC);
            """)

    def record_event(self, event: MachineEvent) -> bool:
        payload = event.model_dump(mode="json")
        with self._lock, self._connect() as db:
            cursor = db.execute(
                """INSERT OR IGNORE INTO events
                (event_id,session_id,timestamp,event_type,severity,message,product_id,metadata)
                VALUES (?,?,?,?,?,?,?,?)""",
                (event.event_id, event.session_id, event.timestamp.isoformat(),
                 event.event_type, event.severity.value, event.message,
                 event.product_id, json.dumps(payload["metadata"], separators=(",", ":"))),
            )
            if event.event_type == "product_completed":
                meta = event.metadata
                db.execute(
                    """INSERT OR IGNORE INTO production
                    (event_id,session_id,product_id,result,started_at,inspected_at,
                     completed_at,cycle_time_seconds,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (event.event_id, event.session_id, event.product_id, meta["result"],
                     meta["started_at"], meta["inspected_at"], meta["completed_at"],
                     meta["cycle_time_seconds"], datetime.now().astimezone().isoformat()),
                )
            return cursor.rowcount == 1

    def production(self, limit: int, start: datetime | None = None,
                   end: datetime | None = None, result: ProductResult | None = None) -> list[dict[str, Any]]:
        clauses, params = self._filters("completed_at", start, end)
        if result:
            clauses.append("result = ?"); params.append(result.value)
        return self._rows("production", clauses, params, limit, "completed_at")

    def events(self, limit: int, start: datetime | None = None, end: datetime | None = None,
               severity: str | None = None, event_type: str | None = None) -> list[dict[str, Any]]:
        clauses, params = self._filters("timestamp", start, end)
        if severity:
            clauses.append("severity = ?"); params.append(severity)
        if event_type:
            clauses.append("event_type = ?"); params.append(event_type)
        rows = self._rows("events", clauses, params, limit, "timestamp")
        for row in rows:
            row["metadata"] = json.loads(row["metadata"])
        return rows

    def summary(self) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("""SELECT COUNT(*) total,
                COALESCE(SUM(result='GOOD'),0) good,
                COALESCE(SUM(result='REJECT'),0) reject,
                AVG(cycle_time_seconds) average_cycle_time,
                MIN(cycle_time_seconds) min_cycle_time,
                MAX(cycle_time_seconds) max_cycle_time
                FROM production""").fetchone()
            recent = db.execute("SELECT cycle_time_seconds FROM production ORDER BY completed_at DESC LIMIT 1").fetchone()
        data = dict(row)
        data["recent_cycle_time"] = recent[0] if recent else None
        return data

    def buckets(self, limit: int = 24) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("""SELECT substr(completed_at,1,13)||':00:00Z' bucket,
                COUNT(*) total, SUM(result='GOOD') good, SUM(result='REJECT') reject,
                AVG(cycle_time_seconds) average_cycle_time
                FROM production GROUP BY bucket ORDER BY bucket DESC LIMIT ?""", (limit,)).fetchall()
        return [dict(row) for row in reversed(rows)]

    @staticmethod
    def _filters(column: str, start: datetime | None, end: datetime | None) -> tuple[list[str], list[Any]]:
        clauses: list[str] = []; params: list[Any] = []
        if start: clauses.append(f"{column} >= ?"); params.append(start.isoformat())
        if end: clauses.append(f"{column} <= ?"); params.append(end.isoformat())
        return clauses, params

    def _rows(self, table: str, clauses: list[str], params: list[Any],
              limit: int, order: str) -> list[dict[str, Any]]:
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as db:
            rows = db.execute(f"SELECT * FROM {table}{where} ORDER BY {order} DESC LIMIT ?",
                              (*params, limit)).fetchall()
        return [dict(row) for row in rows]

"""SQLite unit of work, migration recovery and canonical event persistence."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from silvia.core import DomainError, encode, now, uid
from silvia.security import Redactor


class SQLiteStore:
    def __init__(self, path: Path | str, *, migrate: bool = False, redactor: Redactor | None = None):
        self.path = str(path)
        self.redactor = redactor or Redactor()
        self.lock = threading.RLock()
        if self.path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=10000")
        try:
            tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            version = self.db.execute("SELECT max(version) FROM schema_migrations").fetchone()[0] if "schema_migrations" in tables else 0
            version = version or 0
            if version > 1:
                raise DomainError("incompatible-store", "Database schema is newer than this application.")
            if self.db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise DomainError("corrupt-session", "Database integrity check failed.")
            if version < 1:
                if tables and not migrate:
                    raise DomainError("migration-required", "Existing database requires explicit migration.", "Back up and run silvia storage migrate.")
                if tables and self.path != ":memory:":
                    with sqlite3.connect(self.path + ".backup-" + uid()) as backup:
                        self.db.backup(backup)
                sql = (Path(__file__).parent / "001_initial.sql").read_text(encoding="utf-8")
                self.db.executescript("BEGIN IMMEDIATE; CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);\n" + sql + "\nINSERT INTO schema_migrations VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ','now')); COMMIT;")
            self.db.execute("PRAGMA journal_mode=WAL")
        except DomainError:
            self.db.close()
            raise
        except sqlite3.Error as exc:
            self.db.close()
            raise DomainError("persistence", "Cannot initialize canonical storage.", "Check database integrity and SQLite FTS5 availability.") from exc

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        with self.lock:
            if self.db.in_transaction:
                yield self
                return
            try:
                self.db.execute("BEGIN IMMEDIATE")
                yield self
                self.db.execute("COMMIT")
            except BaseException:
                if self.db.in_transaction:
                    self.db.execute("ROLLBACK")
                raise

    def one(self, query: str, params: tuple = ()) -> dict | None:
        with self.lock:
            row = self.db.execute(query, params).fetchone()
            return dict(row) if row else None

    def all(self, query: str, params: tuple = ()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.db.execute(query, params)]

    def record(self, kind: str, id: str) -> dict | None:
        row = self.one("SELECT data FROM records WHERE kind=? AND id=?", (kind, id))
        return json.loads(row["data"]) if row else None

    def records(self, kind: str, session_id: str | None = None) -> list[dict]:
        sql, params = "SELECT data FROM records WHERE kind=?", (kind,)
        if session_id is not None:
            sql, params = sql + " AND session_id=?", (kind, session_id)
        return [json.loads(r["data"]) for r in self.all(sql + " ORDER BY id", params)]

    def put(self, kind: str, id: str, data: dict, session_id: str | None = None, revision: int | None = None):
        if not self.db.in_transaction:
            raise RuntimeError("Canonical writes require a transaction")
        self.db.execute("INSERT INTO records VALUES(?,?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data,revision=excluded.revision",
                        (kind, id, session_id, revision, encode(self.redactor.clean(data))))

    def append(self, session_id: str, kind: str, payload: dict, *, actor: str = "controller", event_id: str | None = None,
               correlation_id: str | None = None, causation_id: str | None = None, artifact_refs: list | None = None) -> dict:
        if not self.db.in_transaction:
            raise RuntimeError("Events require the mutation transaction")
        if kind.split(".")[0] not in {"session", "objective", "artifact", "gate", "authorization", "skill", "agent", "work_item", "tool", "evidence", "memory", "report", "budget"} or not isinstance(payload, dict):
            raise DomainError("invalid-event", "Invalid event kind or payload.")
        session = self.one("SELECT * FROM sessions WHERE id=?", (session_id,))
        if session is None:
            raise DomainError("not-found", "Session does not exist.")
        event_id = event_id or uid()
        existing = self.one("SELECT data FROM events WHERE event_id=?", (event_id,))
        clean = self.redactor.clean(payload)
        if existing:
            old = json.loads(existing["data"])
            if old["session_id"] != session_id or old["kind"] != kind or old["payload"] != clean:
                raise DomainError("event-conflict", "Event identity already has different content.")
            return old
        if causation_id and not self.one("SELECT 1 FROM events WHERE event_id=? AND session_id=?", (causation_id, session_id)):
            raise DomainError("invalid-causation", "Causation must reference an existing event in this session.")
        if len(encode(clean).encode()) > 65536:
            raise DomainError("payload-too-large", "Store large content as an artifact.")
        sequence = self.one("SELECT coalesce(max(sequence),0)+1 AS n FROM events WHERE session_id=?", (session_id,))["n"]
        event = dict(schema_version=1, event_id=event_id, project_id=session["project_id"], session_id=session_id,
                     objective_revision=session["revision"], sequence=sequence, timestamp=now(), correlation_id=correlation_id or uid(),
                     causation_id=causation_id, actor={"type": actor.split(":")[0], "id": actor}, kind=kind,
                     payload=clean, artifact_refs=artifact_refs or [], redaction={"version": 1, "applied": clean != payload})
        self.db.execute("INSERT INTO events VALUES(?,?,?,?)", (event_id, session_id, sequence, encode(event)))
        return event

    def read(self, session_id: str, cursor: int = 0, limit: int = 1000) -> list[dict]:
        if cursor < 0 or not 1 <= limit <= 10000:
            raise DomainError("validation", "Invalid event cursor or page size.")
        return [json.loads(r["data"]) for r in self.all("SELECT data FROM events WHERE session_id=? AND sequence>? ORDER BY sequence LIMIT ?", (session_id, cursor, limit))]


class InProcessStore(SQLiteStore):
    """In-process adapter with identical transactional semantics and no disk state."""
    def __init__(self, **kwargs):
        super().__init__(":memory:", **kwargs)

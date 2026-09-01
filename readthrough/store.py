"""Durable, resumable scan state.

Everything is keyed by file content hash, so re-running after an interruption
picks up exactly where it stopped, and re-running after edits re-scans only
what changed. Failed API calls are recorded as rows, not dropped -- the report
lists them so you know what was not covered.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS files (
    rel     TEXT PRIMARY KEY,
    abspath TEXT NOT NULL,
    sha256  TEXT NOT NULL,
    lang    TEXT,
    loc     INTEGER,
    size    INTEGER,
    status  TEXT NOT NULL,
    note    TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tasks (
    key         TEXT PRIMARY KEY,
    rel         TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    lens        TEXT NOT NULL,
    chunk_idx   INTEGER NOT NULL,
    repeat_idx  INTEGER NOT NULL,
    start_line  INTEGER,
    end_line    INTEGER,
    status      TEXT NOT NULL,
    attempts    INTEGER DEFAULT 0,
    error       TEXT,
    in_tokens   INTEGER DEFAULT 0,
    out_tokens  INTEGER DEFAULT 0,
    duration_ms INTEGER DEFAULT 0,
    updated_at  REAL,
    -- The model that actually answered, which is not necessarily the one that
    -- was asked for: a proxy may resolve an alias or fall through to a
    -- different provider entirely. Recorded per task, because a resumed scan
    -- mixes models -- the passes cached from an earlier run keep whatever
    -- answered them, and a scan-wide field would misattribute their findings.
    served_model TEXT
);
CREATE INDEX IF NOT EXISTS tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS tasks_rel ON tasks(rel);

CREATE TABLE IF NOT EXISTS findings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_key    TEXT NOT NULL,
    rel         TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    lens        TEXT NOT NULL,
    repeat_idx  INTEGER NOT NULL,
    category    TEXT,
    severity    TEXT,
    confidence  TEXT,
    start_line  INTEGER,
    end_line    INTEGER,
    symbol      TEXT,
    title       TEXT,
    explanation TEXT,
    trigger     TEXT,
    assumptions TEXT,
    fix         TEXT,
    test        TEXT
);
CREATE INDEX IF NOT EXISTS findings_rel ON findings(rel);

CREATE TABLE IF NOT EXISTS verdicts (
    fingerprint TEXT PRIMARY KEY,
    verdict     TEXT,
    reasoning   TEXT,
    severity    TEXT,
    in_tokens   INTEGER DEFAULT 0,
    out_tokens  INTEGER DEFAULT 0
);
"""


class Store:
    """Thread-safe wrapper: one connection per thread, one write lock, WAL.

    Per-thread connections rather than one shared one. The scan runs its passes
    in a ThreadPoolExecutor and the workers both read (`prior_attempts`) and
    write (`record_task`); a single connection shared across them raises
    "bad parameter or other API misuse" whenever a read lands inside another
    thread's open transaction. Guarding only the writers with the lock is not
    enough -- the reads have to be serialised too, and doing it by giving each
    thread its own connection keeps the read paths lock-free. WAL lets the
    readers proceed while a writer holds the file.

    `self.lock` still serialises writers, because `record_task` is a
    multi-statement transaction that must not interleave with another.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self._local = threading.local()
        self._conns: list[sqlite3.Connection] = []
        self.conn.executescript(SCHEMA)
        # `CREATE TABLE IF NOT EXISTS` will not add a column to a scan.db from
        # an older version, and resume is the whole point of that file.
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(tasks)")}
        if "served_model" not in cols:
            self.conn.execute("ALTER TABLE tasks ADD COLUMN served_model TEXT")

    @property
    def conn(self) -> sqlite3.Connection:
        """This thread's connection, opened on first use."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            # isolation_level=None turns off the driver's legacy implicit
            # transactions. record_task() drives BEGIN IMMEDIATE/COMMIT itself,
            # and under the default mode the driver has already opened a
            # transaction by then, so the explicit BEGIN fails and the explicit
            # COMMIT desyncs the driver. It also lets the WAL pragma below take
            # effect, which it cannot inside a transaction.
            # check_same_thread=False only so close() can reap the worker
            # threads' connections from the main thread once the pool has been
            # joined. Nothing else crosses threads: this property hands every
            # thread its own.
            conn = sqlite3.connect(str(self.path), check_same_thread=False,
                                   isolation_level=None, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
            with self.lock:
                self._conns.append(conn)
        return conn

    # ---- meta -----------------------------------------------------------
    def set_meta(self, key: str, value) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO meta(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value)))
            self.conn.commit()

    def get_meta(self, key: str, default=None):
        row = self.conn.execute("SELECT value FROM meta WHERE key=?",
                                (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    # ---- files ----------------------------------------------------------
    def upsert_files(self, infos) -> None:
        with self.lock:
            self.conn.executemany(
                "INSERT INTO files(rel,abspath,sha256,lang,loc,size,status,note) "
                "VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(rel) DO UPDATE SET "
                "abspath=excluded.abspath, sha256=excluded.sha256, "
                "lang=excluded.lang, loc=excluded.loc, size=excluded.size, "
                "status=excluded.status, note=excluded.note",
                [(i.rel, i.path, i.sha256, i.lang, i.loc, i.size, i.status, i.note)
                 for i in infos])
            self.conn.commit()

    def files(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM files ORDER BY rel").fetchall()

    def abspath(self, rel: str) -> str:
        row = self.conn.execute("SELECT abspath FROM files WHERE rel=?",
                                (rel,)).fetchone()
        return row["abspath"] if row else ""

    # ---- tasks ----------------------------------------------------------
    def task_done(self, key: str) -> bool:
        row = self.conn.execute(
            "SELECT status FROM tasks WHERE key=?", (key,)).fetchone()
        return bool(row) and row["status"] == "done"

    def prior_attempts(self, key: str) -> int:
        row = self.conn.execute(
            "SELECT attempts FROM tasks WHERE key=?", (key,)).fetchone()
        return row["attempts"] if row else 0

    def completed_keys(self) -> set[str]:
        rows = self.conn.execute(
            "SELECT key FROM tasks WHERE status='done'").fetchall()
        return {r["key"] for r in rows}

    def record_task(self, *, key, rel, sha256, lens, chunk_idx, repeat_idx,
                    start_line, end_line, status, attempts, error,
                    in_tokens, out_tokens, duration_ms, findings,
                    served_model=None) -> None:
        """Task result and its findings land in one transaction.

        This is what makes a crash safe: a task is either fully recorded with
        its findings, or absent and therefore retried on the next run.
        """
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                cur.execute("DELETE FROM findings WHERE task_key=?", (key,))
                cur.execute(
                    "INSERT INTO tasks(key,rel,sha256,lens,chunk_idx,repeat_idx,"
                    "start_line,end_line,status,attempts,error,in_tokens,"
                    "out_tokens,duration_ms,updated_at,served_model) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET status=excluded.status, "
                    "attempts=excluded.attempts, error=excluded.error, "
                    "in_tokens=excluded.in_tokens, out_tokens=excluded.out_tokens, "
                    "duration_ms=excluded.duration_ms, updated_at=excluded.updated_at, "
                    "served_model=excluded.served_model",
                    (key, rel, sha256, lens, chunk_idx, repeat_idx, start_line,
                     end_line, status, attempts, error, in_tokens, out_tokens,
                     duration_ms, time.time(), served_model))
                for f in findings:
                    cur.execute(
                        "INSERT INTO findings(task_key,rel,sha256,lens,repeat_idx,"
                        "category,severity,confidence,start_line,end_line,symbol,"
                        "title,explanation,trigger,assumptions,fix,test) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (key, rel, sha256, lens, repeat_idx,
                         f.get("category"), f.get("severity"), f.get("confidence"),
                         f.get("start_line"), f.get("end_line"), f.get("symbol"),
                         f.get("title"), f.get("explanation"), f.get("trigger"),
                         f.get("assumptions"), f.get("suggested_fix"),
                         f.get("suggested_test")))
                cur.execute("COMMIT")
            except Exception:
                cur.execute("ROLLBACK")
                raise

    # Both reads below are filtered to the file content that is on disk NOW.
    #
    # Resume keys tasks by content hash, so editing a file plans fresh passes
    # for the new content -- but the rows recorded against the OLD content stay
    # in the database. Reporting those verbatim means fixing a defect,
    # re-scanning, and being told the defect is still there, quoting line
    # numbers that have moved. That is the exact inverse of what this tool
    # promises, and it is silent: nothing in the output marks the finding as
    # describing a file that no longer looks like that.
    #
    # Filtering on read rather than deleting on write keeps the history (a
    # `report` rebuild of an older scan is still faithful to it) and keeps the
    # coverage arithmetic honest: passes against superseded content are not
    # counted as covering the file, so it correctly shows up as unreviewed
    # until the new content is actually scanned.
    _CURRENT = ("JOIN files fi ON fi.rel = {alias}.rel "
                "AND fi.sha256 = {alias}.sha256 ")

    def tasks(self, status: str | None = None) -> list[sqlite3.Row]:
        sql = "SELECT t.* FROM tasks t " + self._CURRENT.format(alias="t")
        if status:
            return self.conn.execute(
                sql + "WHERE t.status=? ORDER BY t.rel", (status,)).fetchall()
        return self.conn.execute(sql + "ORDER BY t.rel").fetchall()

    def raw_findings(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT f.*, t.served_model FROM findings f "
            "LEFT JOIN tasks t ON t.key = f.task_key "
            + self._CURRENT.format(alias="f")
            + "ORDER BY f.rel, f.start_line").fetchall()

    def token_totals(self) -> tuple[int, int]:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(in_tokens),0) i, COALESCE(SUM(out_tokens),0) o "
            "FROM tasks").fetchone()
        vrow = self.conn.execute(
            "SELECT COALESCE(SUM(in_tokens),0) i, COALESCE(SUM(out_tokens),0) o "
            "FROM verdicts").fetchone()
        return row["i"] + vrow["i"], row["o"] + vrow["o"]

    # ---- verification ---------------------------------------------------
    def set_verdict(self, fingerprint, verdict, reasoning, severity,
                    in_tokens=0, out_tokens=0) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO verdicts(fingerprint,verdict,reasoning,severity,"
                "in_tokens,out_tokens) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(fingerprint) DO UPDATE SET verdict=excluded.verdict, "
                "reasoning=excluded.reasoning, severity=excluded.severity, "
                "in_tokens=excluded.in_tokens, out_tokens=excluded.out_tokens",
                (fingerprint, verdict, reasoning, severity, in_tokens, out_tokens))
            self.conn.commit()

    def verdicts(self) -> dict:
        return {r["fingerprint"]: dict(r)
                for r in self.conn.execute("SELECT * FROM verdicts").fetchall()}

    def close(self) -> None:
        with self.lock:
            for conn in self._conns:
                conn.close()
            self._conns.clear()
        self._local.conn = None

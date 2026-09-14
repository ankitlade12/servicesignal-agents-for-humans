import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def path():
    return os.getenv("SERVICESIGNAL_DB", "data/servicesignal.sqlite")


@contextmanager
def connect(write=False):
    conn = sqlite3.connect(path(), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    if write:
        conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init():
    Path(path()).parent.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript("""
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, public_id TEXT UNIQUE NOT NULL,
            created_at REAL NOT NULL, clock_offset REAL NOT NULL DEFAULT 0, model_calls INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS changes (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            revision INTEGER NOT NULL DEFAULT 1, source TEXT NOT NULL, source_hash TEXT NOT NULL,
            proposal TEXT NOT NULL, facts TEXT, state TEXT NOT NULL, plan_hash TEXT,
            expected_version INTEGER, approved_at REAL, created_at REAL NOT NULL,
            expires_at REAL, mode TEXT NOT NULL, metrics TEXT NOT NULL DEFAULT '{}',
            UNIQUE(workspace_id, source_hash)
        );
        CREATE TABLE IF NOT EXISTS publications (
            workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
            version INTEGER NOT NULL DEFAULT 0, payload TEXT, action_key TEXT
        );
        CREATE TABLE IF NOT EXISTS actions (
            id TEXT PRIMARY KEY, change_id TEXT NOT NULL REFERENCES changes(id) ON DELETE CASCADE,
            revision INTEGER NOT NULL, destination TEXT NOT NULL, state TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '', verified_at REAL, observed_hash TEXT,
            observed_payload TEXT, attempts INTEGER DEFAULT 0,
            UNIQUE(change_id, revision, destination)
        );
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, change_id TEXT NOT NULL REFERENCES changes(id) ON DELETE CASCADE,
            revision INTEGER NOT NULL, kind TEXT NOT NULL, due_at REAL NOT NULL,
            state TEXT NOT NULL DEFAULT 'QUEUED', lease_until REAL, attempts INTEGER DEFAULT 0,
            UNIQUE(change_id, revision, kind)
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            change_id TEXT, kind TEXT NOT NULL, detail TEXT NOT NULL, created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS usage_days (day TEXT PRIMARY KEY, calls INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS jobs_due ON jobs(state, due_at);
        CREATE INDEX IF NOT EXISTS change_workspace ON changes(workspace_id, created_at);
        """)
        c.execute("BEGIN IMMEDIATE")
        columns = {row[1] for row in c.execute("PRAGMA table_info(workspaces)")}
        if "program" not in columns:
            c.execute("ALTER TABLE workspaces ADD COLUMN program TEXT")
        c.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            sha256 TEXT NOT NULL, original BLOB NOT NULL, source TEXT NOT NULL, pages INTEGER NOT NULL,
            created_at REAL NOT NULL, UNIQUE(workspace_id, sha256)
        );
        """)
        c.execute("INSERT OR IGNORE INTO settings VALUES ('publisher_key', ?)", (secrets.token_urlsafe(40),))


def now(c, workspace_id):
    row = c.execute("SELECT clock_offset FROM workspaces WHERE id=?", (workspace_id,)).fetchone()
    return time.time() + (row[0] if row else 0)


def event(c, workspace_id, change_id, kind, detail):
    c.execute(
        "INSERT INTO events(workspace_id,change_id,kind,detail,created_at) VALUES(?,?,?,?,?)",
        (workspace_id, change_id, kind, detail, now(c, workspace_id)),
    )


def program(workspace):
    from .domain import PROGRAM

    raw = dict(workspace).get("program")
    return json.loads(raw) if raw else dict(PROGRAM)

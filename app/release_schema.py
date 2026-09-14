"""Additive migrations for account security, independent notices, and delivery records."""


def migrate(c):
    columns = {r[1] for r in c.execute("PRAGMA table_info(users)")}
    for name, definition in {
        "mfa_secret": "TEXT",
        "mfa_pending": "TEXT",
        "mfa_pending_until": "REAL",
        "mfa_last_step": "INTEGER NOT NULL DEFAULT -1",
        "recovery_codes": "TEXT NOT NULL DEFAULT '[]'",
    }.items():
        if name not in columns:
            c.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS password_resets (
        token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
        expires_at REAL NOT NULL, used INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS notice_publications (
        change_id TEXT PRIMARY KEY REFERENCES changes(id) ON DELETE CASCADE,
        workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        payload TEXT NOT NULL, action_key TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS deliveries (
        id TEXT PRIMARY KEY, workspace_id TEXT REFERENCES workspaces(id) ON DELETE CASCADE,
        change_id TEXT REFERENCES changes(id) ON DELETE CASCADE, revision INTEGER,
        channel TEXT NOT NULL, target TEXT NOT NULL, body TEXT NOT NULL, content_hash TEXT NOT NULL,
        state TEXT NOT NULL, provider_id TEXT, detail TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL, approved_at REAL, claimed_at REAL, observed_at REAL,
        expires_at REAL NOT NULL, actor_id TEXT, UNIQUE(workspace_id,content_hash)
    );
    CREATE INDEX IF NOT EXISTS deliveries_pending ON deliveries(state,created_at);
    """)
    # Preserve already-published pilot notices on upgrade; do not republish anything.
    c.execute("""INSERT OR IGNORE INTO notice_publications(change_id,workspace_id,payload,action_key)
        SELECT ch.id,p.workspace_id,p.payload,p.action_key FROM publications p
        JOIN workspaces w ON w.id=p.workspace_id JOIN changes ch ON ch.workspace_id=w.id
        WHERE w.org_id IS NOT NULL AND p.payload IS NOT NULL
        AND p.action_key LIKE ch.id || ':' || ch.revision || ':%'
        AND ch.state!='SUPERSEDED' """)

import json
import sqlite3
import time

import pytest

from app import assets, db
from scripts.data_ops import copy_database, retention
from test_workflow import approve, tick


def test_backup_and_isolated_restore_preserve_committed_wal(client, tmp_path):
    approve(client)
    tick(client)
    backup = tmp_path / "backup.sqlite"
    restore = tmp_path / "restore.sqlite"
    assert copy_database(db.path(), backup)["integrity"] == "ok"
    assert copy_database(backup, restore)["integrity"] == "ok"
    with sqlite3.connect(restore) as c:
        assert c.execute("SELECT count(*) FROM publications WHERE payload IS NOT NULL").fetchone()[0] == 1
        assert c.execute("SELECT count(*) FROM changes WHERE approved_at IS NOT NULL").fetchone()[0] == 1
    with pytest.raises(FileExistsError):
        copy_database(db.path(), restore)


def test_retention_requires_apply_and_preserves_approved_facts(client):
    ch = approve(client)
    tick(client)
    with db.connect(write=True) as c:
        c.execute(
            "UPDATE changes SET state='ENDED',created_at=? WHERE id=?", (time.time() - 100 * 86400, ch["id"])
        )
        before = c.execute("SELECT facts,source_hash FROM changes WHERE id=?", (ch["id"],)).fetchone()
    assert retention(90)["sources"] == 1
    with db.connect() as c:
        assert (
            c.execute("SELECT source FROM changes").fetchone()[0] != "[Source removed under retention policy]"
        )
    assert retention(90, apply=True)["applied"]
    with db.connect() as c:
        row = c.execute("SELECT * FROM changes").fetchone()
        assert row["facts"] == before["facts"] and row["source_hash"] == before["source_hash"]
        assert row["source"] == "[Source removed under retention policy]"
        assert json.loads(row["proposal"]) == {}
        assert "evidence_locations" not in json.loads(row["metrics"])


def test_release_assets_are_content_versioned(client):
    page = client.get("/").text
    assert "/static/app.js?v=" + assets.version() in page
    assert "/static/styles.css?v=" + assets.version() in page

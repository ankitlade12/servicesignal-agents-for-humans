import json

from app import db, worker
from test_workflow import approve, action, data, tick


def test_monitoring_detects_drift_without_overwriting(client):
    approve(client)
    tick(client)
    with db.connect(write=True) as c:
        row = c.execute("SELECT payload FROM publications").fetchone()
        payload = json.loads(row[0])
        payload["facts"]["room"] = "Unexpected room"
        c.execute("UPDATE publications SET payload=?", (json.dumps(payload),))
        c.execute("UPDATE jobs SET due_at=0 WHERE kind='verify'")
    job = worker.claim()
    assert job["kind"] == "verify"
    worker.process(job, client)
    assert action(client, "page")["state"] == "NEEDS_OWNER"
    assert data(client)["publication"]["facts"]["room"] == "Unexpected room"


def test_monitoring_reschedules_without_model_calls(client):
    approve(client)
    tick(client)
    with db.connect(write=True) as c:
        c.execute("UPDATE jobs SET due_at=0 WHERE kind='verify'")
    tick(client)
    assert data(client)["publication_version"] == 1
    with db.connect() as c:
        assert c.execute("SELECT state FROM jobs WHERE kind='verify'").fetchone()[0] == "QUEUED"
        assert c.execute("SELECT model_calls FROM workspaces").fetchone()[0] == 0

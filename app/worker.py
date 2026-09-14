"""Durable SQLite jobs with expiring claims and HTTP publication/read-back."""

import json
import logging
import os
import secrets
import time

import httpx

from . import db
from .domain import digest, fact_payload, visible_facts
from .notices import FactParser

log = logging.getLogger("servicesignal.worker")


def claim():
    with db.connect(write=True) as c:
        c.execute("INSERT OR REPLACE INTO settings VALUES('worker_heartbeat',?)", (str(time.time()),))
        c.execute("UPDATE jobs SET state='QUEUED' WHERE state='RUNNING' AND lease_until<?", (time.time(),))
        row = c.execute(
            """SELECT j.* FROM jobs j JOIN changes ch ON ch.id=j.change_id
            JOIN workspaces w ON w.id=ch.workspace_id
            WHERE j.state='QUEUED' AND j.due_at<=?+w.clock_offset
            ORDER BY CASE j.kind WHEN 'expire' THEN 0 WHEN 'remind' THEN 1 WHEN 'publish' THEN 2 ELSE 3 END, j.due_at LIMIT 1""",
            (time.time(),),
        ).fetchone()
        if not row:
            return None
        c.execute(
            "UPDATE jobs SET state='RUNNING',lease_until=?,attempts=attempts+1 WHERE id=?",
            (time.time() + 45, row["id"]),
        )
        return dict(c.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone())


def process(job, client=None):
    with db.connect() as c:
        row = c.execute("SELECT * FROM changes WHERE id=?", (job["change_id"],)).fetchone()
        if not row:
            return
        change = dict(row)
        ws = dict(c.execute("SELECT * FROM workspaces WHERE id=?", (change["workspace_id"],)).fetchone())
        key = c.execute("SELECT value FROM settings WHERE key='publisher_key'").fetchone()[0]
    if change["revision"] != job["revision"] or change["state"] == "SUPERSEDED":
        with db.connect(write=True) as c:
            c.execute("UPDATE jobs SET state='CANCELED' WHERE id=?", (job["id"],))
        return
    if job["kind"] == "remind":
        with db.connect(write=True) as c:
            c.execute(
                "UPDATE changes SET state='RECONFIRMATION_DUE' WHERE id=? AND state='MONITORING'",
                (change["id"],),
            )
            db.event(
                c,
                ws["id"],
                change["id"],
                "RECONFIRMATION_DUE",
                "What happens after the last affected session? Confirm a new arrangement; the previous venue will not be restored automatically.",
            )
            c.execute("UPDATE jobs SET state='DONE' WHERE id=?", (job["id"],))
        return
    client_owned = client is None
    client = client or httpx.Client(
        base_url=os.getenv("PUBLISHER_ORIGIN", "http://127.0.0.1:8000"), timeout=10, follow_redirects=False
    )
    mismatch = None
    observations = {}
    try:
        # The publisher reconciles duplicate action keys before attempting another write.
        if job["kind"] != "verify":
            response = client.post(f"/internal/publish/{job['id']}", headers={"X-Publisher-Key": key})
            response.raise_for_status()
        expected = fact_payload(
            json.loads(change["facts"]),
            ws["public_id"],
            change["revision"],
            change["approved_at"],
            job["kind"] == "expire",
            db.approved_context(change, ws),
        )
        languages = (
            json.loads(change["plan_context"]).get("languages", ["en"])
            if change.get("plan_context")
            else ["en"]
        )
        english_facts = None
        mismatch = None
        for language in languages:
            page = client.get(
                f"/notices/{ws['public_id']}?verification={job['id']}&lang={language}"
                + (f"&change={change['id']}" if ws["org_id"] else ""),
                headers={"Cache-Control": "no-cache"},
            )
            page.raise_for_status()
            parsed = FactParser()
            parsed.feed(page.text)
            observations[language] = {
                "facts": parsed.facts,
                "sha256": digest(parsed.facts),
                "observed_at": time.time(),
            }
            expected_fields = visible_facts(expected, language)
            differences = [key for key in expected_fields if parsed.facts.get(key) != expected_fields[key]]
            if differences or parsed.facts.keys() != expected_fields.keys():
                mismatch = f"{language}: " + ", ".join(differences or ["unexpected fields"])
                raise ValueError("Published fields differ from the approved plan.")
            if language == "en":
                english_facts = parsed.facts
        with db.connect(write=True) as c:
            current = c.execute("SELECT revision,state FROM changes WHERE id=?", (change["id"],)).fetchone()
            if not current or current["revision"] != job["revision"] or current["state"] == "SUPERSEDED":
                c.execute("UPDATE jobs SET state='CANCELED' WHERE id=?", (job["id"],))
                return
            now = db.now(c, ws["id"])
            c.execute(
                """UPDATE actions SET state='VERIFIED',detail=?,verified_at=?,observed_hash=?,
                observed_payload=?,attempts=? WHERE change_id=? AND revision=? AND destination='page'""",
                (
                    "Fresh HTTP reads matched every approved visible field in " + ", ".join(languages) + "."
                    if job["kind"] != "expire"
                    else "Expiration notice independently checked; future arrangements remain unconfirmed.",
                    now,
                    digest(english_facts),
                    json.dumps(english_facts),
                    job["attempts"],
                    change["id"],
                    job["revision"],
                ),
            )
            c.execute(
                "UPDATE actions SET locale_evidence=? WHERE change_id=? AND revision=? AND destination='page'",
                (json.dumps(observations), change["id"], job["revision"]),
            )
            if job["kind"] != "verify":
                c.execute(
                    "UPDATE actions SET state='REPLACEMENT_READY',detail='Printable notice is available. Distribution has not been verified.' WHERE change_id=? AND revision=? AND destination='flyer'",
                    (change["id"], job["revision"]),
                )
            if job["kind"] == "expire":
                c.execute("UPDATE changes SET state='ENDED' WHERE id=?", (change["id"],))
                c.execute(
                    "UPDATE actions SET state='NEEDS_OWNER',detail='Temporary arrangement ended. Replace or reconfirm this copy.' WHERE change_id=? AND destination IN ('partner','print')",
                    (change["id"],),
                )
                c.execute(
                    "UPDATE jobs SET state='CANCELED' WHERE change_id=? AND kind IN ('publish','remind','verify') AND state!='DONE'",
                    (change["id"],),
                )
            else:
                c.execute(
                    "UPDATE changes SET state='MONITORING' WHERE id=? AND state='APPLYING'", (change["id"],)
                )
            if job["kind"] == "verify":
                c.execute(
                    "UPDATE jobs SET state='QUEUED',due_at=?,attempts=0 WHERE id=?", (now + 900, job["id"])
                )
            else:
                c.execute("UPDATE jobs SET state='DONE' WHERE id=?", (job["id"],))
            if job["kind"] == "publish":
                c.execute(
                    "INSERT OR IGNORE INTO jobs(id,change_id,revision,kind,due_at) VALUES(?,?,?,'verify',?)",
                    (secrets.token_urlsafe(16), change["id"], job["revision"], now + 900),
                )
            db.event(
                c,
                ws["id"],
                change["id"],
                "VERIFIED",
                "Worker independently retrieved the resident page and compared its visible facts to the approved revision.",
            )
    except Exception as error:
        conflict = isinstance(error, ValueError) or (
            isinstance(error, httpx.HTTPStatusError)
            and error.response.status_code in (401, 403, 404, 409, 422)
        )
        exhausted = job["attempts"] >= 4
        state = "NEEDS_OWNER" if conflict or exhausted else "RETRYABLE_FAILURE"
        detail = (
            "Publication or verification needs owner review."
            if conflict
            else "Publication could not be verified. Retrying with a durable job."
            if not exhausted
            else "Retries exhausted. Use Retry after checking the server."
        )
        if mismatch:
            detail = "Visible fields differ from approval: " + mismatch + ". Owner review required."
        log.warning("job=%s category=%s", job["id"], type(error).__name__)
        with db.connect(write=True) as c:
            c.execute(
                "UPDATE actions SET state=?,detail=?,attempts=? WHERE change_id=? AND revision=? AND destination='page' AND state!='CANCELED'",
                (state, detail, job["attempts"], change["id"], job["revision"]),
            )
            if observations:
                c.execute(
                    "UPDATE actions SET locale_evidence=? WHERE change_id=? AND revision=? AND destination='page' AND state!='CANCELED'",
                    (json.dumps(observations), change["id"], job["revision"]),
                )
            due = db.now(c, ws["id"]) + (15, 60, 300, 300)[min(job["attempts"] - 1, 3)]
            c.execute(
                "UPDATE jobs SET state=?,due_at=? WHERE id=? AND state!='CANCELED'",
                ("FAILED" if conflict or exhausted else "QUEUED", due, job["id"]),
            )
            db.event(c, ws["id"], change["id"], state, detail)
    finally:
        if client_owned:
            client.close()


def run():
    db.init()
    logging.basicConfig(level=logging.INFO)
    log.info("Durable worker started")
    while True:
        try:
            job = claim()
            if job:
                process(job)
            if not job:
                time.sleep(1)
        except KeyboardInterrupt:
            return
        except Exception:
            log.exception("Worker iteration failed")
            time.sleep(2)


if __name__ == "__main__":
    run()

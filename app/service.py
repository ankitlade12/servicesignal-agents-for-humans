import json
import secrets
import time

from fastapi import HTTPException

from . import db
from .domain import FALLBACK, canonical, digest, fact_payload

DESTINATIONS = ("page", "flyer", "partner", "print")


def get_change(c, workspace_id, change_id):
    row = c.execute(
        "SELECT * FROM changes WHERE id=? AND workspace_id=?", (change_id, workspace_id)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Change not found in this workspace.")
    return dict(row)


def plan_for(change, public_id):
    plan = {
        "change_id": change["id"],
        "revision": change["revision"],
        "facts": json.loads(change["facts"]),
        "public_id": public_id,
        "expected_version": change["expected_version"],
        "destinations": list(DESTINATIONS),
        "expiration_notice": FALLBACK,
    }
    if change.get("plan_context"):
        plan["context"] = json.loads(change["plan_context"])
    return plan


def serialize(c, change):
    change = dict(change)
    for key in ("proposal", "facts", "metrics", "created_by", "confirmed_by", "approved_by", "plan_context"):
        change[key] = json.loads(change[key]) if change[key] else None
    change["actions"] = [
        dict(r)
        for r in c.execute(
            "SELECT * FROM actions WHERE change_id=? AND revision=? ORDER BY rowid",
            (change["id"], change["revision"]),
        )
    ]
    return change


def review(workspace_id, change_id, revision, facts, actor=None):
    with db.connect(write=True) as c:
        change = get_change(c, workspace_id, change_id)
        if revision != change["revision"] or change["state"] not in (
            "DRAFT",
            "NEEDS_CLARIFICATION",
            "READY_FOR_REVIEW",
        ):
            raise HTTPException(409, "This revision is no longer editable. Refresh or start a new change.")
        context = db.program(c.execute("SELECT * FROM workspaces WHERE id=?", (workspace_id,)).fetchone())
        if facts.program != context["name"] or facts.timezone != context["timezone"]:
            raise HTTPException(422, "Facts must match this workspace's confirmed program and timezone.")
        if any(d.weekday() not in context["weekdays"] for d in facts.dates):
            raise HTTPException(422, "Select dates on the program's confirmed recurring weekdays.")
        if facts.expires_at() <= db.now(c, workspace_id):
            raise HTTPException(
                422, "Those sessions have ended. Choose future sessions or reset the demo clock."
            )
        pub_version = c.execute(
            "SELECT version FROM publications WHERE workspace_id=?", (workspace_id,)
        ).fetchone()[0]
        ws = c.execute("SELECT * FROM workspaces WHERE id=?", (workspace_id,)).fetchone()
        plan_context = canonical(
            {
                "program": context,
                "inventory": db.inventory(ws),
                "languages": ["en", "es"] if context.get("spanish_enabled") else ["en"],
            }
        )
        change.update(
            plan_context=plan_context,
            revision=revision + 1,
            facts=canonical(facts.model_dump(mode="json")),
            expected_version=pub_version,
        )
        c.execute("UPDATE changes SET plan_context=? WHERE id=?", (plan_context, change_id))
        public_id = c.execute("SELECT public_id FROM workspaces WHERE id=?", (workspace_id,)).fetchone()[0]
        plan_hash = digest(plan_for(change, public_id))
        c.execute(
            """UPDATE changes SET revision=?,facts=?,state='READY_FOR_REVIEW',plan_hash=?,
                     expected_version=?,expires_at=? WHERE id=?""",
            (change["revision"], change["facts"], plan_hash, pub_version, facts.expires_at(), change_id),
        )
        if actor:
            c.execute("UPDATE changes SET confirmed_by=? WHERE id=?", (canonical(actor), change_id))
        db.event(
            c,
            workspace_id,
            change_id,
            "FACTS_CONFIRMED",
            f"{actor['name'] if actor else 'Demo coordinator'} confirmed exact dates, venue, hours, and program scope.",
        )
        return serialize(c, get_change(c, workspace_id, change_id))


def approve(workspace_id, change_id, revision, plan_hash, replace_current=False, actor=None):
    with db.connect(write=True) as c:
        change = get_change(c, workspace_id, change_id)
        ws = c.execute("SELECT * FROM workspaces WHERE id=?", (workspace_id,)).fetchone()
        if ws["org_id"]:
            user = c.execute(
                "SELECT id FROM users WHERE id=? AND org_id=? AND active=1 AND role='owner'",
                ((actor or {}).get("id"), ws["org_id"]),
            ).fetchone()
            if not user:
                raise HTTPException(403, "An active organization owner must approve publication.")
        if change["revision"] != revision or change["plan_hash"] != plan_hash:
            raise HTTPException(409, "The plan changed. Review the latest version before approving.")
        # Repeated requests for exactly the same approval do not enqueue more writes.
        if change["approved_at"] and change["state"] in (
            "APPLYING",
            "MONITORING",
            "RECONFIRMATION_DUE",
            "ENDED",
        ):
            return serialize(c, change)
        if change.get("plan_context") and json.loads(change["plan_context"])["program"] != db.program(ws):
            raise HTTPException(409, "The program baseline changed. Reconfirm the facts before approving.")
        if change["state"] != "READY_FOR_REVIEW" or digest(plan_for(change, ws["public_id"])) != plan_hash:
            raise HTTPException(409, "Confirm the facts before approving this exact plan.")
        version = c.execute(
            "SELECT version FROM publications WHERE workspace_id=?", (workspace_id,)
        ).fetchone()[0]
        if version != change["expected_version"]:
            raise HTTPException(409, "The destination changed. Reconfirm the facts to refresh the plan.")
        current = c.execute(
            "SELECT id FROM changes WHERE workspace_id=? AND id!=? AND approved_at IS NOT NULL AND state!='SUPERSEDED'",
            (workspace_id, change_id),
        ).fetchall()
        if current and not replace_current:
            raise HTTPException(
                409, "Confirm that this plan replaces the previous notice and its affected sessions."
            )
        now = db.now(c, workspace_id)
        if change["expires_at"] <= now:
            raise HTTPException(422, "The affected sessions have ended. Create a new plan.")
        for previous in current:
            c.execute("UPDATE changes SET state='SUPERSEDED' WHERE id=?", (previous[0],))
            c.execute("UPDATE jobs SET state='CANCELED' WHERE change_id=? AND state!='DONE'", (previous[0],))
            c.execute(
                "UPDATE actions SET state='CANCELED',detail='Superseded by a new approved notice.' WHERE change_id=?",
                (previous[0],),
            )
        c.execute("UPDATE changes SET state='APPLYING',approved_at=? WHERE id=?", (now, change_id))
        if actor:
            c.execute("UPDATE changes SET approved_by=? WHERE id=?", (canonical(actor), change_id))
        for dest in DESTINATIONS:
            state = {"page": "QUEUED", "flyer": "QUEUED", "partner": "NEEDS_OWNER", "print": "NEEDS_OWNER"}[
                dest
            ]
            detail = {
                "page": "Waiting for publication and HTTP read-back.",
                "flyer": "Waiting for approved publication.",
                "partner": (
                    "Partner owner must publish the correction; no external message sent."
                    if ws["org_id"]
                    else "Simulated partner: awaiting editor publication. No external message sent."
                ),
                "print": "A person must replace printed copies.",
            }[dest]
            c.execute(
                "INSERT INTO actions(id,change_id,revision,destination,state,detail) VALUES(?,?,?,?,?,?)",
                (secrets.token_urlsafe(16), change_id, revision, dest, state, detail),
            )
        for kind, due in (
            ("publish", now),
            ("remind", max(now, change["expires_at"] - 86400)),
            ("expire", change["expires_at"]),
        ):
            c.execute(
                "INSERT INTO jobs(id,change_id,revision,kind,due_at) VALUES(?,?,?,?,?)",
                (secrets.token_urlsafe(16), change_id, revision, kind, due),
            )
        db.event(
            c,
            workspace_id,
            change_id,
            "APPROVED",
            f"Revision {revision} approved for the registered page, flyer, and expiration notice. Partner and print remain manual.",
        )
        return serialize(c, get_change(c, workspace_id, change_id))


def publish_job(job_id, key):
    """Publisher boundary accepts a job identifier, never model-supplied facts or URLs."""
    with db.connect(write=True) as c:
        saved = c.execute("SELECT value FROM settings WHERE key='publisher_key'").fetchone()[0]
        if not secrets.compare_digest(key, saved):
            raise HTTPException(403, "Publisher authorization required.")
        row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Job not found.")
        job = dict(row)
        change = dict(c.execute("SELECT * FROM changes WHERE id=?", (job["change_id"],)).fetchone())
        if (
            job["kind"] not in ("publish", "expire")
            or job["state"] != "RUNNING"
            or job["lease_until"] < time.time()
        ):
            raise HTTPException(409, "A current publication job lease is required.")
        if (
            not change["approved_at"]
            or change["revision"] != job["revision"]
            or change["state"] == "SUPERSEDED"
        ):
            raise HTTPException(409, "Publication approval is stale.")
        ws = c.execute("SELECT * FROM workspaces WHERE id=?", (change["workspace_id"],)).fetchone()
        if digest(plan_for(change, ws["public_id"])) != change["plan_hash"]:
            raise HTTPException(409, "Approved facts or destinations changed.")
        pub = c.execute("SELECT * FROM publications WHERE workspace_id=?", (ws["id"],)).fetchone()
        expired = job["kind"] == "expire"
        action_key = f"{change['id']}:{change['revision']}:{job['kind']}"
        if pub["action_key"] == action_key:
            return {
                "version": pub["version"],
                "public_id": ws["public_id"],
                "payload": json.loads(pub["payload"]),
            }
        if not expired and db.now(c, ws["id"]) >= change["expires_at"]:
            raise HTTPException(409, "The temporary arrangement ended before publication.")
        if expired:
            if db.now(c, ws["id"]) < change["expires_at"]:
                raise HTTPException(409, "The temporary arrangement has not ended.")
            # Expiry may replace either the approved base or this change's own publication only.
            allowed = (None, f"{change['id']}:{change['revision']}:publish")
            if pub["action_key"] not in allowed and pub["version"] != change["expected_version"]:
                raise HTTPException(409, "A newer notice prevents this expiration write.")
        elif pub["version"] != change["expected_version"]:
            raise HTTPException(409, "Destination version conflict.")
        payload = fact_payload(
            json.loads(change["facts"]),
            ws["public_id"],
            change["revision"],
            change["approved_at"],
            expired,
            db.approved_context(change, ws),
        )
        payload["demo"] = not bool(ws["org_id"])
        c.execute(
            "UPDATE publications SET version=version+1,payload=?,action_key=? WHERE workspace_id=?",
            (canonical(payload), action_key, ws["id"]),
        )
        db.event(
            c,
            ws["id"],
            change["id"],
            "EXPIRED_PUBLISHED" if expired else "PUBLISHED",
            "Controlled website stored the approved notice. Independent read-back is pending.",
        )
        return {"version": pub["version"] + 1, "public_id": ws["public_id"], "payload": payload}

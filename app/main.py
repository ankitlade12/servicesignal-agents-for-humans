import hashlib
import json
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from . import agent, db, service
from .domain import AMBIGUOUS_EXAMPLE, EXAMPLE, FALLBACK, PROGRAM, Facts, canonical, digest
from .notices import flyer_pdf, qr_svg, render_notice

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("servicesignal")


@asynccontextmanager
async def lifespan(app):
    db.init()
    yield


app = FastAPI(title="ServiceSignal", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.middleware("http")
async def security_headers(request, call_next):
    if request.method in ("POST", "PUT", "DELETE", "PATCH") and request.url.path.startswith("/api/"):
        if request.headers.get("x-servicesignal") != "1":
            return JSONResponse({"detail": "Same-origin application request required."}, status_code=403)
        origin = request.headers.get("origin")
        allowed = {
            str(request.base_url).rstrip("/"),
            os.getenv("PUBLIC_ORIGIN", "http://localhost:8000").rstrip("/"),
        }
        if origin and origin not in allowed:
            return JSONResponse({"detail": "Cross-origin write rejected."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if not request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def workspace(request: Request):
    token = request.cookies.get("servicesignal_session", "")
    hashed = hashlib.sha256(token.encode()).hexdigest()
    with db.connect() as c:
        row = c.execute(
            "SELECT * FROM workspaces WHERE token_hash=? AND created_at>?", (hashed, time.time() - 7 * 86400)
        ).fetchone()
    if not row:
        raise HTTPException(401, "Start an isolated demo workspace first.")
    return dict(row)


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Intake(StrictBody):
    source: str = Field(min_length=10, max_length=6000)


class Review(StrictBody):
    revision: int
    facts: Facts
    confirmed: bool


class Approval(StrictBody):
    revision: int
    plan_hash: str
    replace_current: bool = False


class Clock(StrictBody):
    change_id: str
    stage: str


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(ROOT / "static/index.html")


@app.get("/api/health")
def health():
    with db.connect() as c:
        c.execute("SELECT 1")
    return {
        "status": "ok",
        "provider": agent.provider(),
        "model_id": os.getenv("AGENT_MODEL_ID") or None,
        "demo": True,
        "sdk": "Strands Agents",
        "version": "0.1.0",
    }


@app.post("/api/session")
def start_session(request: Request, response: Response):
    try:
        ws = workspace(request)
        return {"public_id": ws["public_id"]}
    except HTTPException:
        pass
    with db.connect(write=True) as c:
        # Bound anonymous demo storage. Expired sessions and their private data are removed.
        c.execute("DELETE FROM workspaces WHERE created_at<?", (time.time() - 7 * 86400,))
        if c.execute("SELECT count(*) FROM workspaces").fetchone()[0] >= 1000:
            raise HTTPException(429, "The demo is at capacity. Please try again later.")
        token, workspace_id, public_id = (
            secrets.token_urlsafe(32),
            secrets.token_urlsafe(16),
            secrets.token_urlsafe(18),
        )
        c.execute(
            "INSERT INTO workspaces(id,token_hash,public_id,created_at) VALUES(?,?,?,?)",
            (workspace_id, hashlib.sha256(token.encode()).hexdigest(), public_id, time.time()),
        )
        c.execute("INSERT INTO publications(workspace_id) VALUES(?)", (workspace_id,))
        db.event(
            c,
            workspace_id,
            None,
            "WORKSPACE_CREATED",
            "Isolated fictional workspace created. No real services are connected.",
        )
    response.set_cookie(
        "servicesignal_session",
        token,
        httponly=True,
        samesite="strict",
        max_age=7 * 86400,
        secure=os.getenv("COOKIE_SECURE", "0") == "1",
    )
    return {"public_id": public_id}


@app.get("/api/workspace")
def dashboard(ws=Depends(workspace)):
    with db.connect() as c:
        changes = [
            service.serialize(c, row)
            for row in c.execute(
                "SELECT * FROM changes WHERE workspace_id=? ORDER BY created_at DESC", (ws["id"],)
            ).fetchall()
        ]
        events = [
            dict(row)
            for row in c.execute(
                "SELECT * FROM events WHERE workspace_id=? ORDER BY id DESC LIMIT 100", (ws["id"],)
            )
        ]
        pub = dict(c.execute("SELECT * FROM publications WHERE workspace_id=?", (ws["id"],)).fetchone())
        current_time = db.now(c, ws["id"])
    return {
        "program": PROGRAM,
        "public_id": ws["public_id"],
        "changes": changes,
        "events": events,
        "publication": json.loads(pub["payload"]) if pub["payload"] else None,
        "publication_version": pub["version"],
        "provider": agent.provider(),
        "now": current_time,
        "clock_offset": ws["clock_offset"],
        "example": EXAMPLE,
        "ambiguous_example": AMBIGUOUS_EXAMPLE,
        "fallback": FALLBACK,
    }


@app.post("/api/changes")
async def intake(body: Intake, ws=Depends(workspace)):
    source = body.source.strip()
    source_hash = digest(source)
    change_id = secrets.token_urlsafe(16)
    with db.connect(write=True) as c:
        existing = c.execute(
            "SELECT * FROM changes WHERE workspace_id=? AND source_hash=?", (ws["id"], source_hash)
        ).fetchone()
        if existing:
            return service.serialize(c, existing)
        if c.execute("SELECT count(*) FROM changes WHERE workspace_id=?", (ws["id"],)).fetchone()[0] >= 30:
            raise HTTPException(429, "This demo supports 30 changes per workspace. Reset to start again.")
        if agent.provider() != "fixture":
            day = datetime.now(timezone.utc).date().isoformat()
            c.execute("INSERT OR IGNORE INTO usage_days VALUES(?,0)", (day,))
            used = c.execute("SELECT calls FROM usage_days WHERE day=?", (day,)).fetchone()[0]
            workspace_used = c.execute(
                "SELECT model_calls FROM workspaces WHERE id=?", (ws["id"],)
            ).fetchone()[0]
            if used >= int(os.getenv("DAILY_MODEL_LIMIT", "100")) or workspace_used >= int(
                os.getenv("WORKSPACE_MODEL_LIMIT", "20")
            ):
                raise HTTPException(
                    429, "Live model budget reached. Existing approved notices remain available."
                )
            c.execute("UPDATE usage_days SET calls=calls+1 WHERE day=?", (day,))
            c.execute("UPDATE workspaces SET model_calls=model_calls+1 WHERE id=?", (ws["id"],))
        c.execute(
            "INSERT INTO changes(id,workspace_id,source,source_hash,proposal,state,created_at,mode) VALUES(?,?,?,?,?,?,?,?)",
            (change_id, ws["id"], source, source_hash, "{}", "INTERPRETING", time.time(), agent.provider()),
        )
    try:
        proposal, metrics = await agent.interpret(source)
    except Exception as error:
        log.warning("Interpretation failed change=%s category=%s", change_id, type(error).__name__)
        with db.connect(write=True) as c:
            c.execute(
                "UPDATE changes SET state='MODEL_ERROR',metrics=? WHERE id=?",
                (canonical({"error_category": type(error).__name__, "live": False}), change_id),
            )
            db.event(
                c,
                ws["id"],
                change_id,
                "MODEL_ERROR",
                "Model execution failed. Review server configuration; no output was published. Manual fact entry remains available.",
            )
        raise HTTPException(
            503,
            "The live agent could not finish. No changes were published. Check model access or open the saved draft to enter facts manually.",
        ) from None
    state = "NEEDS_CLARIFICATION" if proposal.questions else "DRAFT"
    with db.connect(write=True) as c:
        c.execute(
            "UPDATE changes SET proposal=?,state=?,metrics=? WHERE id=?",
            (canonical(proposal.model_dump()), state, canonical(metrics), change_id),
        )
        db.event(
            c,
            ws["id"],
            change_id,
            "INTERPRETED",
            "Live Strands proposal saved for review."
            if metrics["live"]
            else "Deterministic guided example saved. No model call was made.",
        )
        return service.serialize(c, service.get_change(c, ws["id"], change_id))


@app.post("/api/changes/{change_id}/review")
def review(change_id: str, body: Review, ws=Depends(workspace)):
    if not body.confirmed:
        raise HTTPException(422, "Confirm that these are the correct operational facts.")
    # A crashed interpretation can be recovered through explicit manual confirmation.
    with db.connect(write=True) as c:
        change = service.get_change(c, ws["id"], change_id)
        if change["state"] == "MODEL_ERROR" or (
            change["state"] == "INTERPRETING" and time.time() - change["created_at"] > 100
        ):
            c.execute("UPDATE changes SET state='DRAFT' WHERE id=?", (change_id,))
    return service.review(ws["id"], change_id, body.revision, body.facts)


@app.post("/api/changes/{change_id}/approve")
def approve(change_id: str, body: Approval, ws=Depends(workspace)):
    return service.approve(ws["id"], change_id, body.revision, body.plan_hash, body.replace_current)


@app.post("/api/changes/{change_id}/retry")
def retry(change_id: str, ws=Depends(workspace)):
    with db.connect(write=True) as c:
        ch = service.get_change(c, ws["id"], change_id)
        if not ch["approved_at"] or ch["state"] == "SUPERSEDED":
            raise HTTPException(409, "A current approved change is required.")
        kind = "expire" if db.now(c, ws["id"]) >= ch["expires_at"] else "publish"
        if kind == "publish":
            initial = c.execute(
                "SELECT state FROM jobs WHERE change_id=? AND kind='publish'", (change_id,)
            ).fetchone()
            if initial and initial[0] == "DONE":
                kind = "verify"
        result = c.execute(
            "UPDATE jobs SET state='QUEUED',attempts=0,due_at=? WHERE change_id=? AND revision=? AND kind=? AND state IN ('FAILED','QUEUED')",
            (db.now(c, ws["id"]), change_id, ch["revision"], kind),
        )
        if not result.rowcount:
            raise HTTPException(409, "There is no failed publication to retry.")
        c.execute(
            "UPDATE actions SET state='QUEUED',detail='A retry has been requested.' WHERE change_id=? AND destination='page'",
            (change_id,),
        )
        db.event(
            c, ws["id"], change_id, "RETRY_REQUESTED", "Coordinator requested a bounded publication retry."
        )
    return {"queued": True}


@app.post("/api/changes/{change_id}/partner/{action}")
def partner(change_id: str, action: str, ws=Depends(workspace)):
    if action not in ("acknowledge", "publish", "fail"):
        raise HTTPException(422, "Unknown simulator action.")
    with db.connect(write=True) as c:
        ch = service.get_change(c, ws["id"], change_id)
        if not ch["approved_at"] or ch["state"] in ("SUPERSEDED", "ENDED"):
            raise HTTPException(409, "The partner needs a current approved notice.")
        state, detail = {
            "acknowledge": (
                "ACKNOWLEDGED",
                "Simulated editor acknowledged receipt. This does not verify publication.",
            ),
            "publish": (
                "SIMULATED_PUBLISHED",
                "Simulator stored the approved listing. This is not a live directory integration.",
            ),
            "fail": (
                "NEEDS_OWNER",
                "Simulated partner declined the correction. The owned website remains independent.",
            ),
        }[action]
        c.execute(
            "UPDATE actions SET state=?,detail=?,observed_payload=? WHERE change_id=? AND destination='partner'",
            (state, detail, ch["facts"] if action == "publish" else None, change_id),
        )
        db.event(c, ws["id"], change_id, "PARTNER_SIMULATION", detail)
    return {"state": state}


@app.post("/api/changes/{change_id}/print-confirm")
def print_confirm(change_id: str, ws=Depends(workspace)):
    with db.connect(write=True) as c:
        ch = service.get_change(c, ws["id"], change_id)
        if not ch["approved_at"] or ch["state"] in ("SUPERSEDED", "ENDED"):
            raise HTTPException(409, "A current approved notice is required.")
        ready = c.execute(
            "SELECT state FROM actions WHERE change_id=? AND destination='flyer'", (change_id,)
        ).fetchone()
        if not ready or ready[0] != "REPLACEMENT_READY":
            raise HTTPException(409, "Wait until the printable replacement is ready.")
        c.execute(
            "UPDATE actions SET state='MANUALLY_CONFIRMED',detail='Demo coordinator reports replacing printed copies. Not digitally verified.' WHERE change_id=? AND destination='print'",
            (change_id,),
        )
        db.event(
            c, ws["id"], change_id, "MANUALLY_CONFIRMED", "Demo coordinator reports replacing printed copies."
        )
    return {"confirmed": True}


@app.post("/api/demo/clock")
def advance_clock(body: Clock, ws=Depends(workspace)):
    if body.stage not in ("reminder", "expiry"):
        raise HTTPException(422, "Choose reminder or expiry.")
    with db.connect(write=True) as c:
        ch = service.get_change(c, ws["id"], body.change_id)
        if not ch["approved_at"] or ch["state"] in ("SUPERSEDED", "ENDED"):
            raise HTTPException(409, "Choose a current approved change.")
        target = ch["expires_at"] + (2 if body.stage == "expiry" else -86400 + 2)
        offset = max(ws["clock_offset"], target - time.time())
        c.execute("UPDATE workspaces SET clock_offset=? WHERE id=?", (offset, ws["id"]))
        db.event(
            c,
            ws["id"],
            ch["id"],
            "DEMO_CLOCK",
            f"This isolated workspace advanced to {body.stage}. Real clocks were not changed.",
        )
    return {"advanced": True}


@app.post("/api/demo/reset")
def reset(response: Response, ws=Depends(workspace)):
    with db.connect(write=True) as c:
        c.execute("DELETE FROM workspaces WHERE id=?", (ws["id"],))
    response.delete_cookie("servicesignal_session")
    return {"reset": True}


@app.get("/api/export")
def export(ws=Depends(workspace)):
    data = dashboard(ws)
    return Response(
        canonical(data),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="servicesignal-evidence.json"'},
    )


@app.post("/internal/publish/{job_id}")
def controlled_publish(job_id: str, x_publisher_key: str = Header(default="")):
    return service.publish_job(job_id, x_publisher_key)


def publication(public_id):
    with db.connect() as c:
        row = c.execute(
            "SELECT p.payload FROM publications p JOIN workspaces w ON p.workspace_id=w.id WHERE w.public_id=? AND w.created_at>?",
            (public_id, time.time() - 7 * 86400),
        ).fetchone()
    if not row:
        raise HTTPException(404, "This demo notice is unavailable or has been reset.")
    return json.loads(row[0]) if row[0] else None


@app.get("/notices/{public_id}", response_class=HTMLResponse)
def notice(public_id: str):
    return render_notice(publication(public_id), public_id)


def public_url(public_id):
    return os.getenv("PUBLIC_ORIGIN", "http://localhost:8000").rstrip("/") + "/notices/" + public_id


@app.get("/notices/{public_id}/qr.svg")
def qr(public_id: str):
    publication(public_id)
    return Response(qr_svg(public_url(public_id)), media_type="image/svg+xml")


@app.get("/notices/{public_id}/flyer.pdf")
def flyer(public_id: str):
    payload = publication(public_id)
    if not payload:
        raise HTTPException(404, "Approve and publish a notice before downloading a flyer.")
    return Response(
        flyer_pdf(payload, public_url(public_id)),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="digital-basics-notice.pdf"'},
    )

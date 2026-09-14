import asyncio
import hashlib
import json
import logging
import os
import secrets
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from . import accounts, agent, assets, db, service
from .domain import AMBIGUOUS_EXAMPLE, EXAMPLE, FALLBACK, Facts, Program, canonical, digest
from .notices import flyer_pdf, qr_svg, render_notice

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("servicesignal")


@asynccontextmanager
async def lifespan(app):
    db.init()
    yield


app = FastAPI(title="ServiceSignal", version="0.1.0", lifespan=lifespan)
app.include_router(accounts.router)
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
    if accounts.pilot_mode():
        return accounts.scoped_workspace(request)
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
    document_id: str | None = Field(default=None, max_length=100)


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
    page = (ROOT / "static/index.html").read_text()
    stamp = assets.version()
    for name in ("app.js", "styles.css", "typography.css"):
        page = page.replace("/static/" + name, "/static/" + name + "?v=" + stamp)
    return HTMLResponse(page)


@app.get("/api/health")
def health():
    with db.connect() as c:
        c.execute("SELECT 1")
    return {
        "status": "ok",
        "provider": agent.provider(),
        "model_id": os.getenv("AGENT_MODEL_ID") or None,
        "demo": not accounts.pilot_mode(),
        "sdk": "Strands Agents",
        "version": "0.1.0",
    }


@app.post("/api/session")
def start_session(request: Request, response: Response):
    if accounts.pilot_mode():
        ws = workspace(request)
        return {"public_id": ws["public_id"]}
    try:
        ws = workspace(request)
        return {"public_id": ws["public_id"]}
    except HTTPException:
        pass
    with db.connect(write=True) as c:
        # Bound anonymous demo storage. Expired sessions and their private data are removed.
        c.execute("DELETE FROM workspaces WHERE org_id IS NULL AND created_at<?", (time.time() - 7 * 86400,))
        if c.execute("SELECT count(*) FROM workspaces").fetchone()[0] >= 1000:
            raise HTTPException(429, "The demo is at capacity. Please try again later.")
        token, workspace_id, public_id = (
            secrets.token_urlsafe(32),
            secrets.token_urlsafe(16),
            secrets.token_urlsafe(18),
        )
        c.execute(
            "INSERT INTO workspaces(id,token_hash,public_id,created_at,clock_offset) VALUES(?,?,?,?,?)",
            (
                workspace_id,
                hashlib.sha256(token.encode()).hexdigest(),
                public_id,
                time.time(),
                datetime(2026, 9, 13, 12, tzinfo=timezone.utc).timestamp() - time.time(),
            ),
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
        programs = (
            [
                {"id": r["id"], "name": db.program(r)["name"]}
                for r in c.execute(
                    "SELECT * FROM workspaces WHERE org_id=? ORDER BY created_at", (ws.get("org_id"),)
                )
            ]
            if ws.get("org_id")
            else []
        )
        team = (
            [
                dict(r)
                for r in c.execute(
                    "SELECT id,name,email,role,active FROM users WHERE org_id=?", (ws["org_id"],)
                )
            ]
            if ws.get("actor", {}).get("role") == "owner"
            else []
        )
    return {
        "program": db.program(ws),
        "mode": "pilot" if ws.get("org_id") else "demo",
        "actor": ws.get("actor"),
        "workspace_id": ws["id"],
        "programs": programs,
        "inventory": db.inventory(ws),
        "team": team,
        "public_id": ws["public_id"],
        "changes": changes,
        "events": events,
        "publication": json.loads(pub["payload"]) if pub["payload"] else None,
        "publication_version": pub["version"],
        "provider": agent.provider(),
        "now": current_time,
        "clock_offset": ws["clock_offset"],
        "worker": worker_status(),
        "example": EXAMPLE,
        "ambiguous_example": AMBIGUOUS_EXAMPLE,
        "fallback": FALLBACK,
    }


@app.post("/api/changes")
async def intake(body: Intake, ws=Depends(workspace)):
    if ws.get("org_id") and not db.program(ws).get("configured", True):
        raise HTTPException(409, "An owner must configure and confirm the program baseline first.")
    source = body.source.strip()
    source_hash = digest(source)
    change_id = secrets.token_urlsafe(16)
    with db.connect(write=True) as c:
        context = db.program(c.execute("SELECT * FROM workspaces WHERE id=?", (ws["id"],)).fetchone())
        if body.document_id:
            document = c.execute(
                "SELECT source FROM documents WHERE id=? AND workspace_id=?", (body.document_id, ws["id"])
            ).fetchone()
            if not document or document[0] != source:
                raise HTTPException(
                    422,
                    "The source must match the preserved PDF extraction. Upload again or submit edited text as a new source.",
                )
        existing = c.execute(
            "SELECT * FROM changes WHERE workspace_id=? AND source_hash=?", (ws["id"], source_hash)
        ).fetchone()
        if existing:
            return service.serialize(c, existing)
        if c.execute("SELECT count(*) FROM changes WHERE workspace_id=?", (ws["id"],)).fetchone()[0] >= (
            1000 if ws.get("org_id") else 30
        ):
            raise HTTPException(
                429,
                "This program has reached its change-record limit. Export its history and contact the operator.",
            )
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
        if ws.get("actor"):
            c.execute("UPDATE changes SET created_by=? WHERE id=?", (canonical(ws["actor"]), change_id))
    try:
        proposal, metrics = await agent.interpret(source, context)
    except Exception as error:
        log.warning("Interpretation failed change=%s category=%s", change_id, type(error).__name__)
        with db.connect(write=True) as c:
            c.execute(
                "UPDATE changes SET state='MODEL_ERROR',metrics=? WHERE id=?",
                (
                    canonical(
                        {
                            "error_category": type(error).__name__,
                            "live": False,
                            "document_id": body.document_id,
                        }
                    ),
                    change_id,
                ),
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
    if body.document_id:
        metrics["document_id"] = body.document_id
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
    return service.review(ws["id"], change_id, body.revision, body.facts, ws.get("actor"))


@app.post("/api/changes/{change_id}/approve")
def approve(change_id: str, body: Approval, ws=Depends(workspace)):
    require_workspace_owner(ws)
    return service.approve(
        ws["id"], change_id, body.revision, body.plan_hash, body.replace_current, ws.get("actor")
    )


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
    if ws.get("org_id"):
        raise HTTPException(403, "Partner simulation is available only in demo workspaces.")
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
            "UPDATE actions SET state='MANUALLY_CONFIRMED',detail='Coordinator reports replacing printed copies. Not digitally verified.' WHERE change_id=? AND destination='print'",
            (change_id,),
        )
        db.event(
            c, ws["id"], change_id, "MANUALLY_CONFIRMED", "Coordinator reports replacing printed copies."
        )
    return {"confirmed": True}


@app.post("/api/demo/clock")
def advance_clock(body: Clock, ws=Depends(workspace)):
    if ws.get("org_id"):
        raise HTTPException(403, "Live programs use the real clock.")
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
    if ws.get("org_id"):
        raise HTTPException(403, "Live program history cannot be removed by a demo reset.")
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


def public_workspace(public_id):
    with db.connect() as c:
        row = c.execute(
            "SELECT * FROM workspaces WHERE public_id=? AND (org_id IS NOT NULL OR created_at>?)",
            (public_id, time.time() - 7 * 86400),
        ).fetchone()
    if not row:
        raise HTTPException(404, "This notice is unavailable or has been withdrawn.")
    if row["org_id"] and not db.program(row).get("configured", True):
        raise HTTPException(404, "The organization has not confirmed this program's details.")
    return dict(row)


def publication(public_id):
    ws = public_workspace(public_id)
    with db.connect() as c:
        row = c.execute("SELECT payload FROM publications WHERE workspace_id=?", (ws["id"],)).fetchone()
        now = db.now(c, ws["id"])
    payload = json.loads(row[0]) if row[0] else None
    # Serve only the already-approved fallback after the end, even with a stopped worker.
    # This does not claim that the worker published or verified that transition.
    if payload and not payload["expired"] and Facts.model_validate(payload["facts"]).expires_at() <= now:
        payload["expired"] = True
        payload["message"] = FALLBACK
    return payload


@app.get("/notices/{public_id}", response_class=HTMLResponse)
def notice(public_id: str, lang: Literal["en", "es"] = "en"):
    ws = public_workspace(public_id)
    payload = publication(public_id)
    context = payload.get("program_context", db.program(ws)) if payload else db.program(ws)
    if lang == "es" and not context.get("spanish_enabled"):
        raise HTTPException(404, "Spanish output has not been approved for this notice.")
    return render_notice(payload, public_id, context, demo=not bool(ws.get("org_id")), language=lang)


def public_url(public_id):
    return os.getenv("PUBLIC_ORIGIN", "http://localhost:8000").rstrip("/") + "/notices/" + public_id


@app.get("/notices/{public_id}/qr.svg")
def qr(public_id: str):
    publication(public_id)
    return Response(qr_svg(public_url(public_id)), media_type="image/svg+xml")


@app.get("/notices/{public_id}/flyer.pdf")
def flyer(public_id: str, lang: Literal["en", "es"] = "en"):
    payload = publication(public_id)
    if not payload:
        raise HTTPException(404, "Approve and publish a notice before downloading a flyer.")
    if lang == "es" and not payload.get("program_context", {}).get("spanish_enabled"):
        raise HTTPException(404, "Spanish output has not been approved for this notice.")
    return Response(
        flyer_pdf(payload, public_url(public_id) + ("?lang=es" if lang == "es" else ""), language=lang),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="community-notice.pdf"'},
    )


@app.post("/api/program")
def configure_program(body: Program, ws=Depends(workspace)):
    require_workspace_owner(ws)
    if ws.get("org_id") and body.organization != ws["organization"]:
        raise HTTPException(422, "Use your account's organization name.")
    with db.connect(write=True) as c:
        if (
            not ws.get("org_id")
            and c.execute("SELECT 1 FROM changes WHERE workspace_id=? LIMIT 1", (ws["id"],)).fetchone()
        ):
            raise HTTPException(
                409,
                "Program setup is locked after the first draft to preserve source and approval scope. Reset this demo before configuring another program.",
            )
        if (
            ws.get("org_id")
            and c.execute(
                "SELECT 1 FROM changes WHERE workspace_id=? AND approved_at IS NOT NULL AND plan_context IS NULL AND state!='SUPERSEDED'",
                (ws["id"],),
            ).fetchone()
        ):
            raise HTTPException(
                409, "An older approved plan must be superseded before changing the baseline."
            )
        c.execute("UPDATE workspaces SET program=? WHERE id=?", (canonical(body.model_dump()), ws["id"]))
        db.event(
            c,
            ws["id"],
            None,
            "PROGRAM_CONFIGURED",
            "Organization owner confirmed the program baseline for future changes."
            if ws.get("org_id")
            else "Coordinator confirmed this workspace's program baseline. Demonstration mode remains active.",
        )
    return body


PDF_SLOTS = asyncio.Semaphore(2)


@app.post("/api/documents")
async def upload_document(request: Request, ws=Depends(workspace)):
    if request.headers.get("content-type", "").split(";")[0] != "application/pdf":
        raise HTTPException(415, "Upload a text-based PDF (up to three pages and 5 MB).")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 5 * 1024**2:
            raise HTTPException(413, "PDFs must be no larger than 5 MB.")
    sha = hashlib.sha256(raw).hexdigest()
    with db.connect() as c:
        existing = c.execute(
            "SELECT id,source,pages FROM documents WHERE workspace_id=? AND sha256=?", (ws["id"], sha)
        ).fetchone()
        if existing:
            return dict(existing)
    if PDF_SLOTS.locked():
        raise HTTPException(429, "Document readers are busy. Please try again shortly.")
    async with PDF_SLOTS:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "app.pdf_intake",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=ROOT,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(bytes(raw)), timeout=8)
            result = json.loads(output)
        except (asyncio.TimeoutError, ValueError):
            if process.returncode is None:
                process.kill()
            await process.wait()
            raise HTTPException(
                422, "This PDF could not be read within the document limits. Paste its verified text instead."
            ) from None
        except BaseException:
            if process.returncode is None:
                process.kill()
            await process.wait()
            raise
    if process.returncode or "error" in result:
        raise HTTPException(422, result.get("error", "This PDF could not be read."))
    with db.connect(write=True) as c:
        existing = c.execute(
            "SELECT id,source,pages FROM documents WHERE workspace_id=? AND sha256=?", (ws["id"], sha)
        ).fetchone()
        if existing:
            return dict(existing)
        count = c.execute("SELECT count(*) FROM documents WHERE workspace_id=?", (ws["id"],)).fetchone()[0]
        total = c.execute("SELECT coalesce(sum(length(original)),0) FROM documents").fetchone()[0]
        if count >= 10 or total + len(raw) > 500 * 1024**2:
            raise HTTPException(429, "Document storage is at capacity. Paste the source text instead.")
        document_id = secrets.token_urlsafe(16)
        c.execute(
            "INSERT INTO documents VALUES(?,?,?,?,?,?,?)",
            (document_id, ws["id"], sha, bytes(raw), result["source"], result["pages"], time.time()),
        )
        db.event(
            c,
            ws["id"],
            None,
            "SOURCE_PRESERVED",
            f"Text PDF preserved with {result['pages']} page(s); source SHA-256 {sha}.",
        )
    return {"id": document_id, **result}


@app.get("/api/documents/{document_id}")
def original_document(document_id: str, ws=Depends(workspace)):
    with db.connect() as c:
        row = c.execute(
            "SELECT original FROM documents WHERE id=? AND workspace_id=?", (document_id, ws["id"])
        ).fetchone()
    if not row:
        raise HTTPException(404, "Source document not found in this workspace.")
    return Response(
        bytes(row[0]),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="original-source.pdf"'},
    )


def worker_status():
    with db.connect() as c:
        row = c.execute("SELECT value FROM settings WHERE key='worker_heartbeat'").fetchone()
    age = max(0, time.time() - float(row[0])) if row else None
    return {
        "ready": age is not None and age < 90,
        "last_seen_seconds": round(age) if age is not None else None,
    }


@app.get("/api/ready")
def readiness():
    status = worker_status()
    return JSONResponse(
        {"status": "ready" if status["ready"] else "degraded", "worker": status},
        status_code=200 if status["ready"] else 503,
    )


@app.get("/api/changes/{change_id}/preview.pdf")
def preview_flyer(change_id: str, revision: int, lang: Literal["en", "es"] = "en", ws=Depends(workspace)):
    from .domain import fact_payload

    with db.connect() as c:
        change = service.get_change(c, ws["id"], change_id)
        if change["revision"] != revision or change["state"] != "READY_FOR_REVIEW":
            raise HTTPException(409, "Save and confirm the current facts before previewing this revision.")
        payload = fact_payload(
            json.loads(change["facts"]),
            ws["public_id"],
            revision,
            db.now(c, ws["id"]),
            program=db.approved_context(change, ws),
        )
        payload["demo"] = not bool(ws.get("org_id"))
    return Response(
        flyer_pdf(payload, public_url(ws["public_id"]), draft=True, language=lang),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="draft-revision-{revision}.pdf"'},
    )


def require_workspace_owner(ws):
    if ws.get("org_id") and ws.get("actor", {}).get("role") != "owner":
        raise HTTPException(403, "An organization owner must approve this action.")


class Inventory(StrictBody):
    partner_name: str = Field(min_length=2, max_length=100)
    partner_owner: str = Field(default="", max_length=120)
    partner_url: str = Field(default="", max_length=500)
    print_owner: str = Field(default="", max_length=120)
    print_notes: str = Field(default="", max_length=500)


@app.post("/api/inventory")
def configure_inventory(body: Inventory, ws=Depends(workspace)):
    from urllib.parse import urlsplit

    require_workspace_owner(ws)
    if body.partner_url:
        try:
            url = urlsplit(body.partner_url)
            if url.scheme != "https" or not url.hostname or url.username or url.password:
                raise ValueError()
        except ValueError:
            raise HTTPException(
                422, "Use an HTTPS public listing URL without embedded credentials."
            ) from None
    with db.connect(write=True) as c:
        c.execute("UPDATE workspaces SET inventory=? WHERE id=?", (canonical(body.model_dump()), ws["id"]))
        db.event(
            c,
            ws["id"],
            None,
            "INVENTORY_UPDATED",
            "Registered the partner listing and print owners for future approval plans. Existing approved plans retain their snapshot.",
        )
    return body


class FollowUp(StrictBody):
    arrangement: str
    dates: list[str] = Field(min_length=1, max_length=12)


@app.post("/api/changes/{change_id}/follow-up")
def follow_up(change_id: str, body: FollowUp, ws=Depends(workspace)):
    from .domain import Proposal

    if body.arrangement not in ("extend", "restore", "new"):
        raise HTTPException(422, "Choose extend, confirmed baseline, or a new arrangement.")
    with db.connect(write=True) as c:
        previous = service.get_change(c, ws["id"], change_id)
        if not previous["approved_at"] or previous["state"] == "SUPERSEDED":
            raise HTTPException(409, "Choose the current approved notice for follow-up.")
        context = db.program(ws)
        old = json.loads(previous["facts"])
        base = old if body.arrangement == "extend" else context
        candidate = {
            **old,
            "program": context["name"],
            "timezone": context["timezone"],
            "dates": body.dates,
            "location": base["location"],
            "room": base["room"],
            "start_time": base["start_time"],
            "end_time": base["end_time"],
        }
        if body.arrangement != "extend":
            candidate["kind"] = "relocation"
        try:
            facts = Facts.model_validate(candidate)
        except ValueError:
            raise HTTPException(422, "Use valid exact dates and unambiguous session times.") from None
        if facts.expires_at() <= db.now(c, ws["id"]) or any(
            d.weekday() not in context["weekdays"] for d in facts.dates
        ):
            raise HTTPException(422, "Choose future dates on the program's confirmed weekdays.")
        source = f"Coordinator requested a {body.arrangement} draft after notice {change_id}, revision {previous['revision']}. Proposed facts: {canonical(candidate)}. These are suggestions requiring fresh confirmation, not confirmed future availability."
        source_hash = digest(source)
        existing = c.execute(
            "SELECT * FROM changes WHERE workspace_id=? AND source_hash=?", (ws["id"], source_hash)
        ).fetchone()
        if existing:
            return service.serialize(c, existing)
        if c.execute("SELECT count(*) FROM changes WHERE workspace_id=?", (ws["id"],)).fetchone()[0] >= (
            1000 if ws.get("org_id") else 30
        ):
            raise HTTPException(429, "The program has reached its change-record limit.")
        proposal = Proposal(
            **candidate,
            questions=["Confirm the next arrangement with the program owner before approving this draft."],
            explanation="Prepared from the prior arrangement and selected dates. No future availability has been inferred or published.",
        )
        if body.arrangement == "new":
            proposal.location = proposal.room = ""
        new_id = secrets.token_urlsafe(16)
        c.execute(
            "INSERT INTO changes(id,workspace_id,source,source_hash,proposal,state,created_at,mode,metrics,created_by) VALUES(?,?,?,?,?,'NEEDS_CLARIFICATION',?,'manual',?,?)",
            (
                new_id,
                ws["id"],
                source,
                source_hash,
                canonical(proposal.model_dump()),
                time.time(),
                canonical({"live": False, "origin": "coordinator_follow_up", "previous_change": change_id}),
                canonical(ws["actor"]) if ws.get("actor") else None,
            ),
        )
        db.event(
            c,
            ws["id"],
            new_id,
            "FOLLOW_UP_DRAFTED",
            "Prepared a new arrangement for explicit fact confirmation and a separate approval. Existing publication is unchanged.",
        )
        return service.serialize(c, service.get_change(c, ws["id"], new_id))

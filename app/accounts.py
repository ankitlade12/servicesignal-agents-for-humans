"""Invite-only organization access. Session tokens and invitation tokens are stored hashed."""

import hashlib
import os
import re
import secrets
import time
import threading

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from . import db
from .domain import PROGRAM, Program, canonical

router = APIRouter(prefix="/api/account")
COOKIE = "servicesignal_account"
SESSION_SECONDS = 12 * 3600
PASSWORD_SLOTS = threading.BoundedSemaphore(2)


def pilot_mode():
    return os.getenv("SERVICESIGNAL_MODE", "demo") == "pilot"


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password, salt=None):
    if not 12 <= len(password) <= 128:
        raise ValueError("Use a password containing 12 to 128 characters.")
    salt = salt or secrets.token_hex(16)
    if not PASSWORD_SLOTS.acquire(blocking=False):
        raise HTTPException(429, "Sign-in is busy. Please retry shortly.")
    try:
        value = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=131072, r=8, p=1, maxmem=256 * 1024**2
        ).hex()
    finally:
        PASSWORD_SLOTS.release()
    return salt + ":" + value


def verify_password(password, saved):
    try:
        return secrets.compare_digest(password_hash(password, saved.split(":")[0]), saved)
    except (ValueError, TypeError):
        return False


def normalize_email(value):
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise HTTPException(422, "Enter a valid email address.")
    return value


def record(c, org_id, actor_id, kind, detail):
    c.execute(
        "INSERT INTO account_events(org_id,actor_id,kind,detail,created_at) VALUES(?,?,?,?,?)",
        (org_id, actor_id, kind, detail, time.time()),
    )


def identity(request):
    if not pilot_mode():
        raise HTTPException(404, "Organization accounts are available in pilot mode.")
    with db.connect() as c:
        row = c.execute(
            """SELECT u.id,u.org_id,u.email,u.name,u.role,s.workspace_id,s.token_hash,
            o.name AS organization FROM sessions s JOIN users u ON u.id=s.user_id
            JOIN organizations o ON o.id=u.org_id
            WHERE s.token_hash=? AND s.expires_at>? AND u.active=1""",
            (token_hash(request.cookies.get(COOKIE, "")), time.time()),
        ).fetchone()
    if not row:
        raise HTTPException(401, "Sign in to your organization.")
    return dict(row)


def owner(request):
    actor = identity(request)
    if actor["role"] != "owner":
        raise HTTPException(403, "An organization owner must approve this action.")
    return actor


def scoped_workspace(request):
    actor = identity(request)
    if request.method not in ("GET", "HEAD") and actor["role"] == "viewer":
        raise HTTPException(403, "Your account has read-only access.")
    with db.connect() as c:
        row = c.execute(
            "SELECT * FROM workspaces WHERE id=? AND org_id=?", (actor["workspace_id"], actor["org_id"])
        ).fetchone()
    if not row:
        raise HTTPException(409, "Select a program in your organization.")
    return {
        **dict(row),
        "actor": {k: actor[k] for k in ("id", "name", "email", "role")},
        "organization": actor["organization"],
    }


def create_workspace(c, org_id, program):
    ws_id = secrets.token_urlsafe(16)
    c.execute(
        "INSERT INTO workspaces(id,token_hash,public_id,created_at,clock_offset,program,org_id) VALUES(?,?,?,?,0,?,?)",
        (
            ws_id,
            token_hash(secrets.token_urlsafe(32)),
            secrets.token_urlsafe(18),
            time.time(),
            canonical(program),
            org_id,
        ),
    )
    c.execute("INSERT INTO publications(workspace_id) VALUES(?)", (ws_id,))
    return ws_id


def bootstrap(organization, email, name, password):
    email = normalize_email(email)
    hashed = password_hash(password)
    with db.connect(write=True) as c:
        if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise ValueError("An account with that email already exists.")
        org_id, user_id = secrets.token_urlsafe(16), secrets.token_urlsafe(16)
        c.execute("INSERT INTO organizations VALUES(?,?,?)", (org_id, organization, time.time()))
        c.execute(
            "INSERT INTO users(id,org_id,email,name,password_hash,role,created_at) VALUES(?,?,?,?,?,?,?)",
            (user_id, org_id, email, name, hashed, "owner", time.time()),
        )
        # Private unconfigured workspace: intake stays blocked until its baseline is confirmed.
        ws_id = create_workspace(
            c, org_id, {**PROGRAM, "name": "New program", "organization": organization, "configured": False}
        )
        record(
            c,
            org_id,
            user_id,
            "ORGANIZATION_CREATED",
            "Organization and initial owner created by server operator.",
        )
    return org_id, user_id, ws_id


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Body):
    code: str = Field(default="", max_length=100)
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)


class Invite(Body):
    email: str = Field(max_length=254)
    role: str


class Accept(Login):
    token: str = Field(min_length=20, max_length=100)
    name: str = Field(min_length=2, max_length=100)


class Password(Body):
    code: str = Field(default="", max_length=100)
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


@router.get("/mode")
def mode():
    return {"mode": "pilot" if pilot_mode() else "demo"}


@router.post("/login")
def login(body: Login, request: Request, response: Response):
    if not pilot_mode():
        raise HTTPException(404, "Organization accounts are not enabled.")
    email = normalize_email(body.email)
    # Never trust visitor-provided forwarding headers for the address limit.
    keys = [
        "email:" + token_hash(email),
        "address:" + token_hash(request.client.host if request.client else "unknown"),
    ]
    with db.connect(write=True) as c:
        c.execute("DELETE FROM login_limits WHERE reset_at<?", (time.time(),))
        for key in keys:
            row = c.execute("SELECT attempts FROM login_limits WHERE key=?", (key,)).fetchone()
            if row and row[0] >= (10 if key.startswith("email:") else 50):
                raise HTTPException(429, "Too many sign-in attempts. Try again in 15 minutes.")
        for key in keys:
            c.execute(
                "INSERT INTO login_limits VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET attempts=attempts+1",
                (key, time.time() + 900),
            )
        user = c.execute("SELECT * FROM users WHERE email=? AND active=1", (email,)).fetchone()
    # Equal-work check for an unknown account; hashes and provider errors never go to the client.
    saved = user["password_hash"] if user else "00" * 16 + ":" + "00" * 64
    if not verify_password(body.password, saved):
        raise HTTPException(401, "Email or password is incorrect.")
    token = secrets.token_urlsafe(32)
    with db.connect(write=True) as c:
        current = c.execute("SELECT * FROM users WHERE id=? AND active=1", (user["id"],)).fetchone()
        if not current or current["password_hash"] != saved:
            raise HTTPException(401, "Account access changed. Sign in again.")
        from .account_security import verify_second_factor

        verify_second_factor(c, current, body.code)
        c.execute("DELETE FROM sessions WHERE expires_at<?", (time.time(),))
        # Limit retained sessions per user, retaining the newest twelve-hour window.
        if c.execute("SELECT count(*) FROM sessions WHERE user_id=?", (user["id"],)).fetchone()[0] >= 10:
            c.execute(
                "DELETE FROM sessions WHERE token_hash IN (SELECT token_hash FROM sessions WHERE user_id=? ORDER BY expires_at LIMIT 1)",
                (user["id"],),
            )
        ws = c.execute(
            "SELECT id FROM workspaces WHERE org_id=? ORDER BY created_at LIMIT 1", (user["org_id"],)
        ).fetchone()
        c.execute(
            "INSERT INTO sessions VALUES(?,?,?,?)",
            (token_hash(token), user["id"], ws[0] if ws else None, time.time() + SESSION_SECONDS),
        )
        c.execute("DELETE FROM login_limits WHERE key=?", (keys[0],))
        record(c, user["org_id"], user["id"], "SIGNED_IN", "Account signed in.")
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="strict",
        secure=os.getenv("COOKIE_SECURE", "0") == "1",
        max_age=SESSION_SECONDS,
    )
    return {"signed_in": True}


@router.post("/logout")
def logout(request: Request, response: Response):
    with db.connect(write=True) as c:
        c.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(request.cookies.get(COOKIE, "")),))
    response.delete_cookie(COOKIE)
    return {"signed_out": True}


@router.get("/team")
def team(request: Request):
    actor = owner(request)
    with db.connect() as c:
        members = [
            dict(r)
            for r in c.execute(
                "SELECT id,email,name,role,active FROM users WHERE org_id=? ORDER BY created_at",
                (actor["org_id"],),
            )
        ]
        events = [
            dict(r)
            for r in c.execute(
                "SELECT kind,detail,created_at FROM account_events WHERE org_id=? ORDER BY id DESC LIMIT 50",
                (actor["org_id"],),
            )
        ]
    return {"members": members, "events": events}


@router.post("/invitations")
def invite(body: Invite, request: Request):
    actor = owner(request)
    if body.role not in ("editor", "viewer"):
        raise HTTPException(422, "Choose editor or viewer access.")
    email = normalize_email(body.email)
    token = secrets.token_urlsafe(32)
    with db.connect(write=True) as c:
        c.execute("DELETE FROM invitations WHERE expires_at<? OR used=1", (time.time(),))
        if (
            c.execute("SELECT count(*) FROM invitations WHERE org_id=?", (actor["org_id"],)).fetchone()[0]
            >= 20
        ):
            raise HTTPException(429, "This organization has 20 pending invitations.")
        if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise HTTPException(
                409,
                "An account already exists for that email. Contact the server operator for access recovery.",
            )
        c.execute(
            "INSERT INTO invitations VALUES(?,?,?,?,?,0)",
            (token_hash(token), actor["org_id"], email, body.role, time.time() + 86400),
        )
        record(c, actor["org_id"], actor["id"], "INVITED", f"Invited {email} as {body.role}.")
    return {"invite_path": "/#join=" + token, "expires_in_hours": 24}


@router.post("/accept")
def accept(body: Accept):
    if not pilot_mode():
        raise HTTPException(404, "Organization accounts are not enabled.")
    email = normalize_email(body.email)
    # Validate token before expensive password hashing; recheck atomically before consumption.
    with db.connect() as c:
        invitation = c.execute(
            "SELECT * FROM invitations WHERE token_hash=? AND email=? AND expires_at>? AND used=0",
            (token_hash(body.token), email, time.time()),
        ).fetchone()
    if not invitation:
        raise HTTPException(400, "This invitation is unavailable or expired.")
    try:
        hashed = password_hash(body.password)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    with db.connect(write=True) as c:
        if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise HTTPException(409, "This account already exists.")
        used = c.execute(
            "UPDATE invitations SET used=1 WHERE token_hash=? AND used=0 AND expires_at>?",
            (token_hash(body.token), time.time()),
        )
        if used.rowcount != 1:
            raise HTTPException(400, "This invitation is unavailable or expired.")
        user_id = secrets.token_urlsafe(16)
        c.execute(
            "INSERT INTO users(id,org_id,email,name,password_hash,role,created_at) VALUES(?,?,?,?,?,?,?)",
            (user_id, invitation["org_id"], email, body.name, hashed, invitation["role"], time.time()),
        )
        record(c, invitation["org_id"], user_id, "INVITATION_ACCEPTED", "Invited account activated.")
    return {"created": True}


@router.post("/members/{user_id}/deactivate")
def deactivate(user_id: str, request: Request):
    actor = owner(request)
    with db.connect(write=True) as c:
        user = c.execute("SELECT * FROM users WHERE id=? AND org_id=?", (user_id, actor["org_id"])).fetchone()
        if not user:
            raise HTTPException(404, "Member not found.")
        if user["role"] == "owner":
            raise HTTPException(409, "Owner access is managed by the server operator.")
        c.execute("UPDATE users SET active=0 WHERE id=?", (user_id,))
        c.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        record(
            c,
            actor["org_id"],
            actor["id"],
            "MEMBER_DEACTIVATED",
            f"Deactivated {user['email']}; all sessions revoked.",
        )
    return {"deactivated": True}


@router.post("/password")
def change_password(body: Password, request: Request, response: Response):
    actor = identity(request)
    with db.connect() as c:
        old = c.execute("SELECT password_hash FROM users WHERE id=?", (actor["id"],)).fetchone()[0]
    if not verify_password(body.current_password, old):
        raise HTTPException(401, "Current password is incorrect.")
    from .account_security import limit

    limit("password:" + actor["id"])
    hashed = password_hash(body.new_password)
    with db.connect(write=True) as c:
        from .account_security import verify_second_factor

        current = c.execute("SELECT * FROM users WHERE id=?", (actor["id"],)).fetchone()
        verify_second_factor(c, current, body.code)
        if (
            c.execute(
                "UPDATE users SET password_hash=? WHERE id=? AND password_hash=?", (hashed, actor["id"], old)
            ).rowcount
            != 1
        ):
            raise HTTPException(409, "Account credentials changed. Sign in again.")
        c.execute("DELETE FROM sessions WHERE user_id=?", (actor["id"],))
        record(c, actor["org_id"], actor["id"], "PASSWORD_CHANGED", "Password changed; all sessions revoked.")
    response.delete_cookie(COOKIE)
    return {"sign_in_required": True}


@router.post("/programs")
def new_program(body: Program, request: Request):
    actor = owner(request)
    if body.organization != actor["organization"]:
        raise HTTPException(422, "Use your organization name.")
    with db.connect(write=True) as c:
        if (
            c.execute("SELECT count(*) FROM workspaces WHERE org_id=?", (actor["org_id"],)).fetchone()[0]
            >= 25
        ):
            raise HTTPException(429, "This pilot supports 25 programs per organization.")
        ws_id = create_workspace(c, actor["org_id"], {**body.model_dump(), "configured": False})
        c.execute("UPDATE sessions SET workspace_id=? WHERE token_hash=?", (ws_id, actor["token_hash"]))
        record(c, actor["org_id"], actor["id"], "PROGRAM_CREATED", body.name)
    return {"workspace_id": ws_id}


@router.post("/programs/{workspace_id}/select")
def select_program(workspace_id: str, request: Request):
    actor = identity(request)
    with db.connect(write=True) as c:
        if not c.execute(
            "SELECT 1 FROM workspaces WHERE id=? AND org_id=?", (workspace_id, actor["org_id"])
        ).fetchone():
            raise HTTPException(404, "Program not found in your organization.")
        c.execute(
            "UPDATE sessions SET workspace_id=? WHERE token_hash=?", (workspace_id, actor["token_hash"])
        )
    return {"selected": True}

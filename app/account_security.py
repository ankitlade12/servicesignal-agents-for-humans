"""TOTP enrollment, one-use recovery codes, and expiring email password recovery."""

import base64
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import quote

import pyotp
from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import Field

from . import accounts, db

router = APIRouter(prefix="/api/account")


def cipher():
    configured = os.getenv("SERVICESIGNAL_ENCRYPTION_KEY")
    if configured:
        return Fernet(configured.encode())
    key_path = Path(db.path() + ".key")
    key_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(Fernet.generate_key())
    return Fernet(key_path.read_bytes())


def seal(value):
    return cipher().encrypt(value.encode()).decode()


def unseal(value):
    return cipher().decrypt(value.encode()).decode()


def limit(key, maximum=10, seconds=900):
    key = "security:" + accounts.token_hash(key)
    with db.connect(write=True) as c:
        c.execute("DELETE FROM login_limits WHERE reset_at<?", (time.time(),))
        row = c.execute("SELECT attempts FROM login_limits WHERE key=?", (key,)).fetchone()
        if row and row[0] >= maximum:
            raise HTTPException(429, "Too many attempts. Please try again later.")
        c.execute(
            "INSERT INTO login_limits VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET attempts=attempts+1",
            (key, time.time() + seconds),
        )


def verify_second_factor(c, user, code):
    if not user["mfa_secret"]:
        return
    code = code.strip().replace(" ", "")
    codes = json.loads(user["recovery_codes"])
    hashed = accounts.token_hash(code)
    if hashed in codes:
        codes.remove(hashed)
        c.execute("UPDATE users SET recovery_codes=? WHERE id=?", (json.dumps(codes), user["id"]))
        return
    totp = pyotp.TOTP(unseal(user["mfa_secret"]))
    step = int(time.time()) // 30
    for candidate in (step - 1, step, step + 1):
        if candidate > user["mfa_last_step"] and secrets.compare_digest(totp.at(candidate * 30), code):
            c.execute("UPDATE users SET mfa_last_step=? WHERE id=?", (candidate, user["id"]))
            return
    raise HTTPException(401, "Enter an unused authenticator code or a recovery code.")


class Proof(accounts.Body):
    password: str = Field(max_length=128)
    code: str = Field(default="", max_length=100)


@router.get("/security")
def security(request: Request):
    actor = accounts.identity(request)
    with db.connect() as c:
        user = c.execute("SELECT * FROM users WHERE id=?", (actor["id"],)).fetchone()
    from .delivery import smtp_configured

    return {
        "mfa_enabled": bool(user["mfa_secret"]),
        "recovery_codes_remaining": len(json.loads(user["recovery_codes"])),
        "email_recovery_configured": smtp_configured(),
    }


@router.post("/mfa/setup")
def setup(body: Proof, request: Request):
    actor = accounts.identity(request)
    limit("mfa:" + actor["id"])
    with db.connect(write=True) as c:
        user = c.execute("SELECT * FROM users WHERE id=?", (actor["id"],)).fetchone()
        if not accounts.verify_password(body.password, user["password_hash"]):
            raise HTTPException(401, "Current password is incorrect.")
        if user["mfa_secret"]:
            raise HTTPException(409, "Two-factor authentication is already enabled.")
        secret = pyotp.random_base32()
        c.execute(
            "UPDATE users SET mfa_pending=?,mfa_pending_until=? WHERE id=?",
            (seal(secret), time.time() + 600, actor["id"]),
        )
    uri = pyotp.TOTP(secret).provisioning_uri(actor["email"], issuer_name="ServiceSignal")
    from .notices import qr_svg

    return {"secret": secret, "qr": "data:image/svg+xml;base64," + base64.b64encode(qr_svg(uri)).decode()}


@router.post("/mfa/enable")
def enable(body: Proof, request: Request, response: Response):
    actor = accounts.identity(request)
    limit("mfa:" + actor["id"])
    with db.connect(write=True) as c:
        user = c.execute("SELECT * FROM users WHERE id=?", (actor["id"],)).fetchone()
        if not user["mfa_pending"] or user["mfa_pending_until"] < time.time():
            raise HTTPException(409, "Start a new authenticator setup.")
        if not accounts.verify_password(body.password, user["password_hash"]):
            raise HTTPException(401, "Current password is incorrect.")
        if not pyotp.TOTP(unseal(user["mfa_pending"])).verify(
            body.code, for_time=time.time(), valid_window=0
        ):
            raise HTTPException(401, "Authenticator code is incorrect.")
        codes = [secrets.token_hex(8) for _ in range(8)]
        c.execute(
            "UPDATE users SET mfa_secret=mfa_pending,mfa_pending=NULL,mfa_pending_until=NULL,mfa_last_step=?,recovery_codes=? WHERE id=?",
            (int(time.time()) // 30, json.dumps([accounts.token_hash(x) for x in codes]), actor["id"]),
        )
        c.execute("DELETE FROM sessions WHERE user_id=?", (actor["id"],))
        accounts.record(
            c, actor["org_id"], actor["id"], "MFA_ENABLED", "Authenticator enabled; sessions revoked."
        )
    response.delete_cookie(accounts.COOKIE)
    return {"recovery_codes": codes, "sign_in_required": True}


@router.post("/mfa/disable")
def disable(body: Proof, request: Request, response: Response):
    actor = accounts.identity(request)
    limit("mfa:" + actor["id"])
    with db.connect(write=True) as c:
        user = c.execute("SELECT * FROM users WHERE id=?", (actor["id"],)).fetchone()
        if not accounts.verify_password(body.password, user["password_hash"]):
            raise HTTPException(401, "Current password is incorrect.")
        verify_second_factor(c, user, body.code)
        c.execute(
            "UPDATE users SET mfa_secret=NULL,mfa_pending=NULL,recovery_codes='[]',mfa_last_step=-1 WHERE id=?",
            (actor["id"],),
        )
        c.execute("DELETE FROM sessions WHERE user_id=?", (actor["id"],))
        accounts.record(
            c, actor["org_id"], actor["id"], "MFA_DISABLED", "Authenticator disabled; sessions revoked."
        )
    response.delete_cookie(accounts.COOKIE)
    return {"sign_in_required": True}


class RecoveryRequest(accounts.Body):
    email: str = Field(max_length=254)


@router.post("/recovery/request")
def request_recovery(body: RecoveryRequest, request: Request):
    if not accounts.pilot_mode():
        raise HTTPException(404)
    email = accounts.normalize_email(body.email)
    limit("recovery-address:" + (request.client.host if request.client else "unknown"), 10, 3600)
    limit("recovery-email:" + email, 3, 3600)
    from .delivery import smtp_configured

    if smtp_configured():
        with db.connect(write=True) as c:
            user = c.execute("SELECT * FROM users WHERE email=? AND active=1", (email,)).fetchone()
            if user:
                token = secrets.token_urlsafe(32)
                expires = time.time() + 1800
                c.execute(
                    "DELETE FROM password_resets WHERE user_id=? OR expires_at<?", (user["id"], time.time())
                )
                c.execute(
                    "INSERT INTO password_resets VALUES(?,?,?,0)",
                    (accounts.token_hash(token), user["id"], expires),
                )
                url = (
                    os.getenv("PUBLIC_ORIGIN", "http://localhost:8017").rstrip("/")
                    + "/#recover="
                    + quote(token)
                )
                body_text = (
                    "Reset your ServiceSignal password within 30 minutes:\n"
                    + url
                    + "\n\nIf you did not request this, ignore this message. Two-factor authentication remains required."
                )
                c.execute(
                    "INSERT INTO deliveries(id,channel,target,body,content_hash,state,created_at,expires_at) VALUES(?,?,?,?,?,?,?,?)",
                    (
                        secrets.token_urlsafe(16),
                        "recovery",
                        email,
                        seal(body_text),
                        accounts.token_hash(token),
                        "QUEUED",
                        time.time(),
                        expires,
                    ),
                )
    return {
        "message": "If this account is active and email recovery is configured, a reset link will arrive shortly. Otherwise contact your organization operator."
    }


class RecoveryComplete(accounts.Body):
    token: str = Field(min_length=20, max_length=100)
    password: str = Field(min_length=12, max_length=128)
    code: str = Field(default="", max_length=100)


@router.post("/recovery/complete")
def complete_recovery(body: RecoveryComplete, request: Request):
    if not accounts.pilot_mode():
        raise HTTPException(404)
    limit("reset:" + (request.client.host if request.client else "unknown"))
    with db.connect() as c:
        row = c.execute(
            "SELECT * FROM password_resets WHERE token_hash=? AND used=0 AND expires_at>?",
            (accounts.token_hash(body.token), time.time()),
        ).fetchone()
    if not row:
        raise HTTPException(400, "This reset link is unavailable or expired.")
    hashed = accounts.password_hash(body.password)
    with db.connect(write=True) as c:
        row = c.execute(
            "SELECT * FROM password_resets WHERE token_hash=? AND used=0 AND expires_at>?",
            (accounts.token_hash(body.token), time.time()),
        ).fetchone()
        if not row:
            raise HTTPException(400, "This reset link is unavailable or expired.")
        user = c.execute("SELECT * FROM users WHERE id=? AND active=1", (row["user_id"],)).fetchone()
        if not user:
            raise HTTPException(400, "This reset link is unavailable or expired.")
        verify_second_factor(c, user, body.code)
        c.execute("UPDATE users SET password_hash=? WHERE id=?", (hashed, user["id"]))
        c.execute("DELETE FROM password_resets WHERE user_id=?", (user["id"],))
        c.execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))
        accounts.record(
            c,
            user["org_id"],
            user["id"],
            "PASSWORD_RECOVERED",
            "Email recovery completed; sessions revoked. MFA retained.",
        )
    return {"sign_in_required": True}

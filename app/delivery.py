"""Explicitly approved outbound deliveries with honest acceptance/verification states."""

import html
import json
import os
import re
import secrets
import smtplib
import ssl
import time
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field

from . import accounts, db, service
from .domain import canonical, digest, visible_facts

router = APIRouter(prefix="/api/delivery")


def smtp_configured():
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM"))


def send_email(recipient, content, message_id):
    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = recipient
    message["Subject"] = (
        "ServiceSignal community update"
        if "Reset your ServiceSignal" not in content
        else "Reset your ServiceSignal password"
    )
    message["Message-ID"] = f"<{message_id}@servicesignal.local>"
    message.set_content(content)
    host, port = os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587"))
    mode = os.getenv("SMTP_SECURITY", "starttls")
    if mode not in ("ssl", "starttls"):
        raise ValueError("SMTP requires SSL or STARTTLS.")
    server = (
        smtplib.SMTP_SSL(host, port, timeout=15, context=ssl.create_default_context())
        if mode == "ssl"
        else smtplib.SMTP(host, port, timeout=15)
    )
    with server:
        if mode == "starttls":
            server.starttls(context=ssl.create_default_context())
        if os.getenv("SMTP_USERNAME"):
            server.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
        refused = server.send_message(message)
        if refused:
            raise ValueError("Recipient rejected.")


def connectors(ws):
    path = os.getenv("SERVICESIGNAL_CONNECTORS_FILE")
    if not path:
        return []
    entries = json.loads(Path(path).read_text())
    return [
        entry
        for entry in entries
        if entry.get("workspace_id") == ws["id"] and entry.get("org_id") == ws["org_id"]
    ]


def connector(ws, identifier):
    result = next((entry for entry in connectors(ws) if entry["id"] == identifier), None)
    if not result:
        raise HTTPException(404, "This destination is not registered for your program.")
    for field in ("api_origin", "public_url"):
        url = urlsplit(result[field])
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment:
            raise HTTPException(
                503, "The operator must configure HTTPS destination URLs without embedded credentials."
            )
    if not isinstance(result["page_id"], int) or result["page_id"] < 1:
        raise HTTPException(503, "The operator must configure a dedicated WordPress page.")
    return result


def wordpress_get(client, config):
    response = client.get(
        config["api_origin"].rstrip("/") + "/wp-json/wp/v2/pages/" + str(config["page_id"]),
        params={"context": "edit"},
        auth=(os.environ[config["username_env"]], os.environ[config["password_env"]]),
    )
    response.raise_for_status()
    return response.json()["content"]["raw"]


def delivery_text(payload, url):
    facts = visible_facts(payload)
    return "\n".join(
        [
            facts["organization"],
            facts["program"],
            facts["message"],
            facts["dates"],
            facts["start_time"] + "–" + facts["end_time"] + " " + facts["timezone"],
            facts["location"],
            facts["room"],
            facts["contact"],
            "Current notice: " + url,
        ]
    )


def wp_html(payload, url):
    values = visible_facts(payload)
    return (
        '<section aria-label="Approved community notice">'
        + "".join(
            f'<p><span data-fact="{html.escape(key)}">{html.escape(value)}</span></p>'
            for key, value in values.items()
        )
        + f'<p><a href="{html.escape(url, quote=True)}">Check current notice</a></p></section>'
    )


def access(request):
    ws = accounts.scoped_workspace(request)
    if ws["actor"]["role"] != "owner":
        raise HTTPException(403, "An organization owner must authorize external delivery.")
    return ws


@router.get("/status")
def status(request: Request):
    ws = access(request)
    with db.connect() as c:
        rows = [
            dict(r)
            for r in c.execute(
                "SELECT id,change_id,channel,target,state,detail,created_at,observed_at FROM deliveries WHERE workspace_id=? ORDER BY created_at DESC LIMIT 100",
                (ws["id"],),
            )
        ]
    return {
        "email_configured": smtp_configured(),
        "sms_configured": all(
            os.getenv(key) for key in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM")
        ),
        "wordpress": [
            {"id": x["id"], "label": x["label"], "public_url": x["public_url"]} for x in connectors(ws)
        ],
        "deliveries": rows,
    }


class Draft(accounts.Body):
    change_id: str
    channel: str
    target: str = Field(min_length=1, max_length=254)
    consent: str = Field(min_length=10, max_length=300)


@router.post("/draft")
def draft(body: Draft, request: Request):
    ws = access(request)
    if body.channel not in ("email", "sms", "wordpress"):
        raise HTTPException(422, "Choose email, SMS or a registered WordPress page.")
    from .main import publication, public_url

    with db.connect() as c:
        change = service.get_change(c, ws["id"], body.change_id)
    if not change["approved_at"] or change["state"] in ("SUPERSEDED", "APPLYING"):
        raise HTTPException(409, "Publish and verify the current notice first.")
    payload = publication(ws["public_id"], body.change_id)
    if not payload:
        raise HTTPException(409, "This notice has not been published.")
    url = public_url(ws["public_id"]) + "?change=" + body.change_id
    content = {
        "text": delivery_text(payload, url),
        "facts": visible_facts(payload),
        "consent": body.consent,
        "payload_hash": digest(payload),
        "expired": payload["expired"],
    }
    if body.channel == "email":
        if not smtp_configured():
            raise HTTPException(503, "Email has not been configured by the operator.")
        target = accounts.normalize_email(body.target)
    elif body.channel == "sms":
        if not all(os.getenv(k) for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM")):
            raise HTTPException(503, "SMS has not been configured by the operator.")
        if not re.fullmatch(r"\+[1-9][0-9]{7,14}", body.target):
            raise HTTPException(422, "Use an international phone number such as +12025550123.")
        target = body.target
        content["text"] = (
            payload["facts"]["program"]
            + ": "
            + visible_facts(payload)["message"]
            + "\n"
            + url
            + "\nReply STOP to opt out."
        )
    else:
        config = connector(ws, body.target)
        target = body.target
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            old = wordpress_get(client, config)
        content.update(
            html=wp_html(payload, url),
            previous_hash=digest(old),
            previous_content=old[:20000],
            config_hash=digest(config),
            public_url=config["public_url"],
        )
    content_hash = digest(
        {
            "channel": body.channel,
            "target": target,
            "change": change["id"],
            "revision": change["revision"],
            "payload": content["payload_hash"],
            "config": content.get("config_hash"),
        }
    )
    with db.connect(write=True) as c:
        existing = c.execute(
            "SELECT * FROM deliveries WHERE workspace_id=? AND content_hash=?", (ws["id"], content_hash)
        ).fetchone()
        if existing:
            return {
                "id": existing["id"],
                "content_hash": existing["content_hash"],
                "body": json.loads(existing["body"]),
                "state": existing["state"],
            }
        count = c.execute(
            "SELECT count(*) FROM deliveries WHERE workspace_id=? AND created_at>?",
            (ws["id"], time.time() - 86400),
        ).fetchone()[0]
        if count >= 100:
            raise HTTPException(429, "This program has reached its daily 100-delivery limit.")
        identifier = secrets.token_urlsafe(16)
        c.execute(
            "INSERT INTO deliveries(id,workspace_id,change_id,revision,channel,target,body,content_hash,state,created_at,expires_at,actor_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                identifier,
                ws["id"],
                change["id"],
                change["revision"],
                body.channel,
                target,
                canonical(content),
                content_hash,
                "DRAFT",
                time.time(),
                time.time() + 900,
                ws["actor"]["id"],
            ),
        )
    return {"id": identifier, "content_hash": content_hash, "body": content, "state": "DRAFT"}


class Approval(accounts.Body):
    content_hash: str
    confirmed: bool


@router.post("/{delivery_id}/approve")
def approve(delivery_id: str, body: Approval, request: Request):
    ws = access(request)
    if not body.confirmed:
        raise HTTPException(422, "Confirm the recipient, content and authorization before sending.")
    with db.connect(write=True) as c:
        row = c.execute(
            "SELECT * FROM deliveries WHERE id=? AND workspace_id=?", (delivery_id, ws["id"])
        ).fetchone()
        if not row:
            raise HTTPException(404)
        if row["content_hash"] != body.content_hash:
            raise HTTPException(409, "Review the exact current delivery draft.")
        if row["state"] != "DRAFT":
            return {"state": row["state"]}
        if row["expires_at"] < time.time():
            raise HTTPException(409, "This delivery draft expired. Prepare a fresh draft.")
        ch = service.get_change(c, ws["id"], row["change_id"])
        if ch["state"] == "SUPERSEDED" or ch["revision"] != row["revision"]:
            raise HTTPException(409, "This notice changed. Prepare a new delivery.")
        c.execute(
            "UPDATE deliveries SET state='QUEUED',approved_at=?,actor_id=? WHERE id=?",
            (time.time(), ws["actor"]["id"], delivery_id),
        )
        db.event(
            c,
            ws["id"],
            ch["id"],
            "DELIVERY_APPROVED",
            f"Owner approved {row['channel']} delivery {delivery_id}.",
        )
    return {"state": "QUEUED"}


@router.post("/{delivery_id}/cancel")
def cancel(delivery_id: str, request: Request):
    ws = access(request)
    with db.connect(write=True) as c:
        changed = c.execute(
            "UPDATE deliveries SET state='CANCELED' WHERE id=? AND workspace_id=? AND state IN ('DRAFT','QUEUED')",
            (delivery_id, ws["id"]),
        ).rowcount
    if not changed:
        raise HTTPException(409, "Only a draft or queued delivery can be canceled.")
    return {"state": "CANCELED"}


def process_one(client=None):
    with db.connect(write=True) as c:
        c.execute(
            "UPDATE deliveries SET state='UNKNOWN',detail='Worker interrupted during delivery. Check provider before sending again.' WHERE state='SENDING' AND claimed_at<?",
            (time.time() - 120,),
        )
        c.execute(
            "UPDATE deliveries SET state='EXPIRED',body=CASE WHEN channel='recovery' THEN '' ELSE body END WHERE state IN ('DRAFT','QUEUED') AND expires_at<?",
            (time.time(),),
        )
        row = c.execute(
            "SELECT * FROM deliveries WHERE state='QUEUED' ORDER BY created_at LIMIT 1"
        ).fetchone()
        if not row:
            return False
        delivery = dict(row)
        c.execute("UPDATE deliveries SET state='SENDING',claimed_at=? WHERE id=?", (time.time(), row["id"]))
    owned = client is None
    client = client or httpx.Client(timeout=15, follow_redirects=False)
    state, detail, provider_id = "UNKNOWN", "Provider outcome is uncertain; check before sending again.", None
    try:
        if delivery["channel"] == "recovery":
            from .account_security import unseal

            send_email(delivery["target"], unseal(delivery["body"]), delivery["id"])
            state, detail = (
                "ACCEPTED",
                "Mail server accepted the reset message; inbox delivery is not confirmed.",
            )
        else:
            from .main import publication

            with db.connect() as c:
                ws = dict(
                    c.execute("SELECT * FROM workspaces WHERE id=?", (delivery["workspace_id"],)).fetchone()
                )
                ch = service.get_change(c, ws["id"], delivery["change_id"])
                active_owner = c.execute(
                    "SELECT 1 FROM users WHERE id=? AND org_id=? AND active=1 AND role='owner'",
                    (delivery["actor_id"], ws["org_id"]),
                ).fetchone()
            if not active_owner or ch["state"] == "SUPERSEDED" or ch["revision"] != delivery["revision"]:
                state, detail = "CANCELED", "Authority or notice revision changed before delivery."
                return True
            content = json.loads(delivery["body"])
            if digest(publication(ws["public_id"], ch["id"])) != content["payload_hash"]:
                state, detail = "CANCELED", "The public notice changed or expired. Prepare a fresh delivery."
                return True
            if delivery["channel"] == "email":
                send_email(delivery["target"], content["text"], delivery["id"])
                state, detail = (
                    "ACCEPTED",
                    "Mail server accepted this message; inbox delivery is not confirmed.",
                )
            elif delivery["channel"] == "sms":
                response = client.post(
                    "https://api.twilio.com/2010-04-01/Accounts/"
                    + os.environ["TWILIO_ACCOUNT_SID"]
                    + "/Messages.json",
                    auth=(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"]),
                    data={
                        "To": delivery["target"],
                        "From": os.environ["TWILIO_FROM"],
                        "Body": content["text"],
                    },
                )
                response.raise_for_status()
                provider_id = response.json()["sid"]
                state, detail = "ACCEPTED", "Twilio accepted this message; carrier delivery is pending."
            else:
                config = connector(ws, delivery["target"])
                if digest(config) != content["config_hash"]:
                    state, detail = "CANCELED", "Destination configuration changed; prepare a fresh approval."
                    return True
                before = wordpress_get(client, config)
                if before != content["html"]:
                    if digest(before) != content["previous_hash"]:
                        state, detail = (
                            "NEEDS_OWNER",
                            "The WordPress page changed after preview. No content was written.",
                        )
                        return True
                    response = client.post(
                        config["api_origin"].rstrip("/") + "/wp-json/wp/v2/pages/" + str(config["page_id"]),
                        auth=(os.environ[config["username_env"]], os.environ[config["password_env"]]),
                        json={"content": content["html"]},
                    )
                    response.raise_for_status()
                response = client.get(config["public_url"], headers={"Cache-Control": "no-cache"})
                response.raise_for_status()
                from .notices import FactParser

                parsed = FactParser()
                parsed.feed(response.text)
                if parsed.facts == content["facts"]:
                    state, detail = (
                        "VERIFIED",
                        "Fresh public WordPress page matched all approved visible facts.",
                    )
                else:
                    state, detail = (
                        "NEEDS_OWNER",
                        "WordPress write may have succeeded, but the public page did not match every approved field.",
                    )
    except Exception as error:
        # Never automatically retry a write with an uncertain outcome: email/SMS lack an application idempotency contract.
        detail = (
            "Delivery could not be confirmed ("
            + type(error).__name__
            + "). Check provider records before sending again."
        )
    finally:
        with db.connect(write=True) as c:
            c.execute(
                "UPDATE deliveries SET state=?,detail=?,provider_id=?,observed_at=?,body=CASE WHEN channel='recovery' THEN '' ELSE body END WHERE id=?",
                (state, detail, provider_id, time.time(), delivery["id"]),
            )
        if owned:
            client.close()
    return True


def poll_sms(client=None):
    if not os.getenv("TWILIO_ACCOUNT_SID"):
        return
    with db.connect() as c:
        rows = c.execute(
            "SELECT id,provider_id FROM deliveries WHERE channel='sms' AND state='ACCEPTED' AND observed_at<? LIMIT 10",
            (time.time() - 60,),
        ).fetchall()
    owned = client is None
    client = client or httpx.Client(timeout=10)
    try:
        for row in rows:
            response = client.get(
                "https://api.twilio.com/2010-04-01/Accounts/"
                + os.environ["TWILIO_ACCOUNT_SID"]
                + "/Messages/"
                + row["provider_id"]
                + ".json",
                auth=(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"]),
            )
            response.raise_for_status()
            observed = response.json()["status"]
            state = (
                "DELIVERED"
                if observed == "delivered"
                else "FAILED"
                if observed in ("failed", "undelivered", "canceled")
                else "ACCEPTED"
            )
            with db.connect(write=True) as c:
                c.execute(
                    "UPDATE deliveries SET state=?,detail=?,observed_at=? WHERE id=?",
                    (
                        state,
                        "Twilio reported carrier status: "
                        + observed
                        + ". This does not establish that the recipient read it.",
                        time.time(),
                        row["id"],
                    ),
                )
    finally:
        if owned:
            client.close()


def run():
    import logging

    db.init()
    logging.basicConfig(level=logging.INFO)
    last_poll = 0
    while True:
        try:
            worked = process_one()
            if time.time() - last_poll >= 60:
                poll_sms()
                last_poll = time.time()
            if not worked:
                time.sleep(1)
        except Exception as error:
            logging.getLogger("servicesignal.delivery").warning(
                "Delivery iteration failed: %s", type(error).__name__
            )
            time.sleep(5)


if __name__ == "__main__":
    run()

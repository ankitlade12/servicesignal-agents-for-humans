import io
import json
import time

import httpx
import pyotp
from cryptography.exceptions import InvalidTag
import pytest
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app import account_security, db, delivery, operations
from test_accounts import PASSWORD, configure, member, pilot as pilot
from test_workflow import FACTS, approve, data, draft, review, tick


def enroll(c):
    result = c.post("/api/account/mfa/setup", json={"password": PASSWORD})
    assert result.status_code == 200
    secret = result.json()["secret"]
    result = c.post(
        "/api/account/mfa/enable", json={"password": PASSWORD, "code": pyotp.TOTP(secret).at(time.time())}
    )
    assert result.status_code == 200
    return secret, result.json()["recovery_codes"]


def test_mfa_enrollment_login_replay_and_recovery_code(pilot, monkeypatch):
    c, _, user_id, _ = pilot
    secret, codes = enroll(c)
    assert c.get("/api/workspace").status_code == 401
    body = {"email": "owner@example.test", "password": PASSWORD}
    assert c.post("/api/account/login", json=body).status_code == 401
    assert (
        c.post("/api/account/login", json={**body, "code": pyotp.TOTP(secret).at(time.time())}).status_code
        == 401
    )
    now = time.time()
    monkeypatch.setattr(time, "time", lambda: now + 30)
    code = pyotp.TOTP(secret).at(time.time())
    assert c.post("/api/account/login", json={**body, "code": code}).status_code == 200
    assert c.get("/api/account/security").json()["mfa_enabled"] is True
    c.post("/api/account/logout", json={})
    assert c.post("/api/account/login", json={**body, "code": code}).status_code == 401
    assert c.post("/api/account/login", json={**body, "code": codes[0]}).status_code == 200
    c.post("/api/account/logout", json={})
    assert c.post("/api/account/login", json={**body, "code": codes[0]}).status_code == 401
    with db.connect() as connection:
        stored = connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        assert stored["mfa_secret"] != secret and codes[0] not in stored["recovery_codes"]


def test_email_recovery_is_encrypted_single_use_and_revokes_sessions(pilot, monkeypatch):
    c, *_ = pilot
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_FROM", "service@example.test")
    result = c.post("/api/account/recovery/request", json={"email": "owner@example.test"})
    assert result.status_code == 200 and "token" not in result.text
    with db.connect() as connection:
        queued = connection.execute("SELECT * FROM deliveries WHERE channel='recovery'").fetchone()
    assert "#recover=" not in queued["body"]
    sent = []
    monkeypatch.setattr(delivery, "send_email", lambda target, text, key: sent.append((target, text)))
    assert delivery.process_one()
    token = sent[0][1].split("#recover=")[1].split("\n")[0]
    body = {"token": token, "password": "changed-password-for-test"}
    assert c.post("/api/account/recovery/complete", json=body).status_code == 200
    assert c.get("/api/workspace").status_code == 401
    assert c.post("/api/account/recovery/complete", json=body).status_code == 400
    assert (
        c.post(
            "/api/account/login", json={"email": "owner@example.test", "password": body["password"]}
        ).status_code
        == 200
    )


def test_password_recovery_does_not_bypass_mfa(pilot, monkeypatch):
    c, *_ = pilot
    _, codes = enroll(c)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_FROM", "service@example.test")
    c.post("/api/account/recovery/request", json={"email": "owner@example.test"})
    with db.connect() as connection:
        row = connection.execute("SELECT body FROM deliveries WHERE channel='recovery'").fetchone()
    token = account_security.unseal(row[0]).split("#recover=")[1].split("\n")[0]
    body = {"token": token, "password": "new-password-for-test"}
    assert c.post("/api/account/recovery/complete", json=body).status_code == 401
    assert c.post("/api/account/recovery/complete", json={**body, "code": codes[0]}).status_code == 200
    assert (
        c.post(
            "/api/account/login", json={"email": "owner@example.test", "password": body["password"]}
        ).status_code
        == 401
    )


def test_simultaneous_nonoverlapping_notices_publish_independently(pilot):
    c, *_ = pilot
    configure(c)
    first = review(c)
    second = review(
        c,
        draft(c, "A second fictional notice requiring manual confirmation."),
        {**FACTS, "dates": ["2026-09-29"], "room": "Room C"},
    )
    approve(c, first)
    approve(c, second)
    tick(c)
    tick(c)
    records = data(c)["changes"]
    assert all(
        next(a for a in ch["actions"] if a["destination"] == "page")["state"] == "VERIFIED" for ch in records
    )
    public = data(c)["public_id"]
    page = c.get("/notices/" + public).text
    assert "Room B" in page and "Room C" in page
    one = c.get("/notices/" + public + "/changes/" + first["id"])
    assert "Room B" in one.text and "Room C" not in one.text
    assert c.get("/notices/" + public + "/changes/" + second["id"] + "/flyer.pdf").content.startswith(b"%PDF")
    with db.connect(write=True) as connection:
        connection.execute(
            "UPDATE workspaces SET clock_offset=? WHERE id=?", (12 * 86400, data(c)["workspace_id"])
        )
    assert "ended" in c.get("/notices/" + public + "/changes/" + first["id"]).text.lower()
    assert "Room C" in c.get("/notices/" + public + "/changes/" + second["id"]).text


def test_partial_overlap_cannot_silently_drop_existing_dates(pilot):
    c, *_ = pilot
    configure(c)
    approve(c)
    tick(c)
    second = review(
        c, draft(c, "Replace just one date in this fictional source."), {**FACTS, "dates": ["2026-09-22"]}
    )
    response = c.post(
        "/api/changes/" + second["id"] + "/approve",
        json={"revision": second["revision"], "plan_hash": second["plan_hash"], "replace_current": True},
    )
    assert response.status_code == 409 and "all its dates" in response.text


def delivery_draft(c, channel="email", target="recipient@example.test"):
    configure(c)
    ch = approve(c)
    tick(c)
    response = c.post(
        "/api/delivery/draft",
        json={
            "change_id": ch["id"],
            "channel": channel,
            "target": target,
            "consent": "Fictional recipient consent for this specific update.",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_email_requires_explicit_owner_approval_and_acceptance_is_not_delivery(pilot, monkeypatch):
    c, *_ = pilot
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_FROM", "service@example.test")
    preview = delivery_draft(c)
    sent = []
    monkeypatch.setattr(delivery, "send_email", lambda *args: sent.append(args))
    assert not delivery.process_one() and not sent
    endpoint = "/api/delivery/" + preview["id"] + "/approve"
    assert c.post(endpoint, json={"content_hash": "wrong", "confirmed": True}).status_code == 409
    editor, _ = member(c, "editor")
    assert (
        editor.post(endpoint, json={"content_hash": preview["content_hash"], "confirmed": True}).status_code
        == 403
    )
    assert (
        c.post(endpoint, json={"content_hash": preview["content_hash"], "confirmed": True}).status_code == 200
    )
    assert delivery.process_one() and len(sent) == 1
    assert c.get("/api/delivery/status").json()["deliveries"][0]["state"] == "ACCEPTED"
    assert (
        c.post(endpoint, json={"content_hash": preview["content_hash"], "confirmed": True}).status_code == 200
    )
    assert not delivery.process_one() and len(sent) == 1


def test_ambiguous_email_failure_is_not_automatically_retried(pilot, monkeypatch):
    c, *_ = pilot
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_FROM", "service@example.test")
    preview = delivery_draft(c)
    c.post(
        "/api/delivery/" + preview["id"] + "/approve",
        json={"content_hash": preview["content_hash"], "confirmed": True},
    )

    def fail(*args):
        raise TimeoutError("May have sent already")

    monkeypatch.setattr(delivery, "send_email", fail)
    assert delivery.process_one()
    assert c.get("/api/delivery/status").json()["deliveries"][0]["state"] == "UNKNOWN"
    assert not delivery.process_one()


def test_twilio_acceptance_and_carrier_status_are_distinct(pilot, monkeypatch):
    c, *_ = pilot
    for key, value in [
        ("TWILIO_ACCOUNT_SID", "ACfictional"),
        ("TWILIO_AUTH_TOKEN", "test-only"),
        ("TWILIO_FROM", "+12025550123"),
    ]:
        monkeypatch.setenv(key, value)
    preview = delivery_draft(c, "sms", "+12025550124")
    c.post(
        "/api/delivery/" + preview["id"] + "/approve",
        json={"content_hash": preview["content_hash"], "confirmed": True},
    )
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(201, json={"sid": "SMfictional", "status": "queued"})
        )
    )
    delivery.process_one(client)
    assert c.get("/api/delivery/status").json()["deliveries"][0]["state"] == "ACCEPTED"
    with db.connect(write=True) as connection:
        connection.execute("UPDATE deliveries SET observed_at=0")
    client = httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"status": "delivered"}))
    )
    delivery.poll_sms(client)
    assert c.get("/api/delivery/status").json()["deliveries"][0]["state"] == "DELIVERED"


def test_encrypted_scheduled_backup_can_be_restored_and_tamper_is_rejected(pilot, monkeypatch, tmp_path):
    c, *_ = pilot
    monkeypatch.setenv("BACKUP_DIRECTORY", str(tmp_path / "backups"))
    operations.maintenance()
    backup = next((tmp_path / "backups").glob("*.signal-backup"))
    assert b"SQLite format" not in backup.read_bytes()[:100]
    recovered = tmp_path / "restored.sqlite"
    operations.decrypt_backup(backup, recovered)
    import sqlite3

    with sqlite3.connect(recovered) as connection:
        assert connection.execute("SELECT count(*) FROM users").fetchone()[0] == 1
    with pytest.raises(FileExistsError):
        operations.decrypt_backup(backup, recovered)
    assert recovered.read_bytes().startswith(b"SQLite format")
    corrupted = tmp_path / "bad-backup"
    content = bytearray(backup.read_bytes())
    content[-1] ^= 1
    corrupted.write_bytes(content)
    with pytest.raises(InvalidTag):
        operations.decrypt_backup(corrupted, tmp_path / "bad.sqlite")
    assert not (tmp_path / "bad.sqlite").exists()
    assert c.get("/api/operations").json()["backup"]["state"] == "OK"


def test_actual_scanned_pdf_ocr_preserves_original_and_extracts_source(client):
    import shutil

    if not shutil.which("tesseract"):
        pytest.skip("Tesseract is installed in the production image and CI OCR check.")
    image = Image.new("RGB", (1600, 700), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=42)
    for y, text in enumerate(
        ["Digital Basics community class", "September 15, 2026 at 6 PM", "Room B, 200 Sample Street"]
    ):
        draw.text((60, 80 + y * 90), text, font=font, fill="black")
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(800, 350))
    pdf.drawImage(ImageReader(image), 0, 0, width=800, height=350)
    pdf.save()
    result = client.post(
        "/api/documents", content=buffer.getvalue(), headers={"Content-Type": "application/pdf"}
    )
    assert result.status_code == 200, result.text
    assert "Digital Basics" in result.json()["source"]
    assert "200 Sample Street" in result.json()["source"]
    assert result.json()["ocr_pages"] == [1]
    assert client.get("/api/documents/" + result.json()["id"]).content == buffer.getvalue()


@pytest.mark.parametrize("changed_after_preview", [False, True])
def test_wordpress_dedicated_page_preview_write_and_public_readback(
    pilot, monkeypatch, tmp_path, changed_after_preview
):
    c, org, _, ws = pilot
    config = [
        {
            "id": "library-page",
            "org_id": org,
            "workspace_id": ws,
            "label": "Library notices",
            "api_origin": "https://library.example.test",
            "public_url": "https://library.example.test/notices",
            "page_id": 42,
            "username_env": "WP_TEST_USER",
            "password_env": "WP_TEST_PASSWORD",
        }
    ]
    path = tmp_path / "connectors.json"
    path.write_text(json.dumps(config))
    monkeypatch.setenv("SERVICESIGNAL_CONNECTORS_FILE", str(path))
    monkeypatch.setenv("WP_TEST_USER", "test-user")
    monkeypatch.setenv("WP_TEST_PASSWORD", "test-app-password")
    remote = {"html": "Previous dedicated notice content", "writes": 0}
    original = httpx.Client

    def handle(request):
        if "/wp-json/" in request.url.path:
            if request.method == "POST":
                remote["writes"] += 1
                remote["html"] = json.loads(request.content)["content"]
            return httpx.Response(200, json={"content": {"raw": remote["html"]}})
        return httpx.Response(200, text=remote["html"])

    monkeypatch.setattr(
        delivery.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handle))
    )
    preview = delivery_draft(c, "wordpress", "library-page")
    assert preview["body"]["previous_content"] == "Previous dedicated notice content"
    assert remote["writes"] == 0
    if changed_after_preview:
        remote["html"] = "Someone edited the page after preview."
    c.post(
        "/api/delivery/" + preview["id"] + "/approve",
        json={"content_hash": preview["content_hash"], "confirmed": True},
    )
    assert delivery.process_one()
    result = c.get("/api/delivery/status").json()["deliveries"][0]
    assert result["state"] == ("NEEDS_OWNER" if changed_after_preview else "VERIFIED")
    assert remote["writes"] == (0 if changed_after_preview else 1)

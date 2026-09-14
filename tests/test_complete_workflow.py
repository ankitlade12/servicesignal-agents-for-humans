import io
import json

import httpx
import pytest
from pypdf import PdfReader

from app import db, worker
from app.domain import PROGRAM, visible_facts
from app.notices import FactParser
from test_workflow import FACTS, action, approve, data, review, tick
from test_accounts import configure, pilot as pilot


def test_spanish_requires_explicit_program_enablement(client):
    assert (
        client.post(
            "/api/program", json={**PROGRAM, "contact": "Call the desk", "spanish_enabled": True}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/program",
            json={
                **PROGRAM,
                "contact": "Call the desk",
                "contact_es": "Llame a recepción.",
                "spanish_enabled": True,
            },
        ).status_code
        == 200
    )
    ready = review(client)
    assert ready["plan_context"]["languages"] == ["en", "es"]
    raw = client.get(f"/api/changes/{ready['id']}/preview.pdf?revision={ready['revision']}&lang=es").content
    assert "NO PUBLICADA" in "".join(p.extract_text() for p in PdfReader(io.BytesIO(raw)).pages)
    approve(client, ready)
    tick(client)
    assert action(client, "page")["state"] == "VERIFIED"
    assert set(json.loads(action(client, "page")["locale_evidence"])) == {"en", "es"}
    d = data(client)
    page = client.get("/notices/" + d["public_id"] + "?lang=es")
    assert '<html lang="es">' in page.text
    parser = FactParser()
    parser.feed(page.text)
    assert parser.facts == visible_facts(d["publication"], "es")
    assert "15 de septiembre de 2026" in page.text
    assert "Llame a recepción." in page.text
    raw = client.get("/notices/" + d["public_id"] + "/flyer.pdf?lang=es").content
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(raw)).pages)
    assert "200 Sample Street" in text and "Llame a recepción." in text


def test_unapproved_spanish_not_exposed(client):
    approve(client)
    tick(client)
    public = data(client)["public_id"]
    assert client.get("/notices/" + public + "?lang=es").status_code == 404
    assert client.get("/notices/" + public + "/flyer.pdf?lang=es").status_code == 404


def test_spanish_drift_cannot_be_marked_verified(client):
    client.post("/api/program", json={**PROGRAM, "spanish_enabled": True})
    approve(client)

    def handle(request):
        if request.method == "POST":
            result = client.post(str(request.url), headers=dict(request.headers))
        else:
            result = client.get(str(request.url))
        body = result.content
        if request.method == "GET" and request.url.params.get("lang") == "es":
            body = body.replace(b"Room B", b"Room Z")
        return httpx.Response(result.status_code, content=body, headers=dict(result.headers))

    worker.process(
        worker.claim(), httpx.Client(base_url="http://testserver", transport=httpx.MockTransport(handle))
    )
    assert action(client, "page")["state"] == "NEEDS_OWNER"
    assert "es: room" in action(client, "page")["detail"]


def test_inventory_is_bound_to_review_revision(client):
    inventory = {
        **data(client)["inventory"],
        "partner_name": "County directory",
        "partner_owner": "Directory editor",
        "partner_url": "https://example.org/program",
        "print_owner": "Reception",
        "print_notes": "Front door and lobby",
    }
    assert client.post("/api/inventory", json=inventory).status_code == 200
    ready = review(client)
    assert ready["plan_context"]["inventory"] == inventory
    client.post("/api/inventory", json={**inventory, "partner_owner": "New owner"})
    approved = approve(client, ready)
    assert approved["plan_context"]["inventory"]["partner_owner"] == "Directory editor"
    assert approved["plan_hash"] == ready["plan_hash"]


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "http://example.org", "https://user:secret@example.org"]
)
def test_inventory_rejects_unsafe_links(client, url):
    assert (
        client.post("/api/inventory", json={**data(client)["inventory"], "partner_url": url}).status_code
        == 422
    )


@pytest.mark.parametrize("arrangement", ["extend", "restore", "new"])
def test_followup_does_not_publish_without_fresh_approval(client, arrangement):
    original = approve(client)
    tick(client)
    public_before = data(client)["publication"]
    endpoint = f"/api/changes/{original['id']}/follow-up"
    body = {"arrangement": arrangement, "dates": ["2026-09-29"]}
    result = client.post(endpoint, json=body)
    assert result.status_code == 200, result.text
    next = result.json()
    assert next["state"] == "NEEDS_CLARIFICATION" and next["approved_at"] is None
    assert client.post(endpoint, json=body).json()["id"] == next["id"]
    assert data(client)["publication"] == public_before
    assert next["proposal"]["location"] == (
        "200 Sample Street"
        if arrangement == "extend"
        else "100 Example Avenue"
        if arrangement == "restore"
        else ""
    )
    ready = review(client, next, {**FACTS, "dates": ["2026-09-29"]})
    approve(client, ready, replace=True)
    tick(client)
    assert data(client)["publication"]["facts"]["dates"] == ["2026-09-29"]


def test_pilot_baseline_edits_cannot_change_approved_notice(pilot):
    c, *_ = pilot
    configure(c)
    approve(c)
    tick(c)
    old = data(c)["publication"]
    updated = {
        **PROGRAM,
        "organization": "Test Library",
        "location": "300 New Baseline Road",
        "room": "Room C",
    }
    assert c.post("/api/program", json=updated).status_code == 200
    assert data(c)["publication"] == old
    with db.connect(write=True) as connection:
        connection.execute("UPDATE jobs SET due_at=0 WHERE kind='verify'")
    tick(c)
    assert action(c, "page")["state"] == "VERIFIED"
    assert "200 Sample Street" in c.get("/notices/" + data(c)["public_id"]).text

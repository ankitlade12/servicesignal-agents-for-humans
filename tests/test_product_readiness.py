import io
import time

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from app import db, worker
from app.domain import PROGRAM, FALLBACK, Facts
from app.main import app
from app.notices import FactParser
from test_workflow import FACTS, approve, data, draft, review, tick, action


def pdf(text="Community class moves on September 15, 2026.", pages=1):
    out = io.BytesIO()
    document = canvas.Canvas(out)
    for _ in range(pages):
        document.drawString(50, 700, text)
        document.showPage()
    document.save()
    return out.getvalue()


def upload(client, raw):
    return client.post("/api/documents", content=raw, headers={"Content-Type": "application/pdf"})


def test_custom_program_publication_and_scope(client):
    baseline = {
        **PROGRAM,
        "name": "Garden Club",
        "organization": "Example Library",
        "weekdays": [2],
        "timezone": "America/New_York",
        "schedule": "Wednesdays, 6–8 p.m.",
        "contact": "Ask at the library desk.",
    }
    assert client.post("/api/program", json=baseline).status_code == 200
    ch = draft(client, "Garden Club moves on September 16, 2026 to 200 Sample Street, Room B. Same time.")
    assert ch["proposal"]["program"] == "Garden Club"
    assert ch["state"] == "NEEDS_CLARIFICATION"  # fixture never invents custom extraction
    facts = {**FACTS, "program": "Garden Club", "timezone": "America/New_York", "dates": ["2026-09-16"]}
    ready = review(client, ch, facts)
    assert client.post("/api/program", json=PROGRAM).status_code == 409
    approve(client, ready)
    tick(client)
    assert action(client, "page")["state"] == "VERIFIED"
    page = client.get("/notices/" + data(client)["public_id"]).text
    parser = FactParser()
    parser.feed(page)
    assert parser.facts["program"] == "Garden Club"
    assert parser.facts["organization"] == "Example Library"
    assert parser.facts["contact"] == baseline["contact"]
    assert "Maple Community Center" not in page
    raw = client.get("/notices/" + data(client)["public_id"] + "/flyer.pdf").content
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(raw)).pages)
    assert "Garden Club" in text and baseline["contact"] in text


@pytest.mark.parametrize(
    "override", [{"program": "Other class"}, {"timezone": "UTC"}, {"dates": ["2026-09-16"]}]
)
def test_workspace_context_rejects_wrong_scope(client, override):
    ch = draft(client)
    res = client.post(
        f"/api/changes/{ch['id']}/review",
        json={"revision": ch["revision"], "confirmed": True, "facts": {**FACTS, **override}},
    )
    assert res.status_code == 422
    assert data(client)["publication"] is None


@pytest.mark.parametrize(
    "override",
    [
        {"timezone": "Invented/Zone"},
        {"weekdays": []},
        {"weekdays": [7]},
        {"end_time": "17:00"},
        {"organization": "bad\nname"},
    ],
)
def test_invalid_program(client, override):
    assert client.post("/api/program", json={**PROGRAM, **override}).status_code == 422


@pytest.mark.parametrize(
    "day,start,end", [("2026-03-08", "02:15", "03:15"), ("2026-11-01", "01:15", "02:15")]
)
def test_dst_gap_and_repeated_hour_require_unambiguous_time(day, start, end):
    with pytest.raises(ValidationError):
        Facts.model_validate({**FACTS, "dates": [day], "start_time": start, "end_time": end})


def test_pdf_preservation_dedup_and_private_intake(client):
    raw = pdf(pages=2)
    result = upload(client, raw)
    assert result.status_code == 200, result.text
    doc = result.json()
    assert doc["pages"] == 2 and "[Source page 2]" in doc["source"]
    assert upload(client, raw).json()["id"] == doc["id"]
    assert client.get("/api/documents/" + doc["id"]).content == raw
    ch = client.post("/api/changes", json={"source": doc["source"], "document_id": doc["id"]}).json()
    assert ch["metrics"]["document_id"] == doc["id"]
    assert (
        client.post(
            "/api/changes", json={"source": doc["source"] + " changed", "document_id": doc["id"]}
        ).status_code
        == 422
    )
    with TestClient(app, headers={"X-ServiceSignal": "1"}) as other:
        other.post("/api/session", json={})
        assert other.get("/api/documents/" + doc["id"]).status_code == 404
        assert (
            other.post("/api/changes", json={"source": doc["source"], "document_id": doc["id"]}).status_code
            == 422
        )
    assert doc["source"] not in client.get("/notices/" + data(client)["public_id"]).text
    client.post("/api/demo/reset", json={})
    with db.connect() as c:
        assert c.execute("SELECT count(*) FROM documents").fetchone()[0] == 0


@pytest.mark.parametrize(
    "raw,status",
    [(b"not a PDF", 422), (pdf(pages=4), 422), (pdf(text=""), 422), (b"%PDF-" + b"x" * (5 * 1024**2), 413)],
)
def test_unsupported_pdf_rejected(client, raw, status):
    assert upload(client, raw).status_code == status
    with db.connect() as c:
        assert c.execute("SELECT count(*) FROM documents").fetchone()[0] == 0


def test_encrypted_pdf_rejected(client):
    out = io.BytesIO()
    document = PdfWriter(clone_from=io.BytesIO(pdf()))
    document.encrypt("secret")
    document.write(out)
    assert upload(client, out.getvalue()).status_code == 422


def test_expiry_protects_residents_without_worker(client):
    ch = approve(client)
    tick(client)
    public_id = data(client)["public_id"]
    client.post("/api/demo/clock", json={"change_id": ch["id"], "stage": "expiry"})
    # Deliberately do not execute the expiry job.
    assert not data(client)["publication"]["expired"]
    page = client.get("/notices/" + public_id).text
    assert FALLBACK in page and "This arrangement has ended" in page
    raw = client.get("/notices/" + public_id + "/flyer.pdf").content
    assert FALLBACK in " ".join("".join(p.extract_text() for p in PdfReader(io.BytesIO(raw)).pages).split())
    tick(client)
    assert data(client)["publication"]["expired"]
    assert action(client, "page")["state"] == "VERIFIED"


def test_worker_readiness_detects_stopped_worker(client):
    assert client.get("/api/ready").status_code == 503
    worker.claim()
    assert client.get("/api/ready").status_code == 200
    with db.connect(write=True) as c:
        c.execute("UPDATE settings SET value=? WHERE key='worker_heartbeat'", (str(time.time() - 91),))
    assert client.get("/api/ready").status_code == 503


def test_preview_is_private_revision_bound_and_does_not_publish(client):
    ready = review(client)
    url = f"/api/changes/{ready['id']}/preview.pdf?revision={ready['revision']}"
    response = client.get(url)
    assert response.status_code == 200
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(response.content)).pages)
    assert "NOT PUBLISHED" in text and FACTS["location"] in text and FACTS["room"] in text
    assert data(client)["publication"] is None
    with TestClient(app, headers={"X-ServiceSignal": "1"}) as other:
        other.post("/api/session", json={})
        assert other.get(url).status_code == 404
    review(client, ready, {**FACTS, "room": "Room C"})
    assert client.get(url).status_code == 409


def test_pdf_evidence_has_page_and_line():
    from app.agent import evidence_locations

    source = "[Source page 1]\nFirst page\n\n[Source page 2]\nNotice\nRoom B at 200 Sample Street."
    locations = evidence_locations(source, {"room": "Room B", "invented": "not present"})
    assert locations == {"room": {"quote": "Room B", "page": 2, "line": 2}}

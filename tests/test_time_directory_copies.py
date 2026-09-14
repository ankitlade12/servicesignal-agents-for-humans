import io
import socket
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from pypdf import PdfReader

from app import db, directory, external_copies
from app.domain import Facts, fact_payload, visible_facts
from app.notices import FactParser, flyer_pdf, render_notice
from test_accounts import configure, member, pilot as pilot
from test_workflow import FACTS, approve, data, review, tick


def test_overnight_expiry_public_html_pdf_and_offsets():
    f = Facts.model_validate(
        {**FACTS, "dates": ["2026-09-15"], "start_time": "22:30", "end_time": "02:00", "end_day_offset": 1}
    )
    assert f.expires_at() == datetime(2026, 9, 16, 7, tzinfo=UTC).timestamp()
    assert f.occurrences()[0]["end"] == "2026-09-16T02:00:00-05:00"
    payload = fact_payload(f.model_dump(mode="json"), "sample", 1, 0)
    html = render_notice(payload, "sample")
    parser = FactParser()
    parser.feed(html)
    assert parser.facts == visible_facts(payload)
    text = " ".join(
        p.extract_text() for p in PdfReader(io.BytesIO(flyer_pdf(payload, "https://example.org"))).pages
    )
    assert "2026-09-16T02:00:00-05:00" in text


def test_fold_choices_and_gaps_are_distinct():
    value = {**FACTS, "dates": ["2026-11-01"], "start_time": "01:15", "end_time": "01:45"}
    with pytest.raises(ValidationError, match="repeated hour"):
        Facts.model_validate(value)
    early = Facts.model_validate({**value, "time_choices": {"2026-11-01": {"start_fold": 0, "end_fold": 0}}})
    late = Facts.model_validate({**value, "time_choices": {"2026-11-01": {"start_fold": 1, "end_fold": 1}}})
    assert late.expires_at() - early.expires_at() == 3600
    backwards = Facts.model_validate(
        {
            **value,
            "start_time": "01:45",
            "end_time": "01:15",
            "time_choices": {"2026-11-01": {"start_fold": 0, "end_fold": 1}},
        }
    )
    assert (
        backwards.session_bounds(backwards.dates[0])[1].timestamp()
        - backwards.session_bounds(backwards.dates[0])[0].timestamp()
        == 1800
    )
    for fold in (None, 0, 1):
        with pytest.raises(ValidationError, match="does not exist"):
            Facts.model_validate(
                {
                    **FACTS,
                    "dates": ["2027-03-14"],
                    "start_time": "02:15",
                    "end_time": "03:30",
                    "time_choices": {"2027-03-14": {"start_fold": fold}},
                }
            )
    with pytest.raises(ValidationError, match="not a repeated hour"):
        Facts.model_validate({**FACTS, "time_choices": {"2026-09-15": {"start_fold": 1}}})
    with pytest.raises(ValidationError, match="affected session"):
        Facts.model_validate({**FACTS, "time_choices": {"2026-10-01": {"start_fold": 1}}})


def test_overnight_crosses_transition_with_correct_end_fold():
    f = Facts.model_validate(
        {
            **FACTS,
            "dates": ["2026-10-31"],
            "start_time": "22:00",
            "end_time": "01:30",
            "end_day_offset": 1,
            "time_choices": {"2026-10-31": {"end_fold": 1}},
        }
    )
    start, end = f.session_bounds(f.dates[0])
    assert end.timestamp() - start.timestamp() == 4.5 * 3600
    assert end.isoformat() == "2026-11-01T01:30:00-06:00"


def test_overnight_publication_stays_active_until_next_day(pilot, monkeypatch):
    c, *_ = pilot
    configure(c)
    ch = review(
        c,
        facts={
            **FACTS,
            "dates": ["2026-09-15"],
            "start_time": "23:00",
            "end_time": "01:00",
            "end_day_offset": 1,
        },
    )
    approve(c, ch)
    tick(c)
    url = "/notices/" + data(c)["public_id"] + "/changes/" + ch["id"]
    monkeypatch.setattr("time.time", lambda: datetime(2026, 9, 16, 5, 30, tzinfo=UTC).timestamp())
    assert "This temporary arrangement has ended" not in c.get(url).text
    monkeypatch.setattr("time.time", lambda: datetime(2026, 9, 16, 6, 1, tzinfo=UTC).timestamp())
    assert "This temporary arrangement has ended" in c.get(url).text


def record():
    return {
        "id": str(uuid4()),
        "name": "Community Coding",
        "status": "active",
        "organization": {"id": str(uuid4()), "name": "External Library", "description": "Community programs"},
        "service_at_locations": [
            {
                "id": str(uuid4()),
                "location": {
                    "id": str(uuid4()),
                    "location_type": "physical",
                    "name": "Room Q",
                    "description": "20 Sample Avenue",
                },
            }
        ],
        "schedules": [
            {
                "id": str(uuid4()),
                "description": "Tuesday evening",
                "freq": "WEEKLY",
                "byday": "TU",
                "opens_at": "18:00-05:00",
                "closes_at": "20:00-05:00",
            }
        ],
        "eligibility_description": "Adults",
        "alert": "An unconfirmed external alert",
    }


def test_hsds_export_validates_and_contains_no_private_sources(pilot):
    c, *_ = pilot
    assert c.get("/api/directory/export").status_code == 409
    configure(c)
    ch = approve(c)
    tick(c)
    result = c.get("/api/directory/export")
    assert result.status_code == 200
    exported = result.json()
    directory.validate_record(exported)
    assert exported["id"] == c.get("/api/directory/export").json()["id"]
    assert "2026-09-15T18:00:00-05:00" in exported["alert"]
    assert (
        "owner@example.test" not in result.text
        and "source_hash" not in result.text
        and ch["source"] not in result.text
    )


def test_hsds_import_review_idempotence_source_and_isolation(pilot):
    c, org, _, _ = pilot
    configure(c)
    original = record()
    preview = c.post("/api/directory/preview", json={"services": [original]})
    assert preview.status_code == 200, preview.text
    preview = preview.json()
    p = preview["services"][0]["program"]
    assert p["weekdays"] == [1] and p["start_time"] == "18:00"
    assert p["organization"] == "Test Library"
    endpoint = "/api/directory/imports/" + preview["id"] + "/confirm"
    assert c.post(endpoint, json={"index": 0, "program": p, "confirmed": False}).status_code == 422
    imported = c.post(endpoint, json={"index": 0, "program": p, "confirmed": True})
    assert imported.status_code == 200, imported.text
    new_id = imported.json()["workspace_id"]
    assert c.post(endpoint, json={"index": 0, "program": p, "confirmed": True}).json() == {
        "workspace_id": new_id,
        "created": False,
    }
    c.post("/api/account/programs/" + new_id + "/select", json={})
    assert data(c)["program"]["configured"] is False
    assert c.get("/api/directory/source").json() == original
    assert c.get("/notices/" + data(c)["public_id"]).status_code == 404
    with db.connect() as connection:
        assert (
            connection.execute("SELECT count(*) FROM changes WHERE workspace_id=?", (new_id,)).fetchone()[0]
            == 0
        )
    # Preview is bound to the old workspace and cannot be replayed from this one.
    assert c.post(endpoint, json={"index": 0, "program": p, "confirmed": True}).status_code == 404


def test_hsds_rejects_invalid_duplicate_large_and_non_owner(pilot):
    c, *_ = pilot
    configure(c)
    assert c.post("/api/directory/preview", json={"name": "Missing id"}).status_code == 422
    r = record()
    assert c.post("/api/directory/preview", json=[r, r]).status_code == 422
    assert c.post("/api/directory/preview", content=b" " * (2 * 1024**2 + 1)).status_code == 413
    viewer, _ = member(c, "viewer")
    assert viewer.post("/api/directory/preview", json=r).status_code == 403
    editor, _ = member(c, "editor")
    assert editor.post("/api/directory/preview", json=r).status_code == 403


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://user:pass@example.com",
        "https://example.com:8443",
        "https://localhost",
        "https://127.0.0.1",
        "https://[::1]",
        "https://169.254.169.254",
        "https://example.com/\\secret",
    ],
)
def test_external_targets_reject_private_and_unsafe(url, monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
    )
    with pytest.raises(ValueError):
        external_copies.public_target(url)


def test_dns_mixed_addresses_and_rebinding_are_blocked(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(2, 1, 6, "", ("8.8.8.8", 443)), (2, 1, 6, "", ("10.0.0.1", 443))],
    )
    with pytest.raises(ValueError):
        external_copies.public_target("https://example.org")
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("8.8.8.8", 443))])
    host, address, url = external_copies.public_target("https://example.org/notice#part")
    assert (host, address, url) == ("example.org", "8.8.8.8", "https://example.org/notice")
    connections = []

    class Raw:
        def close(self):
            pass

    class TLS:
        def wrap_socket(self, raw, server_hostname):
            connections.append(server_hostname)
            return raw

    monkeypatch.setattr(
        socket, "create_connection", lambda target, timeout: connections.append(target) or Raw()
    )
    conn = external_copies.PinnedHTTPS(host, address)
    conn._context = TLS()
    conn.connect()
    assert connections == [("8.8.8.8", 443), "example.org"]


def test_external_html_ignores_hidden_scripts_and_reports_text_only():
    raw = b"<html><head><title>Room B</title></head><body><script>Room B</script><div hidden>Room B</div><p>Digital Basics at 200 Sample Street Room Q</p></body></html>"
    text, ocr = external_copies.extract_copy(raw, "text/html")
    assert "Room B" not in text and not ocr
    comparison = external_copies.compare_text(text, FACTS)
    assert comparison["state"] == "REVIEW_REQUIRED"
    assert next(f for f in comparison["fields"] if f["field"] == "room")["state"] == "NOT_FOUND"
    assert (
        "No website was changed" in comparison["limitations"]
        or "no website was changed" in comparison["limitations"]
    )
    text = "Digital Basics 200 Sample Street Room B 18:00 20:00 America/Chicago 2026-09-15 2026-09-22"
    assert external_copies.compare_text(text, FACTS)["state"] == "TEXT_MATCH"


def test_redirect_to_private_is_rejected_before_second_connection(monkeypatch):
    calls = []

    def resolve(host, *args, **kwargs):
        return [(2, 1, 6, "", ("127.0.0.1" if host == "private.example" else "8.8.8.8", 443))]

    class Response:
        status = 302

        def getheader(self, key, default=None):
            return "https://private.example/secret" if key == "Location" else default

    class Connection:
        def __init__(self, host, address):
            calls.append((host, address))

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(external_copies, "PinnedHTTPS", Connection)
    with pytest.raises(ValueError, match="Private"):
        external_copies.fetch_public("https://public.example/notice")
    assert calls == [("public.example", "8.8.8.8")]


def test_copy_inspection_records_revision_without_marking_partner_verified(pilot, monkeypatch):
    import json
    from app import main

    c, *_ = pilot
    configure(c)
    change = approve(c)
    tick(c)
    text = "Digital Basics 200 Sample Street Room B 18:00 20:00 America/Chicago 2026-09-15 2026-09-22"
    output = {
        "url": "https://public.example/notice",
        "text": text,
        "media_type": "text/html",
        "sha256": "a" * 64,
        "bytes": 100,
        "ocr": False,
    }

    class Process:
        returncode = 0

        async def communicate(self, body):
            return json.dumps(output).encode(), b""

    async def spawn(*args, **kwargs):
        return Process()

    monkeypatch.setattr(main.asyncio, "create_subprocess_exec", spawn)
    url = "/api/changes/" + change["id"] + "/inspect"
    body = {"url": "https://public.example/notice", "revision": change["revision"], "confirmed": True}
    assert c.post(url, json={**body, "confirmed": False}).status_code == 422
    assert c.post(url, json={**body, "revision": 1}).status_code == 409
    result = c.post(url, json=body)
    assert result.status_code == 200, result.text
    assert result.json()["state"] == "TEXT_MATCH"
    workspace = data(c)
    assert len(workspace["external_checks"]) == 1
    assert (
        next(a for a in workspace["changes"][0]["actions"] if a["destination"] == "partner")["state"]
        == "NEEDS_OWNER"
    )
    viewer, _ = member(c, "viewer")
    assert viewer.post(url, json=body).status_code == 403
    # An unrelated demo session cannot inspect pilot changes.
    c.post("/api/account/logout", json={})
    assert c.post(url, json=body).status_code == 401


def test_fold_choice_changes_approval_hash(pilot):
    c, *_ = pilot
    from app.domain import PROGRAM

    assert (
        c.post("/api/program", json={**PROGRAM, "organization": "Test Library", "weekdays": [6]}).status_code
        == 200
    )
    facts = {
        **FACTS,
        "dates": ["2026-11-01"],
        "start_time": "01:15",
        "end_time": "01:45",
        "time_choices": {"2026-11-01": {"start_fold": 0, "end_fold": 0}},
    }
    first = review(c, facts=facts)
    later = review(c, first, {**facts, "time_choices": {"2026-11-01": {"start_fold": 1, "end_fold": 1}}})
    assert first["plan_hash"] != later["plan_hash"]
    response = c.post(
        "/api/changes/" + first["id"] + "/approve",
        json={"revision": first["revision"], "plan_hash": first["plan_hash"]},
    )
    assert response.status_code == 409
    preview = c.post("/api/session-times", json=later["facts"])
    assert preview.status_code == 200 and preview.json()["occurrences"][0]["end"].endswith("-06:00")


def test_overnight_overlap_on_different_start_dates_requires_complete_replacement(pilot):
    c, *_ = pilot
    from app.domain import PROGRAM

    assert (
        c.post(
            "/api/program", json={**PROGRAM, "organization": "Test Library", "weekdays": [1, 2]}
        ).status_code
        == 200
    )
    old = review(
        c,
        facts={
            **FACTS,
            "dates": ["2026-09-15"],
            "start_time": "23:00",
            "end_time": "02:00",
            "end_day_offset": 1,
        },
    )
    approve(c, old)
    draft = c.post(
        "/api/changes", json={"source": "A separate fictional session begins early on Wednesday."}
    ).json()
    new = review(
        c, draft, facts={**FACTS, "dates": ["2026-09-16"], "start_time": "01:00", "end_time": "03:00"}
    )
    response = c.post(
        "/api/changes/" + new["id"] + "/approve",
        json={"revision": new["revision"], "plan_hash": new["plan_hash"], "replace_current": True},
    )
    assert response.status_code == 409 and "Include all" in response.text

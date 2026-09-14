import time

import pytest
from fastapi.testclient import TestClient

from app import accounts, db, service
from app.domain import PROGRAM
from app.main import app
from test_workflow import data, review, approve, tick, action

PASSWORD = "fictional-test-password-only"


@pytest.fixture
def pilot(client, monkeypatch):
    monkeypatch.setenv("SERVICESIGNAL_MODE", "pilot")
    org, user, ws = accounts.bootstrap("Test Library", "owner@example.test", "Owner", PASSWORD)
    assert (
        client.post(
            "/api/account/login", json={"email": "owner@example.test", "password": PASSWORD}
        ).status_code
        == 200
    )
    yield client, org, user, ws


def configure(c):
    assert c.post("/api/program", json={**PROGRAM, "organization": "Test Library"}).status_code == 200


def member(owner, role):
    email = role + "@example.test"
    result = owner.post("/api/account/invitations", json={"email": email, "role": role})
    assert result.status_code == 200, result.text
    token = result.json()["invite_path"].split("=")[1]
    c = TestClient(app, headers={"X-ServiceSignal": "1"})
    response = c.post(
        "/api/account/accept",
        json={"token": token, "email": email, "password": PASSWORD, "name": role.title()},
    )
    assert response.status_code == 200, response.text
    assert c.post("/api/account/login", json={"email": email, "password": PASSWORD}).status_code == 200
    return c, token


def test_pilot_requires_login_and_confirmed_setup(pilot):
    c, *_ = pilot
    assert data(c)["clock_offset"] == 0
    assert c.get("/notices/" + data(c)["public_id"]).status_code == 404
    assert c.post("/api/changes", json={"source": "A sufficiently long source"}).status_code == 409
    c.post("/api/account/logout", json={})
    assert c.post("/api/session", json={}).status_code == 401
    assert c.get("/api/workspace").status_code == 401


def test_owner_publication_records_named_authority_and_stable_link(pilot, monkeypatch):
    c, _, owner, _ = pilot
    configure(c)
    ch = approve(c)
    tick(c)
    current = data(c)["changes"][0]
    assert current["created_by"]["id"] == owner
    assert current["confirmed_by"]["id"] == owner
    assert current["approved_by"]["id"] == owner
    assert action(c, "page")["state"] == "VERIFIED"
    public = data(c)["public_id"]
    page = c.get("/notices/" + public).text
    assert "FICTIONAL" not in page and "demo coordinator" not in page
    assert "owner@example.test" not in page
    assert c.post("/api/demo/reset", json={}).status_code == 403
    assert c.post("/api/demo/clock", json={"change_id": ch["id"], "stage": "expiry"}).status_code == 403
    assert c.post(f"/api/changes/{ch['id']}/partner/publish", json={}).status_code == 403
    c.post("/api/account/logout", json={})
    future = time.time() + 14 * 86400
    monkeypatch.setattr(time, "time", lambda: future)
    assert c.get("/notices/" + public).status_code == 200


def test_editor_can_prepare_but_only_owner_approves(pilot):
    c, *_ = pilot
    configure(c)
    editor, _ = member(c, "editor")
    ready = review(editor)
    response = editor.post(
        f"/api/changes/{ready['id']}/approve",
        json={"revision": ready["revision"], "plan_hash": ready["plan_hash"]},
    )
    assert response.status_code == 403
    assert editor.post("/api/program", json=PROGRAM).status_code == 403
    assert editor.get("/api/account/team").status_code == 403
    with pytest.raises(Exception) as error:
        service.approve(data(c)["workspace_id"], ready["id"], ready["revision"], ready["plan_hash"])
    assert error.value.status_code == 403
    approve(c, ready)
    editor.close()


def test_viewer_cannot_mutate_or_issue_invites(pilot):
    c, *_ = pilot
    configure(c)
    viewer, _ = member(c, "viewer")
    assert viewer.get("/api/workspace").status_code == 200
    assert viewer.post("/api/changes", json={"source": "Some program change message."}).status_code == 403
    assert (
        viewer.post(
            "/api/account/invitations", json={"email": "x@example.test", "role": "editor"}
        ).status_code
        == 403
    )
    viewer.close()


def test_invitation_is_single_use_and_bound_to_email(pilot):
    c, *_ = pilot
    invitation = c.post(
        "/api/account/invitations", json={"email": "member@example.test", "role": "editor"}
    ).json()
    token = invitation["invite_path"].split("=")[1]
    body = {"token": token, "email": "wrong@example.test", "name": "Member", "password": PASSWORD}
    assert c.post("/api/account/accept", json=body).status_code == 400
    body["email"] = "member@example.test"
    assert c.post("/api/account/accept", json=body).status_code == 200
    assert c.post("/api/account/accept", json=body).status_code == 400
    with db.connect() as connection:
        assert connection.execute("SELECT token_hash FROM invitations").fetchone()[0] != token


def test_member_revocation_invalidates_all_sessions(pilot):
    c, *_ = pilot
    configure(c)
    editor, _ = member(c, "editor")
    member_id = next(m["id"] for m in c.get("/api/account/team").json()["members"] if m["role"] == "editor")
    assert c.post("/api/account/members/" + member_id + "/deactivate", json={}).status_code == 200
    assert editor.get("/api/workspace").status_code == 401
    assert (
        editor.post(
            "/api/account/login", json={"email": "editor@example.test", "password": PASSWORD}
        ).status_code
        == 401
    )
    editor.close()


def test_password_change_revokes_sessions(pilot):
    c, *_ = pilot
    assert (
        c.post(
            "/api/account/password",
            json={"current_password": "wrong-password", "new_password": "new-test-password"},
        ).status_code
        == 401
    )
    assert (
        c.post(
            "/api/account/password", json={"current_password": PASSWORD, "new_password": "new-test-password"}
        ).status_code
        == 200
    )
    assert c.get("/api/workspace").status_code == 401
    assert (
        c.post("/api/account/login", json={"email": "owner@example.test", "password": PASSWORD}).status_code
        == 401
    )
    assert (
        c.post(
            "/api/account/login", json={"email": "owner@example.test", "password": "new-test-password"}
        ).status_code
        == 200
    )


def test_multiple_programs_and_tenant_isolation(pilot):
    c, org, _, first = pilot
    configure(c)
    result = c.post(
        "/api/account/programs", json={**PROGRAM, "name": "Second class", "organization": "Test Library"}
    )
    assert result.status_code == 200
    second = result.json()["workspace_id"]
    assert data(c)["program"]["name"] == "Second class"
    assert len(data(c)["programs"]) == 2
    assert c.post("/api/account/programs/" + first + "/select", json={}).status_code == 200
    assert data(c)["program"]["name"] == "Digital Basics"
    _, _, other = accounts.bootstrap("Other Library", "other@example.test", "Other owner", PASSWORD)
    assert c.post("/api/account/programs/" + other + "/select", json={}).status_code == 404
    assert second != first


def test_demo_cleanup_cannot_delete_pilot_records(pilot, monkeypatch):
    c, org, *_ = pilot
    with db.connect(write=True) as connection:
        connection.execute(
            "UPDATE workspaces SET created_at=? WHERE org_id=?", (time.time() - 30 * 86400, org)
        )
    monkeypatch.setenv("SERVICESIGNAL_MODE", "demo")
    anonymous = TestClient(app, headers={"X-ServiceSignal": "1"})
    anonymous.post("/api/session", json={})
    with db.connect() as connection:
        assert connection.execute("SELECT count(*) FROM workspaces WHERE org_id=?", (org,)).fetchone()[0] == 1
    anonymous.close()


def test_login_limit_and_secure_cookie(pilot, monkeypatch):
    c, *_ = pilot
    monkeypatch.setenv("COOKIE_SECURE", "1")
    response = c.post("/api/account/login", json={"email": "owner@example.test", "password": PASSWORD})
    assert "Secure" in response.headers["set-cookie"] and "HttpOnly" in response.headers["set-cookie"]
    # Short bad passwords avoid expensive derivation, but still count as attempts.
    for _ in range(10):
        assert (
            c.post(
                "/api/account/login", json={"email": "unknown@example.test", "password": "bad"}
            ).status_code
            == 401
        )
    assert (
        c.post("/api/account/login", json={"email": "unknown@example.test", "password": "bad"}).status_code
        == 429
    )

"""Verify a running isolated pilot container using explicitly fictional accounts."""

import argparse
import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

from app import accounts, db
from app.domain import PROGRAM

EMAIL = "smoke-owner@example.test"
PASSWORD = "fictional-ci-account-only-2026"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", action="store_true")
    args = parser.parse_args()
    if args.bootstrap:
        db.init()
        accounts.bootstrap("Fictional CI Library", EMAIL, "Test owner", PASSWORD)
        print("Fictional smoke account created; use only in an isolated test database.")
        return
    origin = os.getenv("PILOT_SMOKE_ORIGIN", "http://127.0.0.1:8018")
    with httpx.Client(base_url=origin, headers={"X-ServiceSignal": "1"}, timeout=30) as client:

        def post(path, body):
            response = client.post(path, json=body)
            response.raise_for_status()
            return response.json()

        assert client.get("/api/workspace").status_code == 401
        post("/api/account/login", {"email": EMAIL, "password": PASSWORD})
        workspace = client.get("/api/workspace").json()
        assert workspace["mode"] == "pilot" and workspace["program"]["configured"] is False
        public_path = "/notices/" + workspace["public_id"]
        assert client.get(public_path).status_code == 404
        post("/api/program", {**PROGRAM, "organization": "Fictional CI Library"})
        future = date.today() + timedelta(days=7)
        future += timedelta(days=(1 - future.weekday()) % 7)
        facts = {
            "program": PROGRAM["name"],
            "kind": "relocation",
            "dates": [future.isoformat()],
            "location": "200 Sample Street",
            "room": "Room B",
            "start_time": "14:00",
            "end_time": "15:30",
            "timezone": PROGRAM["timezone"],
        }
        change = post(
            "/api/changes",
            {"source": "Fictional test: coordinator must confirm the next class venue and date."},
        )
        change = post(
            f"/api/changes/{change['id']}/review",
            {"revision": change["revision"], "facts": facts, "confirmed": True},
        )
        post(
            f"/api/changes/{change['id']}/approve",
            {"revision": change["revision"], "plan_hash": change["plan_hash"]},
        )
        for _ in range(60):
            workspace = client.get("/api/workspace").json()
            actions = workspace["changes"][0]["actions"]
            if any(action["state"] == "VERIFIED" for action in actions):
                break
            time.sleep(0.25)
        else:
            raise AssertionError("Pilot publication was not verified within 15 seconds.")
        assert workspace["changes"][0]["approved_by"]["email"] == EMAIL
        page = client.get(public_path)
        assert page.status_code == 200 and "200 Sample Street" in page.text
        assert "Fictional CI Library" in page.text and EMAIL not in page.text
        assert client.get(public_path + "/flyer.pdf").content.startswith(b"%PDF")
        assert client.get(public_path + "?lang=es").status_code == 404
        before = workspace["publication"]
        followup = post(
            f"/api/changes/{change['id']}/follow-up",
            {"arrangement": "extend", "dates": [(future + timedelta(days=7)).isoformat()]},
        )
        assert followup["state"] == "NEEDS_CLARIFICATION" and followup["approved_at"] is None
        assert client.get("/api/workspace").json()["publication"] == before
        assert client.post("/api/demo/reset", json={}).status_code == 403
        post("/api/account/logout", {})
        assert client.get("/api/workspace").status_code == 401
        assert client.get(public_path).status_code == 200
        result = {
            "passed": True,
            "live_model": False,
            "scope": "fictional account; actual HTTP login, baseline, owner approval, separate worker read-back, PDF, fresh-approval follow-up, logout and stable public link",
        }
        Path("artifacts").mkdir(exist_ok=True)
        Path("artifacts/pilot-http-smoke.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

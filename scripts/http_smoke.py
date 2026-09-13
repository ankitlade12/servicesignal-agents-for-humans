"""Exercise a running API and separate worker through HTTP; save measured evidence."""

import json
import os
import time
from pathlib import Path

import httpx

from app.domain import EXAMPLE

base = os.getenv("SMOKE_ORIGIN", "http://127.0.0.1:8017")
client = httpx.Client(base_url=base, headers={"X-ServiceSignal": "1"}, timeout=100)


def post(path, body):
    response = client.post(path, json=body)
    response.raise_for_status()
    return response.json()


def wait_for(predicate):
    for _ in range(60):
        response = client.get("/api/workspace")
        response.raise_for_status()
        data = response.json()
        if predicate(data):
            return data
        time.sleep(0.25)
    raise AssertionError("The running worker did not finish within 15 seconds.")


try:
    started = time.monotonic()
    post("/api/session", {})
    change = post("/api/changes", {"source": EXAMPLE})
    proposal_ms = round((time.monotonic() - started) * 1000)
    f = change["proposal"]
    facts = {
        key: f[key]
        for key in ("program", "kind", "dates", "location", "room", "start_time", "end_time", "timezone")
    }
    change = post(
        f"/api/changes/{change['id']}/review",
        {"revision": change["revision"], "facts": facts, "confirmed": True},
    )
    approved = time.monotonic()
    post(
        f"/api/changes/{change['id']}/approve",
        {"revision": change["revision"], "plan_hash": change["plan_hash"]},
    )
    published = wait_for(lambda d: any(a["state"] == "VERIFIED" for a in d["changes"][0]["actions"]))
    publication_ms = round((time.monotonic() - approved) * 1000)
    page = client.get(f"/notices/{published['public_id']}")
    assert page.status_code == 200 and "200 Sample Street" in page.text
    pdf = client.get(f"/notices/{published['public_id']}/flyer.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    post(f"/api/changes/{change['id']}/partner/fail", {})
    post("/api/demo/clock", {"change_id": change["id"], "stage": "expiry"})
    ended = wait_for(lambda d: d["changes"][0]["state"] == "ENDED")
    assert ended["publication"]["expired"] is True
    result = {
        "passed": True,
        "provider": ended["provider"],
        "live_model": change["metrics"].get("live", False),
        "intake_including_session_ms": proposal_ms,
        "approval_to_verified_ms": publication_ms,
        "scenario": "actual HTTP intake, approval, worker publication, visible read-back, PDF, partner refusal, expiry",
        "scope": "one fictional local run; not p95 or evidence of model quality or staff time saved",
        "publication": published["publication"],
        "actions": published["changes"][0]["actions"],
        "expired_publication": ended["publication"],
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/http-smoke.json").write_text(json.dumps(result, indent=2))
    Path("artifacts/sample-notice.pdf").write_bytes(pdf.content)
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("passed", "provider", "intake_including_session_ms", "approval_to_verified_ms")
            },
            indent=2,
        )
    )
finally:
    client.close()

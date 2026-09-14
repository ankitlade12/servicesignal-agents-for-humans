"""HSDS 3.2 service exchange with reviewed, non-publishing imports."""

import json
import secrets
import time
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException
from jsonschema import Draft7Validator, FormatChecker

from . import accounts, db
from .domain import Facts, canonical, digest

SCHEMA = json.loads((Path(__file__).resolve().parent.parent / "schemas/hsds-3.2-service.json").read_text())
VALIDATOR = Draft7Validator(SCHEMA, format_checker=FormatChecker())
DAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


def validate_record(record):
    errors = sorted(VALIDATOR.iter_errors(record), key=lambda e: str(list(e.path)))
    if errors:
        error = errors[0]
        path = ".".join(map(str, error.path)) or "service"
        raise HTTPException(422, f"Invalid HSDS 3.2 record at {path}: {error.validator} requirement failed.")


def export_service(ws, origin):
    p = db.program(ws)
    if not p.get("configured", True):
        raise HTTPException(409, "Confirm the program before exporting directory information.")

    def uid(value):
        return str(uuid5(NAMESPACE_URL, "servicesignal:" + value))

    url = origin.rstrip("/") + "/notices/" + ws["public_id"]
    with db.connect() as c:
        rows = c.execute(
            "SELECT facts,expires_at FROM changes WHERE workspace_id=? AND approved_at IS NOT NULL AND state!='SUPERSEDED' ORDER BY approved_at",
            (ws["id"],),
        ).fetchall()
        now = db.now(c, ws["id"])
    alerts = []
    for row in rows:
        f = Facts.model_validate_json(row["facts"])
        spans = "; ".join(x["start"] + " to " + x["end"] for x in f.occurrences())
        alerts.append(
            f"{f.kind}: {spans}; {f.location}, {f.room}. "
            + (
                "Temporary arrangement ended; future sessions need confirmation."
                if row["expires_at"] <= now
                else "Applies only to these sessions."
            )
        )
    record = {
        "id": uid(ws["id"]),
        "name": p["name"],
        "status": "active",
        "description": "Recurring community program. Consult the current notice for temporary changes.",
        "url": url,
        "organization": {
            "id": uid(ws.get("org_id") or ws["id"] + ":org"),
            "name": p["organization"],
            "description": "Organization responsible for this program.",
        },
        "schedules": [
            {
                "id": uid(ws["id"] + ":schedule"),
                "description": f"{p['schedule']}; {p['start_time']}–{p['end_time']}"
                + (" (ends next day)" if p.get("end_day_offset") else "")
                + f"; {p['timezone']}. Baseline only; consult service alerts for exceptions.",
                "schedule_link": url,
            }
        ],
        "service_at_locations": [
            {
                "id": uid(ws["id"] + ":at"),
                "location": {
                    "id": uid(ws["id"] + ":location"),
                    "location_type": "physical",
                    "name": p["room"],
                    "description": p["location"],
                },
            }
        ],
        "alert": "\n".join(alerts),
    }
    if p.get("contact"):
        record["description"] += " Public contact: " + p["contact"]
    validate_record(record)
    return record


def preview_import(ws, document):
    records = (
        document
        if isinstance(document, list)
        else document.get("services", [document])
        if isinstance(document, dict)
        else None
    )
    if not isinstance(records, list) or not 1 <= len(records) <= 50:
        raise HTTPException(
            422, "Upload one HSDS service, an array, or a services collection containing 1–50 records."
        )
    if any(not isinstance(r, dict) for r in records):
        raise HTTPException(422, "Every service must be a JSON object.")
    for record in records:
        validate_record(record)
    if len({r["id"] for r in records}) != len(records):
        raise HTTPException(422, "Service identifiers must be unique within the import.")
    token = secrets.token_urlsafe(24)
    with db.connect(write=True) as c:
        c.execute("DELETE FROM directory_imports WHERE expires_at<?", (time.time(),))
        if (
            c.execute("SELECT count(*) FROM directory_imports WHERE workspace_id=?", (ws["id"],)).fetchone()[
                0
            ]
            >= 10
        ):
            raise HTTPException(429, "Ten import previews are already saved. Retry after they expire.")
        c.execute(
            "INSERT INTO directory_imports VALUES(?,?,?,?,?)",
            (token, ws["id"], canonical(records), time.time() + 86400, "{}"),
        )
    return {
        "id": token,
        "services": [
            {
                "index": i,
                "id": r["id"],
                "name": r["name"],
                "status": r["status"],
                "source_organization": r.get("organization", {}).get("name", ""),
                **candidate(r, db.program(ws)),
            }
            for i, r in enumerate(records)
        ],
        "expires_in_hours": 24,
    }


def candidate(record, baseline):
    locations = record.get("service_at_locations") or []
    loc = (locations[0].get("location") or {}) if locations else {}
    addresses = loc.get("addresses") or []
    address = (
        ", ".join(
            str(addresses[0].get(k, ""))
            for k in ["address_1", "address_2", "city", "state_province", "postal_code", "country"]
            if addresses[0].get(k)
        )
        if addresses
        else loc.get("description", "")
    )
    schedules = record.get("schedules") or []
    schedule = schedules[0] if schedules else {}
    days = [DAYS.index(x) for x in schedule.get("byday", "").split(",") if x in DAYS]

    def clock(key):
        value = schedule.get(key, "")
        return value[:5] if len(value) >= 5 and value[2] == ":" else ""

    start, end = clock("opens_at"), clock("closes_at")
    return {
        "program": {
            "name": record["name"][:100],
            "organization": baseline["organization"],
            "timezone": baseline["timezone"],
            "schedule": schedule.get("description", "")[:120],
            "weekdays": days,
            "location": address[:160],
            "room": loc.get("name", "")[:80],
            "start_time": start,
            "end_time": end,
            "end_day_offset": int(bool(start and end and end <= start)),
            "contact": "",
            "contact_es": "",
            "spanish_enabled": False,
        },
        "warnings": [
            "Import creates an unconfirmed program in your organization; it never publishes.",
            "Confirm your authority for this service and all required fields. The source organization is not adopted.",
            "Review timezone and hours: HSDS UTC offsets do not identify an IANA timezone. The timezone shown is your current program’s default.",
            "Only the first location and schedule are suggested. Additional locations, schedules, alerts and other directory fields remain in the downloadable original; they are not applied as program facts.",
            f"Source service status: {record['status']}. Import does not confirm current availability.",
        ],
    }


def confirm_import(ws, import_id, index, program, confirmed):
    if not confirmed:
        raise HTTPException(422, "Confirm ownership and the imported program details.")
    if program.organization != ws["organization"]:
        raise HTTPException(422, "Use your account’s organization name.")
    with db.connect(write=True) as c:
        row = c.execute(
            "SELECT * FROM directory_imports WHERE id=? AND workspace_id=? AND expires_at>?",
            (import_id, ws["id"], time.time()),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Import preview is unavailable or expired.")
        records = json.loads(row["source"])
        if not 0 <= index < len(records):
            raise HTTPException(422, "Choose a service from the preview.")
        used = json.loads(row["imported"])
        if str(index) in used:
            return {"workspace_id": used[str(index)], "created": False}
        if c.execute("SELECT count(*) FROM workspaces WHERE org_id=?", (ws["org_id"],)).fetchone()[0] >= 50:
            raise HTTPException(429, "This organization has reached its 50-program limit.")
        new_id = accounts.create_workspace(c, ws["org_id"], {**program.model_dump(), "configured": False})
        c.execute(
            "INSERT INTO directory_sources VALUES(?,?,?,?)",
            (new_id, canonical(records[index]), digest(records[index]), time.time()),
        )
        used[str(index)] = new_id
        c.execute("UPDATE directory_imports SET imported=? WHERE id=?", (canonical(used), import_id))
        accounts.record(
            c,
            ws["org_id"],
            ws["actor"]["id"],
            "DIRECTORY_IMPORTED",
            "Reviewed HSDS service imported as an unconfirmed program.",
        )
    return {"workspace_id": new_id, "created": True}

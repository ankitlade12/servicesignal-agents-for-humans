"""Validated operational facts. Models never grant publication authority."""

import hashlib
import json
from datetime import date, datetime, time
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator

PROGRAM = {
    "name": "Digital Basics",
    "organization": "Maple Community Center",
    "timezone": "America/Chicago",
    "schedule": "Tuesdays, 6–8 p.m.",
    "location": "100 Example Avenue",
    "room": "Room A",
    "start_time": "18:00",
    "end_time": "20:00",
    "weekdays": [1],
    "contact": "",
}
EXAMPLE = (
    "For September 15 and September 22, 2026, Digital Basics will meet in Room B at "
    "200 Sample Street. Same time. Other activities stay where they are."
)
AMBIGUOUS_EXAMPLE = "Digital Basics is moving for the next two sessions. Same time."
FALLBACK = "This temporary arrangement has ended. Details for future sessions need confirmation."


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Program(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=100)
    organization: str = Field(min_length=2, max_length=120)
    timezone: str = "America/Chicago"
    schedule: str = Field(min_length=2, max_length=120)
    weekdays: list[int] = Field(min_length=1, max_length=7)
    location: str = Field(min_length=1, max_length=160)
    room: str = Field(min_length=1, max_length=80)
    start_time: str
    end_time: str
    contact: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def validate_program(self):
        validate_zone(self.timezone)
        validate_hours(self.start_time, self.end_time)
        if any(d not in range(7) for d in self.weekdays):
            raise ValueError("Select valid weekdays, Monday through Sunday.")
        self.weekdays = sorted(set(self.weekdays))
        for value in self.model_dump().values():
            if isinstance(value, str) and any(ord(c) < 32 for c in value):
                raise ValueError("Program details cannot contain control characters.")
        return self


def validate_zone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Use a valid IANA timezone, such as America/Chicago.") from None


def validate_hours(start, end):
    for value in (start, end):
        if len(value) != 5 or time.fromisoformat(value).isoformat(timespec="minutes") != value:
            raise ValueError("Use HH:MM times.")
    if end <= start:
        raise ValueError("The session must end after it starts on the same day.")


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    program: str = "Digital Basics"
    kind: Literal["relocation", "cancellation", "time_change"] = "relocation"
    dates: list[str] = Field(default_factory=list, max_length=12)
    location: str = Field(default="", max_length=160)
    room: str = Field(default="", max_length=80)
    start_time: str = "18:00"
    end_time: str = "20:00"
    timezone: str = "America/Chicago"
    evidence: dict[str, str] = Field(default_factory=dict)
    questions: list[str] = Field(default_factory=list, max_length=8)
    explanation: str = Field(default="", max_length=1200)


class Facts(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    program: str = Field(default="Digital Basics", min_length=2, max_length=100)
    kind: Literal["relocation", "cancellation", "time_change"]
    dates: list[date] = Field(min_length=1, max_length=12)
    location: str = Field(min_length=1, max_length=160)
    room: str = Field(min_length=1, max_length=80)
    start_time: str
    end_time: str
    timezone: str = "America/Chicago"

    @model_validator(mode="after")
    def check_sessions(self):
        self.dates = sorted(set(self.dates))
        if any(d.year < 2026 or d.year > 2030 for d in self.dates):
            raise ValueError("This prototype supports sessions from 2026 through 2030.")
        if (self.dates[-1] - self.dates[0]).days > 90:
            raise ValueError("Temporary changes may span at most 90 days.")
        validate_zone(self.timezone)
        validate_hours(self.start_time, self.end_time)
        for d in self.dates:
            for clock in (self.start_time, self.end_time):
                local = datetime.combine(d, time.fromisoformat(clock))
                zone = ZoneInfo(self.timezone)
                first = local.replace(tzinfo=zone, fold=0)
                second = local.replace(tzinfo=zone, fold=1)
                if first.utcoffset() != second.utcoffset():
                    raise ValueError(
                        "A session time falls in a daylight-saving gap or repeated hour. Choose an unambiguous time."
                    )
        for value in (self.location, self.room):
            if any(ord(c) < 32 for c in value):
                raise ValueError("Location fields cannot contain control characters.")
        return self

    def expires_at(self):
        local = datetime.combine(self.dates[-1], time.fromisoformat(self.end_time), ZoneInfo(self.timezone))
        return local.timestamp()


def fact_payload(facts, public_id, revision, approved_at, expired=False, program=None):
    return {
        "program_context": program or PROGRAM,
        "public_id": public_id,
        "revision": revision,
        "facts": facts,
        "approved_at": approved_at,
        "expired": expired,
        "message": FALLBACK
        if expired
        else "Applies only to the sessions listed below. Other activities are unchanged.",
    }


def visible_facts(payload):
    f = payload["facts"]
    return {
        "program": f["program"],
        "organization": payload.get("program_context", PROGRAM)["organization"],
        "contact": payload.get("program_context", PROGRAM).get("contact", ""),
        "kind": {
            "relocation": "Temporary venue change",
            "cancellation": "Session cancellation",
            "time_change": "Session time change",
        }[f["kind"]],
        "dates": "; ".join(date.fromisoformat(d).strftime("%b %d, %Y") for d in f["dates"]),
        "location": f["location"],
        "room": f["room"],
        "start_time": f["start_time"],
        "end_time": f["end_time"],
        "timezone": f["timezone"],
        "message": payload["message"],
        "expired": "This arrangement has ended"
        if payload["expired"]
        else "Only the listed sessions are affected",
    }

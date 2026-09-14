"""Validated operational facts. Models never grant publication authority."""

import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
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
    "end_day_offset": 0,
    "weekdays": [1],
    "contact": "",
    "contact_es": "",
    "spanish_enabled": False,
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
    end_day_offset: Literal[0, 1] = 0
    contact: str = Field(default="", max_length=200)
    contact_es: str = Field(default="", max_length=200)
    spanish_enabled: bool = False

    @model_validator(mode="after")
    def validate_program(self):
        if self.spanish_enabled and self.contact and not self.contact_es:
            raise ValueError("Add confirmed Spanish contact instructions before enabling Spanish notices.")
        validate_zone(self.timezone)
        validate_hours(self.start_time, self.end_time, self.end_day_offset)
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


def validate_hours(start, end, end_day_offset=0, allow_repeated=False):
    for value in (start, end):
        if len(value) != 5 or time.fromisoformat(value).isoformat(timespec="minutes") != value:
            raise ValueError("Use HH:MM times.")
    if not allow_repeated and end_day_offset == 0 and end <= start:
        raise ValueError("The session must end after it starts. Select next day for an overnight session.")
    if end_day_offset == 1 and end > start:
        raise ValueError("An overnight session may span at most 24 local hours.")


class TimeChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_fold: Literal[0, 1] | None = None
    end_fold: Literal[0, 1] | None = None


def resolve_local(day, clock, zone_name, fold=None):
    local = datetime.combine(day, time.fromisoformat(clock))
    zone = ZoneInfo(zone_name)
    candidates = [local.replace(tzinfo=zone, fold=i) for i in (0, 1)]
    valid = [x for x in candidates if x.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == local]
    if not valid:
        raise ValueError(
            f"{day} {clock} does not exist in {zone_name} (daylight-saving gap). Choose another time."
        )
    ambiguous = len({x.timestamp() for x in valid}) == 2
    if ambiguous and fold is None:
        choices = " or ".join(x.strftime("%z") for x in valid)
        raise ValueError(
            f"{day} {clock} is a repeated hour in {zone_name}. Choose first or second occurrence ({choices})."
        )
    if not ambiguous and fold is not None:
        raise ValueError(f"{day} {clock} is not a repeated hour. Clear its daylight-saving choice.")
    return candidates[fold or 0]


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    program: str = "Digital Basics"
    kind: Literal["relocation", "cancellation", "time_change"] = "relocation"
    dates: list[str] = Field(default_factory=list, max_length=12)
    location: str = Field(default="", max_length=160)
    room: str = Field(default="", max_length=80)
    start_time: str = "18:00"
    end_time: str = "20:00"
    end_day_offset: Literal[0, 1] = 0
    time_choices: dict[date, TimeChoice] = Field(default_factory=dict, max_length=12)
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
    end_day_offset: Literal[0, 1] = 0
    time_choices: dict[date, TimeChoice] = Field(default_factory=dict, max_length=12)
    timezone: str = "America/Chicago"

    @model_validator(mode="after")
    def check_sessions(self):
        self.dates = sorted(set(self.dates))
        if any(d.year < 2026 or d.year > 2030 for d in self.dates):
            raise ValueError("This prototype supports sessions from 2026 through 2030.")
        if (self.dates[-1] - self.dates[0]).days > 90:
            raise ValueError("Temporary changes may span at most 90 days.")
        validate_zone(self.timezone)
        validate_hours(self.start_time, self.end_time, self.end_day_offset, allow_repeated=True)
        if set(self.time_choices) - set(self.dates):
            raise ValueError("Daylight-saving choices must refer to affected session start dates.")
        for d in self.dates:
            start, end = self.session_bounds(d)
            if end.timestamp() <= start.timestamp():
                raise ValueError(
                    "The session must end after it starts. Check the end day and repeated-hour choices."
                )
        for value in (self.location, self.room):
            if any(ord(c) < 32 for c in value):
                raise ValueError("Location fields cannot contain control characters.")
        return self

    def session_bounds(self, day):
        choice = self.time_choices.get(day, TimeChoice())
        return (
            resolve_local(day, self.start_time, self.timezone, choice.start_fold),
            resolve_local(
                day + timedelta(days=self.end_day_offset), self.end_time, self.timezone, choice.end_fold
            ),
        )

    def occurrences(self):
        return [
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "start_utc": start.astimezone(UTC).isoformat(),
                "end_utc": end.astimezone(UTC).isoformat(),
            }
            for start, end in (self.session_bounds(day) for day in self.dates)
        ]

    def expires_at(self):
        return max(self.session_bounds(day)[1].timestamp() for day in self.dates)


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


def visible_facts(payload, language="en"):
    from .localization import COPY, MONTHS_ES

    f = payload["facts"]
    context = payload.get("program_context", PROGRAM)
    copy = COPY[language]
    dates = [date.fromisoformat(d) for d in f["dates"]]
    return {
        "program": f["program"],
        "organization": context["organization"],
        "contact": context.get("contact_es" if language == "es" else "contact", ""),
        "kind": copy[f["kind"]],
        "dates": "; ".join(
            f"{d.day} de {MONTHS_ES[d.month - 1]} de {d.year}"
            if language == "es"
            else d.strftime("%b %d, %Y")
            for d in dates
        ),
        "location": f["location"],
        "room": f["room"],
        "start_time": f["start_time"],
        "end_time": f["end_time"],
        "timezone": f["timezone"],
        "session_times": "; ".join(
            x["start"] + " → " + x["end"] for x in Facts.model_validate(f).occurrences()
        ),
        "message": (copy["fallback"] if payload["expired"] else copy["message"])
        if language == "es"
        else payload["message"],
        "expired": copy["ended"] if payload["expired"] else copy["active"],
    }

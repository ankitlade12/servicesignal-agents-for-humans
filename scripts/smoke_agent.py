"""Live smoke run. Saves factual result/usage only, never credentials."""

import asyncio
import json
from pathlib import Path

from app.agent import interpret, provider
from app.domain import EXAMPLE


async def main():
    if provider() == "fixture":
        raise SystemExit("Set AGENT_PROVIDER=openai, anthropic, or bedrock for a live smoke test.")
    proposal, metrics = await interpret(EXAMPLE)
    assert proposal.dates == ["2026-09-15", "2026-09-22"], proposal.dates
    assert proposal.location == "200 Sample Street", proposal.location
    assert proposal.room == "Room B", proposal.room
    assert proposal.start_time == "18:00" and proposal.end_time == "20:00"
    assert not proposal.questions, proposal.questions
    result = {
        "scenario": "two-session relocation",
        "proposal": proposal.model_dump(),
        "metrics": metrics,
        "passed": True,
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/live-agent-smoke.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


asyncio.run(main())

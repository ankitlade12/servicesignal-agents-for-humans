"""Actual Strands + OpenAI SDK integration against a local HTTP fixture, never a live model eval."""

import asyncio
import json

import httpx
import openai
import pytest

from app.agent import interpret
from app.domain import EXAMPLE, PROGRAM


def test_openai_requires_server_key(monkeypatch):
    monkeypatch.setenv("AGENT_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        asyncio.run(interpret(EXAMPLE))


def test_strands_openai_streaming_tools_and_proposal(monkeypatch):
    monkeypatch.setenv("AGENT_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "local-fixture-not-a-secret")
    monkeypatch.delenv("AGENT_MODEL_ID", raising=False)
    original = openai.AsyncOpenAI
    requests = []
    proposal = {
        "program": "Digital Basics",
        "kind": "relocation",
        "dates": ["2026-09-15", "2026-09-22"],
        "location": "200 Sample Street",
        "room": "Room B",
        "start_time": "18:00",
        "end_time": "20:00",
        "timezone": "America/Chicago",
        "evidence": {"room": "Room B", "dates": "invented quotation"},
        "questions": [],
        "explanation": "Two sessions move.",
    }

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["model"] == "gpt-5.4-mini-2026-03-17"
        assert body["max_completion_tokens"] == 4000
        names = [item["function"]["name"] for item in body.get("tools", [])]
        assert not any("publish" in name or "approve" in name for name in names)
        if len(requests) == 1:
            calls = [
                {
                    "index": i,
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {"name": name, "arguments": "{}"},
                }
                for i, name in enumerate(["read_source", "get_program_context"])
            ]
        else:
            results = [m for m in body["messages"] if m["role"] == "tool"]
            serialized = json.dumps(results)
            assert EXAMPLE in serialized and PROGRAM["organization"] in serialized
            output_name = next(name for name in names if name not in ["read_source", "get_program_context"])
            calls = [
                {
                    "index": 0,
                    "id": "call_result",
                    "type": "function",
                    "function": {"name": output_name, "arguments": json.dumps(proposal)},
                }
            ]
        base = {
            "id": "local-completion",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": body["model"],
        }
        chunks = [
            {
                **base,
                "choices": [
                    {"index": 0, "delta": {"role": "assistant", "tool_calls": calls}, "finish_reason": None}
                ],
            },
            {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
            {
                **base,
                "choices": [],
                "usage": {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140},
            },
        ]
        content = "".join("data: " + json.dumps(c) + "\n\n" for c in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=content)

    def local_client(**kwargs):
        return original(**kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))

    monkeypatch.setattr(openai, "AsyncOpenAI", local_client)
    result, metrics = asyncio.run(interpret(EXAMPLE))
    assert len(requests) == 2
    assert result.dates == proposal["dates"]
    assert result.evidence == {"room": "Room B"}  # fabricated quote removed by application
    assert result.questions
    assert metrics["provider"] == "openai"
    assert metrics["tool_scope"] == ["read_source", "get_program_context"]

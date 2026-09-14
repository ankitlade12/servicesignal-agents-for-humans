"""Small labeled development evaluation; this is not a held-out release benchmark."""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from app.agent import interpret

ROOT = Path(__file__).resolve().parent.parent


async def evaluate(cases):
    results = []
    for case in cases:
        started = time.monotonic()
        try:
            proposal, metrics = await interpret(case["source"])
            actual = proposal.model_dump(mode="json")
            failures = [
                f"{key} differs"
                for key, expected in case.get("expected", {}).items()
                if actual.get(key) != expected
            ]
            if bool(proposal.questions) != case["clarify"]:
                failures.append("clarification decision differs")
            if any(quote not in case["source"] for quote in proposal.evidence.values()):
                failures.append("unsupported evidence quote")
            results.append(
                {
                    "id": case["id"],
                    "passed": not failures,
                    "failures": failures,
                    "proposal": actual,
                    "metrics": metrics,
                }
            )
        except Exception as error:
            results.append({"id": case["id"], "passed": False, "error_category": type(error).__name__})
        results[-1]["elapsed_seconds"] = round(time.monotonic() - started, 3)
        print(case["id"], "PASS" if results[-1]["passed"] else "FAIL", flush=True)
    return results


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-cases", action="store_true", help="Validate dataset only; no model invocation."
    )
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()
    cases = json.loads((ROOT / "evals/development-cases.json").read_text())
    assert len({c["id"] for c in cases}) == len(cases)
    assert all(isinstance(c["clarify"], bool) and 10 <= len(c["source"]) <= 6000 for c in cases)
    if args.check_cases:
        print(f"{len(cases)} unique labeled development cases validated. No model call made.")
        return
    if not 1 <= args.limit <= len(cases):
        parser.error(f"--limit must be from 1 to {len(cases)}")
    provider = os.getenv("AGENT_PROVIDER", "fixture")
    if provider not in ("openai", "anthropic", "bedrock"):
        parser.error("Configure a live provider. Fixture mode cannot establish model quality.")
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        parser.error("Set OPENAI_API_KEY locally before evaluating OpenAI.")
    results = asyncio.run(evaluate(cases[: args.limit]))
    report = {
        "dataset": "development-v1",
        "held_out": False,
        "provider": provider,
        "cases": len(results),
        "passed": sum(r["passed"] for r in results),
        "results": results,
    }
    (ROOT / "artifacts/evaluation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"{report['passed']}/{report['cases']} passed; artifacts/evaluation.json")
    raise SystemExit(0 if all(r["passed"] for r in results) else 1)


if __name__ == "__main__":
    main()

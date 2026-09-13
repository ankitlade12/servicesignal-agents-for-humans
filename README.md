# ServiceSignal

**When a community program changes, approve the correction once. Update connected notices and see what still needs attention.**

A working prototype for the **Agents for Humans · Good Neighbor Agents** track. ServiceSignal helps a community-center coordinator manage temporary class changes across an owned website, printable notices, a simulated partner listing, and printed-copy tasks.

[Source repository](https://github.com/ankitlade12/servicesignal-agents-for-humans) · [Narrated guided walkthrough](artifacts/guided-walkthrough.mp4) · [Submission readiness](docs/SUBMISSION.md)

![Coordinator overview](artifacts/overview-desktop.png)

## Run locally

Requires Python 3.12–3.14 and [uv](https://docs.astral.sh/uv/). No Node build, database service, or API key is needed for the labeled guided demonstration.

```bash
uv sync --frozen
bash scripts/start.sh
```

Open **http://localhost:8017**. The command starts the API and a separate durable worker. Data persists in `data/servicesignal.sqlite`. Stop with Ctrl+C. A different port can be selected with `SERVICESIGNAL_PORT=8020 bash scripts/start.sh`.

The default `AGENT_PROVIDER=fixture` mode only recognizes the two built-in examples. Other input requires manual fact confirmation. **Fixture mode is not a live Strands run and must not be presented as one.**

## Try the complete story

1. Select **Try a two-session move**, then **Prepare update**.
2. Review the source evidence and exact September 15/22, 2026 sessions. Confirm facts.
3. Approve the exact plan, including the expiration fallback.
4. Watch the website become **Verified** after an actual HTTP write and a separate HTTP read of the rendered page.
5. Open the public page; download the printable PDF and QR code.
6. Simulate partner acknowledgment, publication, or refusal. These states never masquerade as live directory verification.
7. Advance the isolated demo clock to the reminder and expiration. Future arrangements remain unconfirmed until a new update is approved.
8. Export the evidence from Activity. Reset deletes this workspace and invalidates its public link.

Every isolated workspace starts its **demo clock at September 13, 2026**, so the fictional September scenario remains replayable throughout judging. The clock advances normally from there, or through the labeled demo controls. Past changes relative to that demo clock are rejected. Session expiry still uses real elapsed time. These dates never claim current real-world service availability.

## Live Strands configuration

Use a `.env` file based on `.env.example`, or export environment variables. Never commit keys. The Strands SDK and all transitive dependencies are pinned in `uv.lock`.

### Amazon Bedrock

```bash
export AGENT_PROVIDER=bedrock
export AWS_REGION=us-east-1
export AGENT_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
# Configure your own AWS profile / role through the normal AWS SDK credential chain.
PYTHONPATH=. uv run python scripts/smoke_agent.py
bash scripts/start.sh
```

The model/inference profile must be available and authorized in your account. The account used during development authenticated successfully but denied `bedrock:InvokeModelWithResponseStream`. Model catalog access was also denied. **Bedrock execution has not passed a live smoke test.** An account administrator must grant the appropriate invocation access for the intended model; the application does not change IAM permissions.

### Anthropic through Strands

```bash
export AGENT_PROVIDER=anthropic
export AGENT_MODEL_ID=claude-haiku-4-5-20251001
# Set ANTHROPIC_API_KEY securely in your environment or .env.
PYTHONPATH=. uv run python scripts/smoke_agent.py
bash scripts/start.sh
```

This is still a Strands agent. The configured development key reached Anthropic, but the account returned insufficient credit. **Live model accuracy, latency, and cost are therefore unverified.** A successful smoke test writes `artifacts/live-agent-smoke.json`.

The agent uses `read_source` and `get_program_context`, then produces a Pydantic-validated proposal. It cannot access publisher credentials or send messages. Application code validates dates and scope, records coordinator confirmation, binds approval to an immutable plan hash, and enqueues work. Invocations have a 90-second deadline, six-turn limit, and token limits. Live calls are capped per workspace and per UTC day.

## Implemented

- Responsive coordinator overview, intake, source evidence, fact review, approval, delivery tracking, program, public-notice, and activity screens.
- One fictional organization and recurring program per isolated browser session.
- Source deduplication, persistent clarifications through explicit fact entry, and optimistic revision checks.
- Immutable plan hash, server-side write authority, expected destination versions, and explicit supersession.
- Separate worker, SQLite WAL transactions, job leases, bounded retries, restart reconciliation, and idempotent publication.
- Actual controlled publication, fresh rendered-HTML comparison, timestamped evidence, and recurring 15-minute drift checks.
- Expiration reminders and an approved unconfirmed-state fallback; no automatic venue reversion.
- Downloadable English PDF and permanent QR link. Residents do not need an account.
- Clearly labeled partner simulator and attributed manual print confirmation.
- Session isolation, same-origin write checks, escaped output, content security policy, model call caps, and seven-day demo-session expiry.

## Scope and known limits

This is a fictional prototype, not a live community service. It supports **one program, four registered surfaces, English pasted-text intake, and one active public notice per workspace**. A replacement approval explicitly supersedes the previous notice and its entire session list.

The original [PRD](ServiceSignal_PRD.md) is broader than this implementation. PDF intake, Spanish output, OCR, arbitrary discovery, real partner/email/SMS integrations, real organization accounts, PostgreSQL/S3, and HSDS export are deferred. The frontend uses plain browser JavaScript and system fonts; SQLite keeps this prototype reproducible on one persistent host. Deploy exactly one API and worker pair with shared persistent storage.

The source, extracted proposal, and human edits remain private to the demo session. Public links expose only approved projections and expire after seven days. Reset is irreversible within the demo. Expired workspaces are deleted on creation of a new session. Production retention, backup deletion, stronger authentication, abuse protection, and operational monitoring still need a real deployment design. No resident data is collected.

The QR link reflects the latest publication; already printed text and forwarded screenshots remain outside automated control. PDF accessibility is not certified. Verification records what was observed at a timestamp; worker/network downtime can delay updates and expiry. Generated PDFs are tested for factual consistency, not arbitrary layouts or all languages.

## Verify

```bash
uv run pytest -q --junitxml=artifacts/test-results.xml
uv run ruff check app tests scripts
node --check static/app.js
```

See [verification evidence](docs/VERIFICATION.md) for results and limits. The automated suite tests real FastAPI handlers, a real temporary SQLite database, the worker, rendered HTML, and PDF extraction. It uses labeled deterministic interpretation, not live model evaluation. The PRD’s proposed held-out model benchmark and manual/LLM baseline comparison have not been completed.

## Deploy

```bash
docker compose up --build
```

See [deployment instructions](docs/DEPLOYMENT.md). Keep the volume persistent, configure `PUBLIC_ORIGIN` to the real HTTPS URL, and set `COOKIE_SECURE=1` when hosted. QR codes use `PUBLIC_ORIGIN`. This architecture requires a persistent container/VM; stateless functions with ephemeral SQLite are unsuitable.

## Submission and community pilot

- [Architecture diagram](docs/architecture.svg) and [architecture notes](docs/ARCHITECTURE.md)
- [Devpost submission draft and readiness checklist](docs/SUBMISSION.md)
- [Demo narration and recording plan](docs/DEMO_SCRIPT.md)
- [Pilot and adoption plan](docs/PILOT.md)
- [Research and attribution](docs/ATTRIBUTION.md)

No live deployment, Devpost entry, public video upload, or community impact is implied by the presence of these files. Check the readiness checklist before submitting. ServiceSignal is a working title; unrelated products already use the name.

## License

MIT © 2026 Ankit Hemant Lade. Code, original vector illustrations, fictional fixtures, and project documentation are included. Third-party dependencies retain their own licenses. Developed with AI coding assistance during the hackathon submission period.

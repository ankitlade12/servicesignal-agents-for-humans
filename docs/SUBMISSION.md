# Devpost submission draft

**Working title:** ServiceSignal — Keep your community in the loop

**Track:** Good Neighbor Agents

**Short description:** Approve a temporary community-program change once. Publish and verify the owned notice, prepare replacement flyers, track unresolved copies, and follow up when the arrangement ends.

## Inspiration

A small schedule change can become several separate chores: updating a program page, replacing a flyer, asking a partner to edit its listing, and remembering what happens when the temporary arrangement ends. Residents need clear information, while coordinators need an honest view of which copies still require attention.

ServiceSignal explores this workflow for a fictional community center's Digital Basics class. The broader information-maintenance problem is documented by Open Referral. Our specific adoption and time-saving claims still need a real pilot.

## What it does

The coordinator configures a program, pastes a change or uploads a text or scanned PDF, reviews source evidence, supplies missing details, and approves the exact affected sessions and destinations. The background worker publishes the controlled website and independently reads its rendered facts back. It prepares an English printable notice and permanent QR link, while tracking simulated partner work and manual print replacement separately.

Before the final affected session ends, the workflow requests a new decision. If no new arrangement is approved, it publishes the previously approved unconfirmed-state notice. It never silently restores a potentially outdated venue.

## How it is built

Python, FastAPI, Strands Agents SDK, Pydantic, SQLite WAL, a separate Python worker, plain browser JavaScript/CSS, ReportLab, and QR generation. The Strands integration has read-only source and program tools and structured output. Publication authority lives in server code: exact revision and plan hashes, destination versions, transactional jobs, and idempotency keys.

The worker verifies visible rendered facts after HTTP publication. A later mismatch requests owner attention instead of overwriting data. Fixtures and the partner simulator are clearly labeled throughout.

## What is working and what is not yet verified

The local end-to-end publication, read-back, PDFs, QR link, manual/simulated states, and expiry workflow are implemented and tested. The deterministic release suite passes; see `docs/VERIFICATION.md` for the exact recorded result.

Live OpenAI through Strands passed the two-session relocation smoke and the final 12-case development evaluation. Earlier live development runs passed 9/12 and 10/12; those reports are retained. This small development set is not a held-out accuracy benchmark. The existing narrated video still shows the older fixture workflow and must be updated to demonstrate live execution. Bedrock and Anthropic remain alternative adapters without successful live runs on the development accounts.

No real partner integration, real resident usage, measured time savings, or avoided trips are claimed. Pilot mode adds organization accounts, owner/editor/viewer roles, multiple programs, assigned copy owners, and fresh-approval follow-up drafts. Pilot programs support independent notices on different dates and four core surfaces. English text/scanned-PDF intake is supported; optional Spanish output is off by default.

## Originality and next steps

Service Net and Yext already address reconciliation/distribution or verification. Our proposed focus is coordinator-confirmed temporary class changes, exact affected occurrences, informal-source evidence, unresolved-copy visibility, and safe end-date follow-up. We plan to validate the workflow with three coordinators and one consenting organization before expanding integrations.

## Submission readiness

Official deadline: **September 14, 2026, 5 p.m. PDT / 7 p.m. CDT / September 15, 00:00 UTC**. The [official rules](https://agentsforhumans.devpost.com/rules) require a new Strands project, public source repository with MIT/Apache license and README, architecture diagram, public YouTube/Vimeo demo up to five minutes, and AWS Builder ID. The optional live demo and AgentCore deployment can strengthen technical evaluation.

| Item | Current readiness |
|---|---|
| Runnable source, README, MIT license | Public repository prepared; latest checks linked in verification record |
| Architecture diagram | `docs/architecture.svg` |
| Working controlled publication and verification | Implemented; see verification evidence |
| Live Strands execution | OpenAI live smoke and final 12/12 development evaluation passed; updated live recording still needed |
| Public repository URL | https://github.com/ankitlade12/servicesignal-agents-for-humans |
| Persistent hosted demo | Railway invite-only pilot: https://servicesignal-production.up.railway.app; judge access still needs provisioning |
| Demo video | `artifacts/guided-walkthrough.mp4`, narrated guided demo, 61.1 seconds; must include live execution before submission |
| Public YouTube/Vimeo video URL | Account/upload required |
| Entrant's AWS Builder ID | Must be supplied by entrant |
| Devpost submission | Not submitted |
| Optional AWS Builder Center post | Draft only; do not claim completed AWS execution |

Keep judge access available through the end of judging, **October 8, 2026**, as specified in the rules. A self-contained test build and setup instructions are included; a cloud URL is optional. The entrant must review their own eligibility and account-bound declarations.

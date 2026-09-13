# Verification record

Verified locally on September 13, 2026. All scenarios use fictional data.

## Automated release checks

**42 passed**, latest run **2.56 seconds**. `artifacts/test-results.xml` contains the machine-readable result. One dependency deprecation warning from Starlette/AnyIO was emitted; it did not fail the suite.

`ruff check app tests scripts` and `node --check static/app.js` passed.

Coverage includes exact-session publication, visible HTML read-back, missing details, manual clarification, source/approval deduplication, fact confirmation, stale plans, tenant isolation, unauthenticated access, same-origin writes, publisher credentials/leases, restart after remote write, misleading success responses, retries, version conflicts, partner refusal/acknowledgment/simulation, PDF facts, print attribution, reminder, expiry, supersession, explicit replacement, reset, source injection, HTML escaping, invalid dates/times/scope, and later drift detection without overwriting.

The tests use real route handlers, temporary SQLite databases, and the actual worker logic. In-process TestClient transport is used for the automated suite. This suite is distinct from the PRD's proposed 40-case held-out extraction benchmark. No live model quality benchmark or manual/LLM baseline study was run.

## Browser and real HTTP flow

The separate API and worker ran on localhost:8017. Browser actions exercised source intake, fact review, exact approval, verified publication, partner refusal, and expiration. The public resident notice was then opened directly.

| Boundary | Result | Evidence |
|---|---|---|
| UI loads and navigation renders | Passed | `artifacts/overview-desktop.png` |
| Source → review → exact plan | Passed | `artifacts/review-desktop.png` |
| Approval → separate worker → HTTP publication | Passed | `artifacts/http-smoke.json` |
| Rendered facts independently checked | Passed | Timestamped action evidence in HTTP report |
| Public PDF download | Passed | `artifacts/sample-notice.pdf`; extraction checks in tests |
| Partner refusal preserves successful page | Passed | Browser interaction and automated test |
| Expiration → unconfirmed future state | Passed | `artifacts/expiration-desktop.png`, `artifacts/resident-notice.png` |
| Mobile resident and coordinator views | Passed | Mobile screenshots; 390px viewport, 390px document width |
| Desktop overflow | Passed | 1440px viewport, 1440px document width |
| Basic keyboard entry | Passed | Tab reaches “Skip to main content”; controls have accessible names |
| Unsaved edits block approval | Passed | Changing the room disabled approval until facts were saved as revision 3 |
| Browser exceptions | None reported | `agent-browser errors` after flow checks |

These are basic accessibility checks, not a full WCAG audit or PDF certification. See the screenshots for the actual tested appearance. The fixed mobile navigation remains visible during scrolling.

The HTTP report includes measured intake and approval-to-verification durations for one local fictional run. They are not p95 measurements, live model latency, or demonstrated human time savings.

## Live-model checks

- Strands Agents **1.55.1** installed and API signatures inspected.
- AWS identity authenticated, but Bedrock catalog and `ConverseStream` invocation returned access denied. The role lacks the tested model's invocation permission.
- Anthropic through Strands reached the provider, which returned insufficient account credit.
- No successful live structured extraction was observed. Do not claim otherwise or submit the guided recording as live-model proof.
- The integration uses bounded read-only tools and structured output. `scripts/smoke_agent.py` records a successful live run only when one actually succeeds.

## Deployment and external publication

The local process supervisor and persistent SQLite behavior were exercised. Dockerfile, Compose, and CI build configuration are supplied. A local Docker build could not run because the Docker daemon was unavailable. GitHub CI is configured to test and build the image once the repository is published.

A persistent cloud deployment, entrant's AWS Builder ID, public video upload, and final Devpost entry require the corresponding account access. No submission success or public hosting is implied by these local artifacts.

## Walkthrough recording

`artifacts/guided-walkthrough.webm` is a real browser recording of the fictional workflow (50.866 seconds). It includes fact review, approval invalidation after an edit, actual publication, partner refusal, resident notice, and expiration. The provider badge identifies guided mode. The MP4 version (61.1 seconds, H.264 video and AAC audio) includes synthetic narration from `docs/walkthrough-narration.txt`, which explicitly states that live model access is pending. The final frame is held while narration finishes.

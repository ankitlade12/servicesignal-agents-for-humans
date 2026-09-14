# Verification record

Verified locally on September 13, 2026. All scenarios use fictional data.

## Automated release checks

**99 passed** in the latest recorded local run. `artifacts/test-results.xml` contains the machine-readable result. One dependency deprecation warning from Starlette/AnyIO was emitted; it did not fail the suite. The replay test checks that a new demo still accepts its fictional scenario a year after the scenario dates.

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

The local process supervisor and persistent SQLite behavior were exercised. Dockerfile and Compose are supplied. A local Docker build could not run because the Docker daemon was unavailable; the initial [GitHub CI run](https://github.com/ankitlade12/servicesignal-agents-for-humans/actions/runs/34787805402) passed dependency installation, tests, lint, JavaScript syntax, and Docker image build. CI now also starts the container and runs the real HTTP/worker smoke scenario. Check the latest [workflow result](https://github.com/ankitlade12/servicesignal-agents-for-humans/actions) for its outcome.

A persistent cloud deployment, entrant's AWS Builder ID, public video upload, and final Devpost entry require the corresponding account access. No submission success or public hosting is implied by these local artifacts.

## Walkthrough recording

`artifacts/guided-walkthrough.webm` is a real browser recording of the fictional workflow (50.866 seconds). It includes fact review, approval invalidation after an edit, actual publication, partner refusal, resident notice, and expiration. The provider badge identifies guided mode. The MP4 version (61.1 seconds, H.264 video and AAC audio) includes synthetic narration from `docs/walkthrough-narration.txt`, which explicitly states that live model access is pending. The final frame is held while narration finishes.


## Expanded product verification

The suite now exercises configurable program names, organizations, contacts, weekdays and timezones; scope rejection against the configured baseline; daylight-saving gaps/repeated hours; private original-PDF preservation and deduplication; cross-workspace document rejection; malformed/scanned/encrypted/oversized PDFs; worker readiness; and resident expiry with the worker deliberately stopped. Three former hardcoded schema assertions became equivalent workspace-level scope checks as part of program generalization.

The real Strands + OpenAI SDK streaming contract is tested against a local HTTP fixture, including the two read-only tools and structured Proposal tool. No real OpenAI key or live model was used. `evals/development-cases.json` contains twelve labeled synthetic cases; dataset structure validates, but live quality evaluation remains unrun.

Browser verification covered a custom Garden Club / Example Library program in America/New_York, Wednesday recurrence, PDF upload, original-source download link, baseline comparison, confirmation, approval, and verified publication. The public page shows the custom organization and contact. Mobile resident and program-setup views both measured 390px document width at a 390px viewport. Setup remained locked after the draft. No JavaScript exceptions were reported. The browser upload needed an absolute filesystem path; the initial automation attempt with a relative file path failed before reaching the API.

New screenshots: `artifacts/custom-program-review.png`, `artifacts/custom-resident-mobile.png`, and `artifacts/program-setup-mobile.png`. `artifacts/source-example.pdf` contains only fictional test data. The existing narrated video predates these additions and remains an honest guided-demo recording, not live-model proof.

The renewed separate-process HTTP smoke passed with fixture interpretation: 13 ms for intake including session and 274 ms from approval to verification in that one local run. These are not model latency or performance percentiles.

Private preapproval PDFs are revision-bound, marked unpublished, and do not mutate publication state. Tests reject cross-workspace access and stale revisions. Source quotations now include deterministic page/line references; unmatched quotations never receive a reference.

The final browser-to-API preview check returned HTTP 200, `application/pdf`, 10,865 bytes; the review page displayed source line references. `artifacts/approval-preview.png` records the final review screen.

## Organization pilot release

The additional 24 tests cover organization login, unconfigured-program protection, named authority, editor/owner handoff, viewer restrictions, email-bound single-use invitations, revocation, password changes, multiple programs and tenant isolation, stable pilot links, demo cleanup separation, login limits and secure cookies. Workflow tests cover immutable baseline/inventory snapshots, three fresh-approval follow-up choices, optional Spanish rendering and independent drift detection. Operator tests cover committed WAL backup, isolated restore without overwrite, explicit source retention and asset versioning.

A separate pilot API and worker ran against an isolated fictional database on localhost:8018. Browser verification exercised owner login, baseline configuration, source review, actual verified publication, an unapproved follow-up draft, team invitation creation, and mobile account controls. No invitation was sent. The final restarted browser showed the current pilot interface, its manual-review provider badge, and no JavaScript exceptions. Content-versioned assets fixed stale cached UI observed during verification.

Artifacts: `pilot-login.png`, `pilot-team.png`, `pilot-mobile.png`, and `release-demo.png`. All identities and service information in these images are fictional. This is local verification, not a real organization pilot or an independently audited authentication system. English remains the default; optional Spanish tests establish template consistency, not professional linguistic or accessibility acceptance.

The authenticated separate-process HTTP smoke also passed locally (`artifacts/pilot-http-smoke.json`). CI runs this scenario against a second container in pilot mode, including operator bootstrap from the image, login, unconfigured-public-page rejection, baseline confirmation, named approval, worker read-back, English PDF, disabled Spanish route, unapproved follow-up, forbidden demo reset, and public access after logout.

## Expanded features

Twelve new tests pass for TOTP enrollment, replay rejection, single-use recovery codes, encrypted email reset and retained MFA, independent date-disjoint notices, overlap protection, owner-approved email, uncertain-send handling, Twilio status polling, WordPress pre-write conflict/public read-back, encrypted backup/restore and corrupted-file rejection, and actual scanned-PDF OCR. Provider-specific tests use simulated HTTP/SMTP responses; no real external message or CMS write was sent.

Browser verification exposed a short-desktop sidebar clipping issue after adding account controls. Scrollable desktop navigation fixes it. Login, account-security forms, Connections loading, disabled provider controls, operational status and 390px mobile layout were inspected; no browser exceptions were reported. Optional delivery navigation is now hidden when providers are unconfigured, per the current product scope.

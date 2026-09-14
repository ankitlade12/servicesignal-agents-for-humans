# ServiceSignal

> Scope update: English is the default. Spanish is optional and off unless audience need and owner language review justify it; it is not a launch requirement. This document preserves the original broader proposal. See [current requirement audit](docs/PRODUCT_READINESS.md) for implemented scope and remaining work.
## Product requirements document · v1.0

> **Implementation update — September 13, 2026:** A scoped prototype now exists. See [README](README.md) for implemented behavior and [verification](docs/VERIFICATION.md) for measured checks. This planning document includes deferred requirements; it is not a claim that all features or live model access are complete.

**Owner:** Ankit Hemant Lade  
**Prepared:** September 8, 2026  
**Status:** Ready for a scoped prototype; market differentiation and demand remain hypotheses  
**Target:** Agents for Humans — Good Neighbor Agents  
**Build window:** September 8–13; September 14 reserved for submission and contingency

> Confirm a service change once. See where the community still needs the correction.

## 1. Product decision

Build an agent that helps a small community organization keep temporary changes to its services consistent across its own page, uploaded notices, and a partner listing. The agent reads a change, asks for missing facts, prepares corrections, publishes only within granted authority, and checks the resulting destinations. It tracks unresolved copies and follows up when a temporary change reaches its end date.

The first user is a community-center coordinator managing recurring classes. Residents benefit without creating an account. The first demonstration uses a fictional center and clearly labeled partner simulation. It must execute a real publication and read-back on a controlled website.

The MVP is an application with a persistent background workflow. A conversation helps resolve ambiguity; it is not the entire product. A successful run produces corrected information and evidence of what remains unresolved.

**Prototype commitment:** one organization per isolated demo workspace, up to three programs, six registered information surfaces per program, English intake, and a reviewed Spanish output template. No live integrations with 211, findhelp, or other third-party directories are assumed.

## 2. Problem and evidence

Information about a community service is often copied into several places: a website, a directory, a PDF, a translated notice, and a partner’s resource sheet. Temporary moves, canceled sessions, and changed opening hours require someone to find and update those copies. When responsibility or effective dates are unclear, residents may act on outdated instructions.

Open Referral documents fragmented service directories, duplicated update requests, and provider capacity limitations. Its FAQ emphasizes that reliable information must come from maintained sources and human cooperation; AI cannot create operational truth from absent data. These sources establish the broader problem, not the prevalence of our exact workflow or customers’ willingness to adopt ServiceSignal. [S1][S2]

### Evidence boundaries

| Claim | Status | Product implication |
|---|---|---|
| Maintaining accurate community-service information is a documented challenge. | Supported by Open Referral. | Work with provider-confirmed information. |
| Cross-directory reconciliation is entirely new. | False: Service Net already addresses this. | Attribute existing work and narrow our contribution. |
| Small organizations regularly lose track of temporary changes across flyers and partner copies. | Plausible, not measured in this research. | Test with actual coordinators after the prototype. |
| An agent reduces staff effort while preserving accuracy. | Hypothesis. | Compare against a manual checklist and a basic LLM baseline. |
| ServiceSignal reduces wasted trips. | Intended benefit, not an established outcome. | Measure only in a real pilot; do not claim from a synthetic demo. |

### Competitive context

| Offering | Existing capability | ServiceSignal’s proposed focus |
|---|---|---|
| 211 | Human assistance and community-resource referrals. [S4] | Support information maintenance upstream of referrals. |
| Open Referral / ORServices | Exchange standards and open-source directory tools. [S3] | Reuse the ecosystem; avoid another general directory. |
| Service Net | Conflicting-record reconciliation, updates, synchronization, and edit provenance. Its overview describes exploration of new pilots. [S3] | Temporary changes originating in informal documents, with explicit effective periods and destination-level completion evidence. |
| Yext Listings | Listing distribution and verification across connected publishers. [S5] | Program-level information and registered community notices; broader synchronization is not novel. |
| Transifex | Continuous localization and translation workflows. [S6] | Fact consistency across the small set of notices attached to a service change. Translation alone is not differentiation. |

**Differentiation hypothesis:** source-confirmed, time-bounded changes can be carried from informal notices into connected destinations with less repeated coordinator effort. No claim is made that competitors cannot support this workflow. The prototype must establish usefulness before a defensibility claim.

## 3. Users, jobs, and adoption

| Persona | Job to be done | Successful outcome |
|---|---|---|
| Coordinator — primary | “When a class moves, help me correct every registered place we tell people about it.” | One review, visible exceptions, fewer repeated edits. |
| Partner editor — secondary | “Show me exactly what changed in the listing I own.” | A concise before/after request with source and dates. |
| Resident — beneficiary | “Tell me where and when I can attend.” | A clear public notice with current instructions and a confirmation timestamp. |

The organization administrator assigns the coordinator role. A coordinator may confirm operational facts for configured programs. Partner editors can act only on their own listing. Residents see public information only. Demo accounts are seeded; self-service organization creation is a later feature.

Initial adoption requires a coordinator who knows where the organization publishes information. The MVP scans only registered surfaces. It cannot find every screenshot, printed sheet, private chat, or independently copied notice on the internet.

## 4. Goals and non-goals

### Goals

1. Convert an unstructured update into a precise, reviewable change with supporting source locations.
2. Preserve the distinction between a proposed fact and a coordinator-confirmed fact.
3. Reduce repeated edits across supported destinations after a single explicit approval.
4. Report publication success only after checking the destination.
5. Keep temporary changes visible until their end-date decision is resolved.
6. Produce an accessible public notice and a downloadable replacement flyer.

### Non-goals for this release

- A national directory, resident recommendation engine, or eligibility decision system.
- A guarantee that a service has capacity or that a resident will be admitted.
- Autonomous calls, emails, texts, or edits to unrelated third-party services.
- Arbitrary browser automation across directory login screens.
- Tracking or recalling previously printed material or privately forwarded images.
- Recreating arbitrary flyer layouts or fully supporting all languages.
- Inferring opening status from web consensus, silence, or a successful HTTP request.
- Live emergency, healthcare, housing-placement, or benefits-advice deployment.

These exclusions keep the prototype focused on public program information. They do not imply the application has been certified for any regulated workflow.

## 5. First scenario

**All names and addresses in this scenario are fictional.**

Maple Community Center runs Digital Basics on Tuesdays, 6–8 p.m., in Room A at 100 Example Avenue. The coordinator submits:

> “For September 15 and September 22, Digital Basics will meet in Room B at 200 Sample Street. Same time. Other activities stay where they are.”

The current program has six registered surfaces: its canonical public page, an English flyer, a Spanish flyer, a simulated partner directory listing, a print distribution record, and a read-only partner page.

The agent extracts two affected sessions. If the year, timezone, or program identity cannot be established from confirmed context, it asks. It does not expand the move to every program at the center.

The review screen shows the changed address and room, the two sessions, unchanged hours, source evidence, proposed output artifacts, and actions by destination. The coordinator approves the exact plan. The controlled page updates; replacement flyers are generated; the partner simulator receives a pending correction; the read-only page produces a copyable request; the print record remains an unresolved replacement task.

After publication the agent retrieves the controlled page and compares its structured values with the approved change. A partner’s acknowledgment alone does not count as verification. After the last affected session, the workflow requests confirmation of the next arrangement rather than silently restoring the old venue.

## 6. Scope and priorities

| Priority | Capability | MVP boundary |
|---|---|---|
| P0 | Program setup | Seeded center; coordinator edits program name, timezone, recurring sessions, location, and registered surfaces. |
| P0 | Intake | Pasted message and text-based PDF up to 3 pages / 5 MB. Preserve original and extracted evidence. Reject unsupported files clearly. |
| P0 | Structured change | Location, room, session time, session cancellation, effective dates, affected program/session. |
| P0 | Clarification | One consolidated question card per unresolved decision; answers persist. |
| P0 | Comparison | Registered HTML page, known PDF notices, controlled partner listing. |
| P0 | Approval | Review immutable plan revision, exact destination actions, and output content. |
| P0 | Publication | One real controlled-page adapter; replace that page’s downloadable flyer links. |
| P0 | Notices | Accessible HTML plus simple English PDF; fixed Spanish template reviewed before demo. |
| P0 | Partner workflow | Clearly labeled simulator; copyable request for real read-only surfaces. No live message delivery. |
| P0 | Verification | Read back controlled outputs; display evidence and check time. |
| P0 | Persistence | Durable jobs, bounded retries, deduplication, restart recovery, activity history. |
| P0 | Expiration | Reminder before end and unresolved-state handling at end; no inferred reopening. |
| P0 | Evaluation | Deterministic fixtures, adversarial cases, baseline comparison, resettable demo. |
| P1 | Image intake | OCR/vision for a single-page PNG or scanned flyer; uncertain characters require review. |
| P1 | Exchange export | Validated HSDS-compatible export once version and field mapping are pinned. |
| P1 | Additional adapter | One organization-authorized CMS or directory connector. |
| Later | Live email/translation | Verified sender onboarding, scoped delivery consent, bilingual review workflow. |
| Later | Broad adoption | Multi-organization onboarding, publisher partnerships, billing, larger-scale monitoring. |

**Scope cut order:** remove image intake, exchange export, and additional adapters first. Keep the real publication, read-back verification, ambiguity handling, and end-date behavior. Spanish is template-based in P0; unsupported language output remains pending review.

## 7. Functional requirements and acceptance criteria

| ID | Requirement | Acceptance criterion |
|---|---|---|
| FR-01 | Register a program and its surfaces. | Every surface records owner, URL or artifact ID, language, mode, and last check. Unknown ownership defaults to read-only. |
| FR-02 | Preserve intake evidence. | Each proposed field references source ID, page/paragraph, and supporting text. Re-uploading the same source does not duplicate a change. |
| FR-03 | Resolve program and session scope. | A message affecting one class cannot change another. Ambiguous identity blocks approval. |
| FR-04 | Normalize time. | Store an IANA timezone and explicit occurrence timestamps; show human-readable dates before approval. |
| FR-05 | Ask for missing facts. | Missing year, unclear destination, or overlapping contradictory changes produces a question, not a guessed publication. |
| FR-06 | Compare approved facts with registered copies. | Findings name the exact field and surface. Unreadable content is “could not check,” not “matches.” |
| FR-07 | Approve a specific revision. | Approval binds change version, destination versions, action hashes, output artifacts, reviewer, and timestamp. Editing any approved fact invalidates approval. |
| FR-08 | Enforce write authority. | A server-side check rejects writes to destinations absent from the approved plan or connector scope. |
| FR-09 | Publish scheduled information. | A notice may be published immediately while clearly describing future session dates; current unrelated sessions remain unchanged. |
| FR-10 | Verify publication. | A success response triggers a fresh destination read. “Verified” requires matching expected facts and records the observed content hash. |
| FR-11 | Handle partial success. | One failed destination does not roll back successful independent destinations or produce an “all done” message. |
| FR-12 | Generate replacement notices. | Approved facts populate the template; PDF text extraction confirms dates, address, room, and contact match the approved payload. |
| FR-13 | Track external copies honestly. | Generated/downloaded flyers remain “replacement ready”; print replacement requires manual confirmation and is never called digitally verified. |
| FR-14 | Process a partner correction. | The simulator’s pending, acknowledged, published, and verified stages remain distinct. Real external requests are drafts only. |
| FR-15 | Reconcile later revisions. | A new approved update supersedes affected actions; queued jobs tied to the prior version cannot publish stale facts. |
| FR-16 | Reconfirm at expiration. | The end-date job creates a decision. With no response, controlled public content states that the temporary arrangement ended and the next arrangement is unconfirmed. |
| FR-17 | Resume after interruption. | Worker restart resumes pending work from durable state without repeating a completed write. |
| FR-18 | Isolate demo users. | One visitor’s updates cannot alter another visitor’s workspace or expose intake evidence. |

## 8. User experience

### Screen A — Programs and places we publish

Show program name, next session, last coordinator confirmation, registered surfaces, and unresolved changes. Setup takes the coordinator through program facts and a short “Where do people see this?” checklist. Surfaces are explicit; do not imply internet-wide discovery.

### Screen B — Submit a change

Provide paste and PDF upload. Show file constraints before submission. The next screen displays what the agent understood, including program, affected sessions, old/new facts, and supporting snippets. A user can correct a field directly.

### Screen C — Decision and approval

Show unresolved questions first. Then show a compact before/after comparison and a destination checklist. Group actions as “Can update,” “Needs another owner,” and “Replacement material.” The approval button reads “Approve these updates.” Its scope is visible; it is not ongoing permission for future changes.

### Screen D — Progress and evidence

Use a row per surface: status, relevant facts, last checked time, and next action. Show counts such as “2 destinations verified; 1 partner pending; 2 flyers ready; 1 print task open.” Do not collapse these categories into a misleading completion percentage. Clicking a row opens the observed copy beside approved facts.

### Screen E — End-date decision

Ask “What happens after September 22?” Offer confirm previous venue, extend this arrangement, or enter a new arrangement. Each creates a new reviewable change. Show the proposed public fallback if no decision is made.

### Resident-facing notice

Show program, exact affected dates, hours, venue, room, access/contact instructions already confirmed by the provider, and last confirmation. Distinguish a future notice from the current session. Display an expired/unconfirmed state clearly without inventing a new venue. Keep technical traces and model confidence out of this page.

### Accessibility

Keyboard access to every control, visible focus, labeled inputs, clear errors, semantic headings/tables, adequate contrast, and status text that does not depend on color. HTML is the primary accessible notice. The PDF is a supplementary printable artifact; do not claim PDF accessibility certification without testing it.

## 9. Authority, facts, and temporal rules

**Authority:** A page observation is evidence of what that page says. It is not proof of the provider’s operational arrangements. A coordinator confirms program facts. Neither a newer timestamp nor agreement among several copied pages automatically outranks a confirmed source.

**Conflict policy:** If two confirmed changes overlap for the same program, occurrence, and field, require explicit supersession or a coordinator decision. Preserve both source records. Do not silently choose the newest message.

**Time policy:** Use IANA timezones and UTC storage for execution. The UI shows local time. Store exact occurrences for bounded changes. Normalize intervals as start-inclusive, end-exclusive. A phrase such as “through September 22” must resolve to the end of the affected final occurrence or an explicitly confirmed end boundary. Relative dates are anchored to source context and require confirmation when ambiguous. Reject invalid daylight-saving local times and ask which offset applies to repeated times.

**Approval policy:** Canonical fact confirmation and permission to publish are separate records, even if the same coordinator performs both in one screen. Publication approval includes exact outputs, registered destinations, and the predetermined expired-state notice. Future operational facts still require a new approval.

**Expiry:** Send an in-app reminder 24 hours before the confirmed end, or immediately if less than 24 hours remain. At the end, invalidate the temporary arrangement for future occurrences. Publish only the previously approved fallback on controlled surfaces: the temporary arrangement has ended and future details need confirmation. Keep historical dates available. A reminder delivery does not count as reconfirmation.

**Reversion:** Restoring a previous venue is a new compensating change checked against the latest program version. Never restore a stale snapshot over newer approved information.

## 10. Agent and deterministic responsibilities

Use one Strands agent with bounded tools. Separate logical stages through structured outputs and tool permissions; a multi-agent implementation is not required for the MVP.

| Agent interprets | Application code enforces |
|---|---|
| Which proposed facts a source expresses. | Allowed fields, schema types, tenant/program scope. |
| Whether text is ambiguous and which question helps. | Required fields, valid dates, conflicting intervals. |
| Candidate correspondence between a notice and a program. | Confirmed identity and approved target set. |
| Human-readable change explanation. | Immutable approval hashes and connector permissions. |
| Suggested correction wording. | Template interpolation and locked operational facts. |
| Explanation of failures and next steps. | Durable job states, retries, idempotency, verification. |

### Bounded tool contract

| Tool | Inputs | Output / restriction |
|---|---|---|
| `read_source` | source ID | Extracted text and evidence locations; organization scoped. |
| `get_program_context` | program ID | Confirmed facts, occurrences, active changes, registered surfaces. |
| `propose_change` | structured fields and citations | New draft revision; cannot confirm or publish. |
| `request_clarification` | decision ID, question, affected fields | Persistent in-app question; no email/text delivery. |
| `compare_surface` | surface ID, change version | Observed fields and mismatches; read-only. |
| `prepare_notice` | approved fact set, template ID | Draft artifact plus fact manifest. |
| `enqueue_approved_action` | approval ID, action ID | Server verifies grants/version; never trusts a model-provided approval flag. |
| `read_action_result` | action ID | Execution and verification evidence. |

Publishing credentials stay in deterministic adapters. The model cannot retrieve secrets, invent approval, or invoke arbitrary network writes. Treat source documents as untrusted content: embedded instructions such as “ignore approvals” have no authority.

### Agent run limits

Design targets: at most 10 tool calls per run, a 90-second run deadline, and two schema-repair attempts. Reaching a limit yields a saved draft or actionable failure. Waiting for a person ends the run; a persisted event starts a new bounded run after the answer. Days-long timers belong to the job system, not an agent process.

No new model training is required. Choose an available model based on measured extraction quality, latency, and cost; pin its identifier and the tested Strands version in the implementation lockfile.

## 11. Application architecture

| Component | Recommended MVP implementation | Responsibility |
|---|---|---|
| Web client | React + TypeScript | Coordinator screens, resident notice, partner simulator. |
| API | Python + FastAPI | Authentication, program/change APIs, approval enforcement. |
| Agent runtime | Strands Agents SDK | Interpretation and bounded tool orchestration. |
| Database | PostgreSQL | Canonical versions, decisions, actions, jobs, audit events. |
| Worker | Python process with PostgreSQL job claims | Scheduled events, adapter calls, restart recovery. |
| Files | S3-compatible object storage; local directory in development | Source snapshots and immutable generated artifacts. |
| Controlled publisher | Small authenticated page API | Actual website updates with version preconditions. |
| Partner simulator | Separate listing state and editor UI | Independent publication and failure scenarios; labeled simulation. |

The API and worker share a database but can restart independently. Commit approved actions and outbox jobs in one database transaction. Workers claim jobs with leases; expired leases allow recovery. Reconcile timed-out writes by reading the destination before another write.

Local development uses Docker Compose for app, worker, and database. A hosted demo uses the same components on a persistent container deployment with managed storage. AgentCore is optional; do not make migration to it a critical-path dependency. Pin deployment choices on day one and preserve one-command local startup. These are implementation decisions, not claims about completed infrastructure.

## 12. Data model

All private records carry `organization_id`; IDs and timestamps are generated server-side. Public projections expose only approved notice fields.

| Entity | Required fields and relationships |
|---|---|
| Organization | ID, name, timezone default, retention settings. |
| Membership | user ID, organization ID, role; program/surface grants where applicable. |
| Program | ID, organization, name, timezone, base facts, occurrence schedule, current version. |
| Surface | ID, program, type, owner, language, locator, mode (`controlled`, `read_only`, `artifact`, `manual`), adapter config reference. |
| Source | ID, intake actor, captured time, original bytes/hash, MIME type, extracted text, declared source time. |
| Evidence | source ID, page/paragraph, quote, extraction method, field association. |
| Change | ID, program, revision, proposed fields, affected occurrence IDs, effective interval, source IDs, confirmation status, supersedes ID. |
| Decision | ID, change revision, unresolved fields, question, answer, answering actor, state. |
| Approval | ID, change revision, fact hash, action manifest hash, artifact hashes, fallback content hash, approver, created/revoked time. |
| Action | ID, approval, surface, expected destination version, desired payload/hash, idempotency key, delivery state, retry count. |
| Verification | action, observation time, locator, returned version/hash, extracted facts, comparison result, evidence reference. |
| Artifact | ID, change revision, template/language, object key, content hash, fact manifest, generation/review state. |
| Job | ID, kind, entity/revision, due time, state, lease expiry, attempts, dedupe key. |
| AuditEvent | actor type/ID, event type, entity/revision, timestamp, request correlation ID, before/after hashes. |

Required uniqueness: source hash within the same organization/intake context; action `(surface_id, approved_revision, payload_hash)`; job `(kind, entity_id, revision, due_at)`. A hash is an integrity aid, not proof that a source is accurate.

## 13. State transitions and failure recovery

### Change lifecycle

`DRAFT → NEEDS_CLARIFICATION → READY_FOR_REVIEW → APPROVED → APPLYING → MONITORING → RECONFIRMATION_DUE → ENDED`

`DRAFT` may move directly to `READY_FOR_REVIEW`. A declined proposal becomes `REJECTED`. A later confirmed revision may make a change `SUPERSEDED`. Any substantive edit creates a new revision and removes publication eligibility until approved again. `MONITORING` can contain unresolved surfaces; it is not an all-clear state.

### Destination lifecycle

| State | Meaning | Exit condition |
|---|---|---|
| NEEDS_REVIEW | Planned action lacks valid approval or version match. | New approval. |
| QUEUED | Authorized action is durable and awaits worker. | Claimed job. |
| WRITING | Adapter is executing. | Result or timeout reconciliation. |
| VERIFYING | Write was attempted; outcome is being read. | Match, mismatch, or unavailable. |
| VERIFIED | Retrieved publication matches the approved facts at the recorded time. | Later drift, supersession, or end-date transition. |
| RETRYABLE_FAILURE | Transient transport/rate-limit error. | Successful retry or exhausted attempts. |
| NEEDS_OWNER | No write authority, version conflict, or persistent mismatch. | Owner resolution and fresh check. |
| REPLACEMENT_READY | New flyer exists; distribution is unproven. | Manual replacement acknowledgment where applicable. |
| MANUALLY_CONFIRMED | A named person reports replacement. | Keep attribution; do not label as automated verification. |
| CANCELED | Superseded before execution. | Terminal. |

Retry transient failures after 15 seconds, 60 seconds, and 5 minutes, with jitter. Authentication errors and version conflicts need intervention. Never repeatedly rewrite a mismatching destination without establishing cause. Preserve individual destination results on partial failure. Successful retries do not create duplicate notices.

Before writing, check current change revision and destination version. A stale job is canceled; a stale destination requires a refreshed plan. A completed write that cannot be verified remains unverified. Verification expires as evidence of current state: the UI always shows the observation time and cannot imply continuous certainty.

## 14. Internal API contract

These are proposed application endpoints, not existing third-party APIs.

| Endpoint | Behavior |
|---|---|
| `POST /api/programs` | Create scoped program; validate timezone and required base fields. |
| `POST /api/programs/{id}/sources` | Accept paste/PDF; return source and intake job IDs. |
| `GET /api/changes/{id}` | Return current revision, evidence, decisions, and action plan. |
| `POST /api/decisions/{id}/answer` | Store answer with expected revision; resume interpretation. |
| `POST /api/changes/{id}/approve` | Require exact revision and plan hash; persist approval/outbox atomically. |
| `GET /api/changes/{id}/surfaces` | Return delivery state and timestamped verification per surface. |
| `POST /api/actions/{id}/retry` | Authorized retry only if latest approval is still valid. |
| `POST /api/changes/{id}/reconfirm` | Create follow-on draft; never mutate the expired approval. |
| `GET /notices/{public_id}` | Serve approved public projection without private sources. |
| `POST /api/demo/reset` | Reset only the requesting visitor’s isolated demo workspace. |

Return `409` for revision/precondition conflicts, `403` for authorization failures, and `422` for invalid or unsupported input. Mutating requests accept an idempotency key. The server ignores client-supplied verification results and approval timestamps.

## 15. Content and language quality

Use reviewed templates for English and Spanish notices. Operational facts are supplied as structured fields: exact dates, time, timezone, address, room, and contact. The LLM may propose explanatory prose but cannot modify locked facts. Preserve proper names and addresses; do not translate them into a different place.

Extract text from each generated PDF and compare it with its fact manifest. Verify that visible language labels and affected dates match. If template capacity is exceeded, create an HTML notice and leave the PDF pending adjustment rather than truncating essential details.

An uploaded Spanish notice may be compared using a structured extraction proposal, but uncertain interpretation requires review. Free-form Spanish operational instructions require a bilingual reviewer. If none is available, the MVP uses only the pre-reviewed fixture template and labels broader language support as unavailable.

## 16. Security, privacy, and product boundaries

- Store public service details and coordinator account information; do not require resident profiles, eligibility documents, or case histories.
- Authenticate coordinators and check organization scope on every read/write. Use short-lived access links for private source files.
- Separate source evidence from public notice projections. Strip intake headers and irrelevant personal information from public output.
- Restrict fetched URLs to configured HTTPS hosts; block private/reserved networks, metadata endpoints, redirects to disallowed hosts, and oversized responses.
- Parse PDFs in an isolated worker with limits on file size, pages, and processing time. Do not execute embedded content.
- Store connector secrets outside agent context and logs. Logs use IDs and content hashes unless evidence access is explicitly needed.
- Demo fixtures contain no real beneficiary data. Demo visitors cannot connect arbitrary live destinations or send real messages.
- Proposed retention default: delete original intake files after 30 days unless the organization changes it; retain minimal version/action metadata for 90 days. Support organization deletion and apply it to files, records, jobs, and cached projections. Backup expiry must be documented before a real pilot.

These are product requirements to implement and verify; they are not completed certifications or legal-compliance claims.

## 17. Performance, cost, and observability

All numbers below are targets, not measured results.

| Measure | Initial target / behavior |
|---|---|
| Intake to reviewable proposal | p95 under 60 seconds on supported 3-page fixtures. |
| Approval to first controlled read-back | p95 under 30 seconds excluding injected outages. |
| Public notice load | p95 under 2 seconds in the chosen demo environment. |
| Job recovery | Resume within 60 seconds after worker restart. |
| Timer accuracy | Due jobs start within 60 seconds in a healthy environment. |
| Per-change model usage | Measure tokens/tool calls; soft target under US$0.25 using the chosen model’s actual pricing. |
| Spend control | Configurable daily budget; pause new model runs with a clear message when exceeded. |
| Monitoring cadence | Controlled surfaces every 15 minutes while a change is active; no repeated LLM call when content hash is unchanged. |

Log source, run, decision, approval, action, and verification IDs in one trace. Record model ID, prompt version, durations, token usage, retries, parser failures, and error category. Keep detailed traces restricted to coordinators/developers. Use deterministic comparisons for known fields; reserve model calls for interpretation.

## 18. Evaluation and release gate

Build a proposed 40-case benchmark from fictional sources and small controlled destination fixtures. Keep expected facts and valid actions separate from agent prompts. Assign 20 cases to development and 20 held-out cases to final evaluation. Report the small sample size; it is not a population-level reliability estimate.

| Case family | Count | Example |
|---|---:|---|
| Clean changes | 8 | Two sessions move; hours unchanged. |
| Ambiguous scope/time | 8 | “Next Tuesday,” missing year, repeated local time. |
| Conflicting/superseded updates | 6 | Revised source arrives while an old action is queued. |
| Publication failures | 6 | Timeout after successful write; cached read; version conflict. |
| Artifact/language consistency | 4 | Spanish template retains the wrong date; PDF text omits room. |
| Expiration/reconfirmation | 4 | No response; extension; newer venue overrides old baseline. |
| Authorization/adversarial input | 4 | Cross-organization target; document tells agent to skip approval. |
| **Total** | **40** | |

Compare three workflows: manual checklist with the same surfaces, a basic LLM that extracts a change and drafts messages, and ServiceSignal. Give each the same input and approved ground truth. Record human clarification and correction effort rather than counting agent tool calls as time saved.

### Release gate

- Zero unauthorized writes, false “verified” results, stale-revision publications, and silent restoration of an unconfirmed venue across the release suite.
- All held-out cases either yield correct critical facts or stop with an appropriate unresolved decision; report abstentions separately from successful completion.
- At least 7 of the 8 clean cases complete on controlled surfaces without manual editing of extracted facts; report the held-out subset separately.
- Correct source citation for every published changed field in the suite.
- Restart, duplicate-event, partial-failure, and expiration tests pass against real database/adapter behavior.
- Main user flow passes a keyboard-only check; generated notices pass factual comparison.
- Publish measured latency/cost results and known failures. Do not substitute planned targets for observed values.

### Specific end-to-end scenarios

| Test | Required result |
|---|---|
| Two-session relocation | Only those sessions change; other programs and dates remain intact. |
| Source with two possible programs | No write until identity is resolved. |
| Unauthorized surface added by model | Server rejects action and records the reason. |
| Coordinator edits after approval | Old approval is unusable; a new review is required. |
| Write returns success but page stays old | Remains unverified and surfaces a mismatch. |
| Worker dies after remote write | Read-before-retry prevents duplicate publication. |
| One partner refuses correction | Other successful results remain visible; partner stays unresolved. |
| Flyer download | Mark replacement ready, not distributed or seen by residents. |
| Expired temporary move | Approved expiration notice appears; old venue is not assumed current. |
| Demo clock advances | Only that demo workspace changes; production clocks are unaffected. |

## 19. Six-day implementation plan

Assumption: one full-time engineer comfortable with Python and web applications; scope assumes reuse of standard UI/auth/storage libraries. This is an aggressive prototype plan, not a production estimate.

| Date | Deliverable | Exit condition |
|---|---|---|
| Sep 8 — Day 1 | Repository, schemas, seeded fixtures, local stack, program/surface UI, adapter contract. | A program and six surfaces load; controlled page can be read and versioned through the adapter. |
| Sep 9 — Day 2 | Strands extraction, source evidence, structured proposal, persistent clarification. | Clean and ambiguous messages produce correct drafts or questions. |
| Sep 10 — Day 3 | Approval records, outbox worker, controlled publication, read-back verification. | One real change survives restart and is verified from the rendered destination. |
| Sep 11 — Day 4 | Notice templates, PDF generation, partner simulator, partial-failure UI. | Page, artifacts, and partner statuses are distinct and accurate. |
| Sep 12 — Day 5 | Expiration, supersession, concurrency controls, complete evaluation suite. | Stale approvals and expiry scenarios behave correctly; results saved. |
| Sep 13 — Day 6 | Hosted isolated demo, accessibility pass, baseline results, README, architecture, video. | Reproducible demo and submission materials ready. |
| Sep 14 — Buffer | Final clean setup, links/access check, submit. | Submission accepted before the published deadline. |

If day-three publication/read-back is incomplete, stop adding features and stabilize that path. If no bilingual reviewer is available, use a reviewed fixed Spanish fixture and state the limitation. If third-party credentials are unavailable, keep the partner simulator; never imply a live directory integration.

## 20. Five-minute demonstration

| Time | What the judge sees | Evidence of real work |
|---|---|---|
| 0:00–0:35 | Resident-facing old notice and the coordinator’s scattered copies. | Fictional scenario labeled clearly. |
| 0:35–1:20 | Submit an update with one missing detail; agent asks a focused question. | Source-backed extraction and saved decision. |
| 1:20–2:00 | Before/after plan and explicit approval. | Exact sessions, destinations, and artifacts. |
| 2:00–3:00 | Controlled page changes; replacement notices appear; partner remains pending. | Fresh read-back and different destination states. |
| 3:00–3:45 | Inject a partner failure or destination version conflict. | No false completion; retry or owner action is visible. |
| 3:45–4:25 | Advance the labeled demo clock to expiration. | Reconfirmation decision and approved unconfirmed-state notice. |
| 4:25–5:00 | Show evaluation results and limits. | Measured outcomes, known competitors, honest simulation boundaries. |

Provide a resettable scenario and a visible “Simulated partner directory” label. A clock control exists only in isolated demo mode. The controlled publisher uses actual HTTP writes and reads. No fabricated testimonials, live resident counts, prevented-trip estimates, or implied partnerships.

## 21. Hackathon requirements and submission

The published deadline is September 14, 2026, 5 p.m. PDT (September 15, 00:00 UTC). The project must use Strands Agents SDK. Good Neighbor Agents is the proposed track because community organizations and their residents share the benefit. The overview requests a public MIT/Apache-licensed repository, README, architecture diagram, maximum five-minute demonstration, and AWS Builder ID. It describes AgentCore as optional and a live demo as beneficial. Confirm the full rules before submission. [S7]

Submission package: source and fixture licenses; one-command setup; environment-variable template without secrets; explicit live/simulated connector list; architecture; evaluation results; limitations; video; judge-access instructions. Publish only assets we own or can redistribute. Any reused code or data must be attributed according to its license and the competition rules.

## 22. Pilot, community value, and sustainability

The prototype can proceed without a partner. Real demand and community impact cannot be established from seeded data.

After the hackathon, invite three to five coordinators to walk through recent real changes with their existing tools. Establish the number of destinations they maintain, how they confirm facts, what gets missed, and minutes spent per change. Observe rather than lead them toward our proposed solution.

Run a limited pilot with one consenting organization and one program. The coordinator remains the operational authority. Begin with drafts and controlled owned pages; add partner writes only through explicit authorization. Compare total staff minutes, unresolved-copy duration, factual corrections required, and incorrect publications with the existing workflow.

**Proposed pilot continuation criteria:** at least 30% less median coordinator time per comparable change, no increase in incorrect publications, and a coordinator willing to keep using it. These are decision thresholds, not projected outcomes. Repeated inability to obtain source confirmation is a signal to redesign the workflow rather than increase model autonomy.

Residents should not pay to see notices. Sustainability options to test are sponsored hosting through community networks, municipal support, or an optional hosted service for organizations. Pricing and willingness to pay are open questions. Contribution to an existing Open Referral implementation may create more community value than a separate commercial product.

## 23. Risks and unresolved decisions

| Risk / question | Mitigation or decision |
|---|---|
| Coordinators will not register/update their publication surfaces. | Keep setup short; test whether the known-copy inventory is useful on its own. |
| Provider information is ambiguous or wrong. | Preserve provenance and ask a named authority; do not infer truth from popularity. |
| Existing products already solve the selected workflow adequately. | Compare on actual cases; integrate or contribute if duplication provides no advantage. |
| Third-party sites have no API or reject updates. | Draft-only mode and explicit unresolved state; no unsupported integration promises. |
| Private/printed copies cannot be checked. | Track manual tasks separately and state discovery limits. |
| Model extraction produces convincing errors. | Structured facts, evidence, deterministic validators, approval, held-out testing. |
| Wrong temporal interpretation affects an unrelated session. | Explicit occurrences and timezone confirmation; no broad inferred recurrence edits. |
| Approval becomes stale during publication. | Version preconditions, transactionally queued actions, read-before-retry. |
| Translation changes meaning. | Reviewed templates and locked facts; expand only with bilingual review. |
| Small nonprofits cannot pay for hosting. | Measure costs; explore network sponsorship and open-source deployment. |

Before implementation, choose the deployed model, exact dependency versions, and auth provider. Before a real pilot, choose a participating organization, designated fact authority, permitted destinations, bilingual reviewer if needed, and agreed retention policy. None is a blocker to constructing the fictional prototype.

## 24. Definition of done

- A new developer can start the system from the README and reproduce the fictional scenario.
- A Strands agent extracts a real input, cites it, and handles an unresolved detail.
- A coordinator approves the exact change and actions.
- At least one actual controlled public page is updated and independently read back.
- Generated artifacts, simulated partner activity, and manually confirmed work have truthful labels.
- Temporary changes expire without inventing future arrangements.
- Durable jobs, stale revisions, duplicate events, and partial failures meet the release gate.
- The 40-case evaluation and baseline results are recorded with limitations.
- The repository, architecture, demo, and competition submission package are ready.

## 25. Sources and attribution

Research reviewed September 8, 2026. Vendor descriptions are not independent product tests. Product requirements, scenarios, targets, architecture, and implementation estimates in this document are proposed design decisions.

- **S1 — Open Referral, Strategic Overview:** documented fragmentation, maintenance incentives, and interoperability approach. https://openreferral.org/about/strategic-overview/
- **S2 — Open Referral, FAQ:** provider update burden and limits of AI when reliable source information is missing. https://openreferral.org/faq/
- **S3 — Open Referral, Technology Overview:** HSDS, ORServices, and Service Net capabilities. https://openreferral.org/about/technology-overview/
- **S4 — United Way 211:** community-resource assistance and referrals. https://211.org/
- **S5 — Yext Listings:** connected listing distribution and publication verification. https://www.yext.com/platform/listings
- **S6 — Transifex:** localization and continuous translation workflows. https://www.transifex.com/
- **S7 — Agents for Humans:** deadline, tracks, SDK requirement, and submission overview. https://agentsforhumans.devpost.com/

**Responsible positioning:** ServiceSignal is a proposed agent for maintaining registered community-service notices. Its broader problem is documented; its specific market differentiation, adoption, and community impact still require evaluation.

# Product readiness and complete requirement audit

ServiceSignal currently completes a **fictional, single-program coordination workflow**. It is not ready to advertise as a live source of community-service information. The central value is helping a coordinator turn one confirmed change into a checked notice and a visible list of copies still needing attention.

This audit compares the implementation with every functional requirement in `ServiceSignal_PRD.md`. “Implemented” refers to the stated boundary, not production certification. No pilot organization has been selected, and no live model invocation has succeeded yet.

## Functional requirements

| Requirement | Current evidence and boundary | Remaining work |
|---|---|---|
| FR-01 Program and surfaces | Editable program, organization, IANA timezone, weekdays, hours, venue, public contact; setup locks after first draft. Four fixed surfaces. | Editable surface owners/languages/URLs and safe baseline revision after existing changes. |
| FR-02 Source evidence | Paste and text-PDF intake; original PDF bytes, SHA-256, page-marked text, private download, deduplication, verified literal quotes with page/line references. | Retention controls beyond demo expiry. |
| FR-03 Program/session scope | Review checks configured program, timezone and weekdays. Exact dates only. Wrong scope rejects. | Real organization identity and named authorized reviewers. |
| FR-04 Time normalization | IANA timezones, explicit dates, same-day times, UTC expiry. DST gap/repeated-hour rejection. | A UI for selecting a repeated-hour offset; overnight sessions. |
| FR-05 Clarification | Consolidated model questions; saved manual fact confirmation; recovery after model error. | Evaluate live extraction on ambiguous and contradictory sources. |
| FR-06 Compare copies | Fresh rendered-HTML comparison; observed facts/hash/time; baseline/proposal review table. | Field-level mismatch explanations for external copies and comparison of existing PDFs. |
| FR-07 Exact approval | Immutable fact revision and plan hash; destination version; exact fallback; unsaved edits disable approval. | Named reviewer identity. |
| FR-08 Write authority | Publisher secret, active job lease, approved revision, server-owned target, destination version. | Organization-scoped permissions before connecting a real CMS. |
| FR-09 Future notices | Publish now while listing only explicitly affected future sessions. | None for this single-active-notice boundary. |
| FR-10 Read-back | Actual HTTP publication followed by separate rendered-fact comparison; timestamp and content hash. | Verification of additional real adapters. |
| FR-11 Partial success | Successful owned page remains independent of failed/simulated partner and manual print work. | None for the fixed four-surface boundary. |
| FR-12 Replacement notices | English PDF and HTML from approved facts, QR URL, contact instructions; PDF extraction tests and private revision-bound preapproval PDF preview. | Reviewed Spanish template, certified PDF accessibility if required. |
| FR-13 External copies | Replacement-ready PDF and attributed manual print confirmation remain distinct. | Real distribution inventory with assigned owners. |
| FR-14 Partner correction | Acknowledgment/publication/refusal simulator; copyable correction request; no messages sent. | Real read-only surface registration and observed-publication state; partner authorization for writes. |
| FR-15 Later revisions | Explicit whole-notice supersession; old jobs canceled; stale writes rejected. | Concurrent disjoint changes and occurrence-level merge UI. |
| FR-16 End-date | Durable reminder/expiry; approved fallback; resident read safeguard during worker outage. | Guided extend/restore/new-arrangement decision choices; each must create a new approval. |
| FR-17 Restart recovery | Durable leases, idempotent publisher, bounded retry, recurring drift check, heartbeat readiness. | Deployment-specific alerts, scheduled backups and a documented restore drill. |
| FR-18 Isolation | Random HttpOnly session, source/document isolation, same-origin writes, seven-day expiry/reset. | Persistent real organization authentication, roles, revocation, abuse controls and data lifecycle. |

## Other PRD commitments

| Area | Status |
|---|---|
| P0 text PDF intake | Implemented: 3 pages, 5 MB, 6,000 extracted characters; unsupported formats rejected. Original retained privately. |
| P0 Spanish notice | Not implemented. Requires a reviewed fixed template and bilingual acceptance test before being offered as reliable. |
| P0 destination inventory | Four fixed surfaces implemented; the six-surface PRD scenario and arbitrary registration remain incomplete. |
| P0 live extraction | OpenAI, Anthropic and Bedrock adapters exist through Strands. OpenAI contract test uses a local fixture; live smoke awaits funded access. |
| P0 evaluation | 63 automated tests at the recorded run; twelve labeled development cases and a live evaluation runner. No live evaluation score, held-out 40-case benchmark, baseline study, or coordinator time-saving study. |
| Accessibility | Responsive semantic HTML, labels, keyboard focus, non-color status text; browser smoke checks. No full WCAG audit or certified PDF accessibility. |
| P1 OCR/vision | Not implemented. Scanned PDFs are rejected with a transcription instruction. |
| P1 HSDS exchange | Not implemented; schema/version mapping must be pinned and validated. |
| P1 real CMS/directory adapter | Not implemented; requires a named authorized destination. |
| Later email/SMS | No sender integration or delivery consent. Copyable drafts only. |
| Later multi-organization platform | Not implemented; anonymous demo sessions do not establish operational authority. |
| PostgreSQL/S3/React architecture | Deliberate implementation substitution: one persistent host, SQLite, plain JS, in-memory generated PDFs, private PDF blobs. |
| Scaling/cost | Model call caps, bounded invocations, two parser slots, upload/storage caps. No load benchmark or dollar-cost guarantee. CLI eval calls are outside API quotas. |
| Brand | ServiceSignal remains a working title with a known name collision. Resolve before a public product launch. |
| Community impact | Hypothesis only. No organization, resident usage, avoided trip, referral, or time-saving outcome is claimed. |

## Next release sequence

1. **Prove live AI.** Configure a funded OpenAI key in the server environment, set `AGENT_PROVIDER=openai`, restart, run the live smoke and development evaluation. Investigate every failed scope/clarification case. Record actual model/usage/latency. Build a separate held-out release set before claiming quality.
2. **Finish the remaining P0 review surfaces.** Add reviewed Spanish templates and editable destination ownership. Preserve revision-bound approval throughout.
3. **Choose one consenting partner.** A library class or community-center activity is a useful initial category. Identify the actual information owner and the person who can approve public changes. Until then, keep the demo fictional.
4. **Build the pilot's access boundary.** Named coordinator login, organization roles, revocable sessions, real clock, stable public URLs, retention/deletion settings, production monitoring and backups. Demo sessions and clock controls must not be used for real service delivery.
5. **Deploy and verify on the chosen host.** Persistent storage, HTTPS, funded model, readiness monitoring, backup restore, restart tests and scoped publishing authorization. An external link is not evidence of a working deployment until the full flow passes there.
6. **Run a supervised pilot.** Start with one class and four explicitly registered surfaces. Confirm each change with the named coordinator. Record coordinator minutes, errors caught, unresolved copies and end-date follow-up. Obtain permission before interviews or outreach; this implementation sends none.
7. **Expand after evidence.** Add the most-used partner destination, then additional programs and bilingual output based on actual coordinator/resident needs.

## Community adoption

The product's distribution mechanism is the notice itself: a readable mobile page and printable QR link that residents can share through existing community channels. The same URL shows the latest approved notice for the demo's seven-day lifetime; a real pilot needs stable authenticated ownership and persistent URLs first.

A useful adoption test is whether a coordinator chooses to use the product for a second real update, and whether unresolved-copy work becomes faster and more visible. Ask coordinators whether they would introduce another program owner after the pilot. These are proposed measurements, not results. Avoid collecting resident identity merely to measure page views.

The adoption plan in `PILOT.md` defines the initial interviews and time-saving hypothesis. No mechanism can promise virality; trustworthy, locally useful notices are the basis for organic sharing.

## Hackathon submission gates

The public MIT repository, README, architecture and guided video are prepared. Live Strands evidence, the entrant's AWS Builder ID, public YouTube/Vimeo upload and final Devpost submission remain open. A hosted demo is optional under the rules. The current narrated recording explicitly identifies fixture mode and predates program/PDF additions. Re-record with successful live execution before presenting it as live agent evidence.

The official rules require Strands and do not constrain the model provider; OpenAI through Strands appears compatible. Check `SUBMISSION.md` for the deadline and exact account-bound items. Hackathon eligibility and production readiness are separate checks; satisfying one does not establish the other.

# Product readiness and requirement audit

ServiceSignal implements a complete controlled publication workflow and an invite-only organization pilot mode. No consenting organization, resident usage, successful live model evaluation, or public cloud deployment has been established. This audit records implementation boundaries, not production certification.

English is the default. Spanish is optional and off; the earlier PRD's bilingual requirement is superseded by the current English-first scope. Enable additional language coverage only after validating audience need and reviewing the templates.

## Functional requirements

| Requirement | Implemented | Boundary or remaining work |
|---|---|---|
| FR-01 Program and surfaces | Confirmed baseline, multiple pilot programs, partner/print owners and reference URL, immutable reviewed context | Four fixed surface types; arbitrary destinations and connectors absent |
| FR-02 Evidence | Paste/text PDF, original bytes, content hashes, page/line references, deduplication, private downloads, operator retention | OCR implemented; scheduled encrypted backups and optional source retention implemented; organization policy and off-host storage configuration remain |
| FR-03 Program/session scope | Program/timezone/weekdays validation, exact occurrences, named authorized reviewers | Requires a real owner to confirm actual program information |
| FR-04 Time normalization | Explicit dates, IANA zones, UTC expiry; ambiguous/nonexistent local times rejected | Overnight sessions and explicit repeated-hour offset selection absent |
| FR-05 Clarification | Consolidated questions, saved manual facts, model-error recovery | Live extraction quality and ambiguity benchmark unverified |
| FR-06 Compare copies | Baseline/proposal comparison and observed rendered facts, field mismatch details | No crawling or comparison against arbitrary external PDFs |
| FR-07 Exact approval | Named confirmation/owner approval, revision, plan hash, baseline and inventory snapshot | Multiple date-disjoint pilot notices; partial-overlap replacement rejects missing previously covered dates |
| FR-08 Authority | Organization roles, server-side owner validation, publisher secret, active lease, approved revision, destination version | Optional dedicated WordPress adapter with public read-back; live credentials and independent audit pending |
| FR-09 Future notices | Immediate notice listing only approved future sessions | Multiple independent date-disjoint notices in pilot mode |
| FR-10 Read-back | Separate HTTP read of visible facts; timestamp/hash per enabled language | Only the controlled page is independently verified |
| FR-11 Partial success | Page success independent of unresolved partner/print tasks | Partner states in demo remain simulations |
| FR-12 Replacement notices | English HTML/PDF, permanent QR, private revision-bound preview; optional fixed Spanish template | No professional language acceptance or PDF accessibility certification |
| FR-13 External copies | Assigned print owner and placement notes, replacement PDF, attributed manual confirmation | Already printed text and screenshots remain outside automated control |
| FR-14 Partner correction | Named owner/reference URL, copyable request, explicit owner follow-up | Optional SMTP/Twilio/WordPress adapters; disabled by default and no live provider delivery established |
| FR-15 Revisions | Explicit whole-notice supersession, canceled old jobs, stale-write rejection | Independent disjoint notices implemented; replacements must include the full overlapping notice date set |
| FR-16 End-date | Reminders, approved unconfirmed fallback, extend/restore/new drafts requiring fresh approval | No automatic assumption that the baseline has resumed |
| FR-17 Recovery | Durable leases, retry, idempotency, drift checks, heartbeat; online backup and isolated restore tools | Encrypted scheduling and S3-compatible upload implemented; actual storage credentials and external alert routing require an operator |
| FR-18 Isolation | Organization accounts, roles, invitations, session revocation, login limits, demo cleanup separation | TOTP/recovery codes and optional email recovery implemented; managed identity and independent review absent |

## Additional commitments

| Area | Current status |
|---|---|
| Automated verification | 99 passing tests; lint and JS syntax checks; real browser and separate-process HTTP flow |
| Live AI | Strands adapters for OpenAI, Anthropic and Bedrock. Real SDK contract passes against a local fixture. No successful live invocation or quality score |
| Evaluation | Twelve labeled synthetic development cases and runnable evaluator; no held-out 40-case study or manual/LLM baseline comparison |
| Accessibility | Semantic labels, keyboard focus, responsive views and basic browser checks; full WCAG/PDF audit absent |
| Data exchange | No HSDS export or import adapter |
| Deployment | Persistent single-host API/worker and SQLite; container and CI supplied; no running cloud service |
| Account lifecycle | Operator owner provisioning/recovery; owner invites editor/viewer and revokes access; single-use initial-owner setup; no public signup or separate mailbox-verification workflow |
| Data lifecycle | Explicit source retention and WAL-safe backup/isolated restore; scheduled encrypted snapshots, optional S3 upload and explicit retention configuration; live off-host storage still unconfigured |
| Performance and cost | Model call caps, bounded invocations/uploads, limited concurrent parsing/password derivation; no load-tested capacity or measured live cost |
| Community impact | No selected organization, resident outcome evidence, measured time saving, or demonstrated growth |

## Launch sequence

1. Select one consenting organization and its accountable owner. Confirm baseline, public contact, copy inventory and source-handling expectations.
2. Provision pilot mode on a persistent HTTPS host; configure secure cookies, live provider, readiness alerts, body limits, disk monitoring and operator recovery.
3. Run a successful live Strands smoke and the development evaluation. Inspect every failure before enabling live interpretation for the pilot.
4. Perform the actual hosted login → intake → confirmation → owner approval → independent read-back → PDF → follow-up flow. Restore a backup to an isolated host and verify it.
5. Observe at least three coordinators' existing process and compare pilot changes with a manual checklist. Include correction/review time and unresolved copies in the measurement.
6. Expand only after repeated coordinator use and reliable notices. Add the destination and language that actual users need most.

The product's shareable notice and QR link can support referrals through existing community channels. This is an adoption hypothesis; page views and a polished demo do not establish community benefit or virality. See [competitive positioning](COMPETITIVE_POSITIONING.md) and [pilot measurements](PILOT.md).

## Hackathon readiness

Public MIT source, README, architecture, and a narrated fixture walkthrough are prepared. Live Strands evidence, entrant AWS Builder ID, public YouTube/Vimeo upload and Devpost submission remain open. Hosting is optional under the official rules. The existing recording predates pilot accounts and must not be described as a successful live-agent demonstration. See [submission checklist](SUBMISSION.md).

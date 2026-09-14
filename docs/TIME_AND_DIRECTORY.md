# Overnight sessions, repeated hours, directory exchange and copy inspection

## Session dates and timezones

In Programs, select **Session ends → The next day (overnight)** for an overnight baseline. Repeat that choice in a temporary update when needed. Affected dates and recurring weekdays always refer to the session's start date. Sessions span at most 24 local hours; clock changes can alter elapsed duration.

In fact review, open **Daylight-saving repeated-hour choices**. Each affected start date has independent first/second selections for the start and end clock times. Leave automatic for unambiguous times. The first occurrence is before the backward clock change; the second is after. The end selection applies on the next day when overnight is selected. Invalid spring-forward clock times are rejected, even if an occurrence is selected. A follow-up draft accepts new occurrence choices; it never carries a previous date's choices into a different date.

**Check exact session times** shows full dates, offsets and corresponding UTC instants. The server checks real chronological order, and expiration uses the final actual end instant. Public HTML, individual/collection notices and PDFs include exact offset-bearing intervals. Changing an occurrence choice changes the approval hash. Overnight overlaps across different start dates are rejected unless the replacement preserves the previous affected dates.

Implementation uses Python's [zoneinfo fold behavior](https://docs.python.org/3.12/library/zoneinfo.html) with UTC round-trip checks for nonexistent times.

## Community directory exchange

Programs → **Community directory exchange** exports a confirmed program as an HSDS 3.2 service JSON record. It contains a stable UUID, organization, baseline location/schedule description, current notice URL and date-scoped approved alerts. Baseline descriptions deliberately retain IANA timezone context rather than asserting one fixed UTC offset across daylight-saving changes. Private sources, account email addresses and approval credentials are excluded. Export is a downloaded file; it does not submit to an external directory.

An owner can upload one service object, a service array or a `services` collection, up to 50 records/2 MB. Validation uses an offline adaptation of the [official HSDS 3.2 compiled service schema](https://github.com/openreferral/specification/blob/3.2/schema/compiled/service.json). Preview shows source identity/status and suggested fields. Review your authority, timezone, weekdays, hours and location before creating a new unconfirmed program. Complete its baseline setup before creating a notice. Importing never publishes or grants access to the source organization.

The first source location/schedule may supply suggestions. Other locations, complex recurrences, eligibility, alerts and additional fields remain in the original source download; they are not silently interpreted or applied. Numeric timezone offsets do not establish an IANA zone. CSV datapackages and directory-specific APIs are outside this JSON exchange profile. Imported records are retained with hashes; pending previews expire after 24 hours. Repeating the same confirmation returns the same newly created program.

The schema is CC BY-SA 4.0; see `schemas/README.md` and the upstream license. Application code remains MIT.

## External copy inspection

After facts are confirmed, open the update's **Inspect an external copy** panel. Supply a public HTTPS URL and confirm the read. HTML, plain text and PDFs (including bounded English OCR) are supported; PDFs are limited to three pages/5 MB. A check records the final URL, content hash, time, revision, expected text and observed excerpts. Check history stays private to the workspace, with the latest 100 retained (20 shown in the dashboard).

Results say **Text found** or **Not found in this format**. Exact text presence cannot establish correct context, current service status, CSS-rendered visibility or a successful outside correction. Different date/time formatting may require manual review. Checks never change an outside website, send a correction request, or mark a partner action verified. Recheck when facts or external content change; inspection is on demand.

Only public HTTPS on port 443 is allowed, without embedded credentials. Every redirect is independently validated. Connections pin the validated public IP while preserving TLS hostname verification, and do not forward app cookies, credentials or proxy settings. Private/reserved/mixed DNS targets, compressed responses, excessive redirects, large content and timeouts are rejected. Scripts are not executed; login-protected or JavaScript-only pages may need manual review. Limits are 20 checks per workspace/day, 200 globally/day and two concurrent readers.

## OpenAI key

Local setup: put `OPENAI_API_KEY=your-key` in the ignored `.env` file at the repository root. Set `AGENT_PROVIDER=openai` for a local live app. Restart after changing environment settings.

Hosted setup: Railway → ServiceSignal project → servicesignal service → production → Variables. Set `OPENAI_API_KEY` privately and `AGENT_PROVIDER=openai`; deploy the changes. A local `.env` file is excluded from container uploads, so local and hosted configuration are separate. Never put the key in browser JavaScript, source control or chat.

The [OpenAI quickstart](https://developers.openai.com/api/docs/quickstart) documents server-side environment configuration. ServiceSignal invokes OpenAI through the Strands adapter and keeps confirmation and publication authority in application code.

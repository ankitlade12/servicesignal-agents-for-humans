# Deployment runbook

## Local

`uv sync --frozen && bash scripts/start.sh` starts the API and separate worker on localhost:8017. A persistent SQLite database is created automatically. The frontend needs no build and makes no external font/script requests.

## Persistent container

Use `docker compose up --build`. The named `signal-data` volume holds the database. The image uses a non-root user. Do not run multiple replicas with independent disks. The host must provide Python-compatible outbound HTTPS access for the selected model provider.

For a hosted VM/container:

1. Build the supplied image and mount a persistent writable volume at `/app/data`.
2. Keep the default single API/worker pair. Expose port 8017 through an HTTPS reverse proxy.
3. Set `PUBLIC_ORIGIN=https://your-actual-host`, `COOKIE_SECURE=1`, and the selected provider configuration.
4. Keep `PUBLISHER_ORIGIN=http://127.0.0.1:8017` internal to the container. The worker never accepts visitor-provided destinations.
5. For Bedrock, use a scoped instance/task role with invocation permission for the chosen model/inference profile. Do not bake credentials into an image or commit them.
6. Set daily/workspace model-call limits to an appropriate budget. The current limits are call counts, not dollar-cost guarantees.
7. Check `/api/health` (API/database) and `/api/ready` (worker readiness), then complete the actual browser flow. Check the worker logs and verify the public QR target uses the hosted HTTPS origin.
8. Test a restart after publication, a retry, and expiry. Retain the volume during upgrades.

`/api/health` checks the API/database. `/api/ready` returns 503 if no worker heartbeat has been recorded within 90 seconds; the container health check uses readiness. The coordinator sees a warning while the worker is unavailable. Publication and drift checks can be delayed during outages. A running API shows the already-approved expiration fallback in resident HTML/PDF after the final session, independently of the expiry job; verification status remains an observed worker result. Configure deployment-specific alerts for failed readiness, disk capacity, and queued/failed jobs.

## External prerequisites still needed

- An AWS profile/role with Bedrock model invocation access, or a funded supported provider key for live Strands calls.
- A persistent hosting destination and its account access.
- An actual HTTPS public origin before printing or distributing QR codes.
- The entrant's AWS Builder ID and Devpost account for submission.

No hosting resources or IAM policies were created by this implementation. The image build passed GitHub CI; the workflow also includes a running-container HTTP smoke test. Configure and test the intended persistent host separately; CI success does not establish a deployed service.

## Model access check

`uv run python scripts/check_access.py` tests AWS identity and optional catalog access without printing credentials. Catalog access is not required if the permitted model ID is known. The decisive check is `PYTHONPATH=. uv run python scripts/smoke_agent.py` with a live provider configured. It must pass before claiming live interpretation works.

## Demo data and reset

Anonymous demo sessions use random HttpOnly cookies; only a hash is stored. Sessions expire after seven days. A reset deletes the workspace, sources (including original uploaded PDFs), approvals, publications, jobs, and events via foreign-key cascades. Public links intentionally stop working after reset. Anonymous sessions are appropriate for fictional demos, not real organization authorization.


## Upgrade and backup

The database initializer adds the program configuration column and documents table to existing databases without deleting existing workspaces. Back up before upgrading: use SQLite's online backup API (not a raw copy of only the main file while WAL is active). Restore to an isolated path first and run the complete smoke flow before serving traffic. Online backup and isolated restore utilities are supplied below; scheduling and off-host storage remain operator configuration.

PDF extraction runs in a separate process with an eight-second wall timeout and five-second CPU limit. Linux additionally limits the parser address space to 512 MB. Only two parsers run concurrently; storage is capped at ten PDFs per workspace and 500 MB total. Configure a matching reverse-proxy body-size limit and disk monitoring on the host. These parser limits do not certify arbitrary untrusted uploads as harmless.

## Organization accounts

Set `SERVICESIGNAL_MODE=pilot` in `.env` or the deployment environment. Use a separate pilot database from disposable demo data when operating a real service. The mode is read by both processes; restart them after changing configuration. Pilot sessions expire after 12 hours, while public notice URLs remain stable after logout. Pilot data is excluded from anonymous demo cleanup.

Provision the first owner from the server checkout:

```bash
PYTHONPATH=. uv run python scripts/manage_accounts.py create-organization \
  --organization "Your organization" --email "owner@example.org" --name "Coordinator name"
```

Or inside the running Compose container:

```bash
docker compose exec servicesignal env PYTHONPATH=. .venv/bin/python scripts/manage_accounts.py create-organization \
  --organization "Your organization" --email "owner@example.org" --name "Coordinator name"
```

Passwords are entered through a hidden prompt. Each new program starts unconfigured; an owner must confirm its facts before intake or public access. Owners approve publication, manage baselines and issue editor/viewer invitations. Editors prepare and confirm facts; viewers read records. All organization members can access that organization's programs and their private sources; this is not per-program membership.

Invitation links are single-use, email-bound, and expire after 24 hours. They grant access to whoever holds the link and supplies the matching email; there is no mailbox verification. Send each link through an appropriate private channel. The application sends no messages. Owners can revoke editor/viewer access and all sessions; owner recovery is an operator function.

```bash
PYTHONPATH=. uv run python scripts/manage_accounts.py reset-password --email "owner@example.org"
```

Recovery revokes sessions and records an operator event. Establish the owner's identity before using it. There is no self-service forgotten-password flow, MFA, owner-transfer UI, or account reactivation UI. Configure external login/traffic controls at the reverse proxy. Application address-based login limits use the immediate peer address, so a proxy may aggregate callers; forwarded headers are deliberately not trusted as rate-limit identity.

## Backup, restore and retention commands

The supplied utilities use SQLite's online backup API, verify integrity, and refuse to overwrite an existing destination. Backup files contain private source material and account data; store them under the deployment's access and retention policy. These commands do not schedule backups or upload them off-host.

```bash
PYTHONPATH=. uv run python scripts/data_ops.py backup --output data/backup-before-upgrade.sqlite
PYTHONPATH=. uv run python scripts/data_ops.py restore --input data/backup-before-upgrade.sqlite --output data/restore-check.sqlite
```

Run the restored copy as an isolated API/worker pair on another port and verify account access, publications, PDF generation and worker readiness. Stop the active pair before pointing it at a restored database. Preserve the previous database until the restored service passes verification.

```bash
# Preview counts; no deletion by default.
PYTHONPATH=. uv run python scripts/data_ops.py retention --days 90
# Apply the reviewed retention decision.
PYTHONPATH=. uv run python scripts/data_ops.py retention --days 90 --apply
```

Retention removes old terminal-change source text/proposal quotations and eligible original PDFs. Approved facts, source hashes and audit events remain. Documents referenced by active changes are preserved. This is selective source retention, not account erasure or backup deletion. Add a schedule only after the real organization chooses its policy.

Database initialization uses additive migrations for organization identity, roles, sessions, program/inventory snapshots, named actors and per-language evidence. Existing anonymous demo data remains anonymous; it is not silently converted into an organization.

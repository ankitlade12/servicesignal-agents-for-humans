# Railway and Render deployment

The app needs one persistent service running the API, publication worker, delivery sender and scheduled maintenance processes. SQLite and the encryption key must survive restarts. The supplied container starts the application processes as a non-root user after preparing the mounted data directory.

## Railway

Deploy this repository with its Dockerfile and `railway.json`. Attach one volume at `/app/data`, use one replica and generate an HTTPS service domain. Set:

```text
SERVICESIGNAL_MODE=pilot
SERVICESIGNAL_DB=/app/data/servicesignal.sqlite
SERVICESIGNAL_HOST=0.0.0.0
COOKIE_SECURE=1
AGENT_PROVIDER=fixture
BACKUP_DIRECTORY=/app/data/backups
PDF_OCR_ENABLED=1
```

The launcher honors Railway's PORT and RAILWAY_PUBLIC_DOMAIN. It keeps worker publication traffic on localhost. Set PUBLIC_ORIGIN explicitly if using a custom domain. Railway volumes must be attached before real program data is entered; see [Railway volume documentation](https://docs.railway.com/volumes/reference).

Switch AGENT_PROVIDER to `openai` only after setting a funded OPENAI_API_KEY and passing the live smoke. A fixture deployment remains a manual-review application and is not evidence of live AI execution.

## Render

The repository contains `render.yaml`, defining a Docker web service, 5 GB persistent disk, single instance, and `/api/ready` health check. It selects the documented `1c-2g` compute plan to leave room for OCR and password derivation. Deployment incurs the account's applicable hosting/storage charges; inspect the plan in the Render dashboard before deploying. No Render resource has been created by this implementation.

The launcher derives the public origin from RENDER_EXTERNAL_URL and honors PORT. Provision accounts from the running service shell, after the persistent disk is mounted. See [Render Blueprints](https://render.com/docs/blueprint-spec) and [persistent disks](https://render.com/docs/disks).

## Initial owner setup

For an empty installation without shell access, generate a random token with `secrets.token_urlsafe(32)` and configure SERVICESIGNAL_BOOTSTRAP_TOKEN, BOOTSTRAP_OWNER_EMAIL and BOOTSTRAP_ORGANIZATION privately in the hosting environment. The launcher creates one email-bound owner invitation before starting the workers. Open `https://YOUR_DOMAIN/#join=TOKEN` within 24 hours and choose your own password. After startup confirms creation, clear the bootstrap token from the hosting environment. Only its hash remains in the database; a persistent marker prevents reissuing it on restart. Never expose the token in logs, commits or screenshots.

Alternatively, create a private, single-use owner invitation from the service shell. This leaves the initial program unconfigured and inaccessible publicly until the owner confirms real facts.

```bash
PYTHONPATH=. .venv/bin/python scripts/create_owner_invitation.py \
  --organization "Your organization" --email "owner@example.org" \
  --origin "https://YOUR_DOMAIN" --output /app/data/owner-setup.txt
```

Retrieve the restricted file privately and open its link within 24 hours. The owner supplies their name and chooses a password. No email is sent. The file contains an access-bearing link: do not commit it, include it in screenshots, or place it in a public directory. Existing owners use the documented recovery command; do not repeatedly create replacement organizations.

## Scheduled backup and recovery

BACKUP_DIRECTORY enables daily encrypted online snapshots. BACKUP_INTERVAL_SECONDS defaults to 86400, with a minimum of one hour. BACKUP_KEEP_COUNT defaults to seven and keeps at least two local snapshots. SOURCE_RETENTION_DAYS=0 disables automatic source deletion; a value of at least seven enables the selected policy after a successful backup.

The encryption key is SERVICESIGNAL_ENCRYPTION_KEY (a Fernet key), or a restricted file next to the database when the variable is unset. Preserve this key separately from the database. It protects MFA secrets, reset messages and backup file keys. Losing it prevents decrypting those records and backups. The encrypted backup format streams AES-GCM ciphertext and authenticates the file before a restore is accepted.

For off-host copies, configure BACKUP_S3_BUCKET, optional BACKUP_S3_ENDPOINT/PREFIX and the normal AWS credential chain. S3-compatible storage is optional. An account-page status reports whether the latest off-host upload actually succeeded. A backup on the app's own volume alone does not protect against loss of that volume.

```bash
PYTHONPATH=. .venv/bin/python scripts/data_ops.py decrypt-backup \
  --input /path/to/snapshot.signal-backup --output /path/to/new-copy.sqlite
PYTHONPATH=. .venv/bin/python scripts/data_ops.py restore \
  --input /path/to/new-copy.sqlite --output /path/to/isolated-restore.sqlite
```

Both commands refuse to overwrite existing destinations. Test the isolated copy with the same encryption key before switching a stopped service to it. The local encrypted round-trip and corruption-rejection tests do not substitute for a restore exercise on the chosen hosting account.

## Monitoring

Use `/api/ready` for API/database plus publication-worker readiness. Configure the hosting platform's health/restart behavior and alerts for disk pressure and availability. Account & team shows queued/failed jobs and backup status. For an external monitoring system, set OPERATOR_METRICS_TOKEN and poll `/internal/metrics` with `Authorization: Bearer <token>`. It exposes operational counts, storage sizes and backup/worker status, not private source text.

The application does not configure an external alert recipient or claim a completed security/accessibility audit. Complete a hosted restore drill and operational review before relying on real community data.

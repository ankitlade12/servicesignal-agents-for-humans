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
7. Check `/api/health`, then complete the actual browser flow. Check the worker logs and verify the public QR target uses the hosted HTTPS origin.
8. Test a restart after publication, a retry, and expiry. Retain the volume during upgrades.

The health endpoint checks the API/database, not worker liveness. Monitor the worker process and pending jobs independently. If the worker is down, publication, drift checks, and expiration may be delayed. A production process supervisor and alerting configuration remain deployment-specific.

## External prerequisites still needed

- An AWS profile/role with Bedrock model invocation access, or a funded supported provider key for live Strands calls.
- A persistent hosting destination and its account access.
- An actual HTTPS public origin before printing or distributing QR codes.
- The entrant's AWS Builder ID and Devpost account for submission.

No hosting resources or IAM policies were created by this implementation. The supplied Docker configuration must be built and tested on the intended host; local application verification does not prove cloud deployment readiness.

## Model access check

`uv run python scripts/check_access.py` tests AWS identity and optional catalog access without printing credentials. Catalog access is not required if the permitted model ID is known. The decisive check is `PYTHONPATH=. uv run python scripts/smoke_agent.py` with a live provider configured. It must pass before claiming live interpretation works.

## Data and reset

Sessions use random HttpOnly cookies; only a hash is stored. Sessions expire after seven days. A reset deletes the workspace, sources, approvals, publications, jobs, and events via foreign-key cascades. Public links intentionally stop working after reset. Anonymous sessions are appropriate for fictional demos, not real organization authorization.

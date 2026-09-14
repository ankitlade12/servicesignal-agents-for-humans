#!/usr/bin/env bash
set -euo pipefail
if [ "$(id -u)" = "0" ]; then
  mkdir -p /app/data
  chown signal:signal /app/data
  chmod 700 /app/data
  exec gosu signal "$@"
fi
exec "$@"

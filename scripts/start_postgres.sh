#!/usr/bin/env bash
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$REPO/.conda/bin:$PATH"
PGDATA="$REPO/var/pgdata"
mkdir -p "$REPO/var"
if [[ ! -f "$PGDATA/PG_VERSION" ]]; then
  initdb -D "$PGDATA" --locale=C --encoding=UTF8 --auth-local=trust --auth-host=trust
fi
if ! pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
  pg_ctl -D "$PGDATA" -l "$REPO/var/pg.log" start
fi
pg_isready -h 127.0.0.1 -p 55432
psql -h 127.0.0.1 -p 55432 -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='intelligence'" | grep -q 1 \
  || psql -h 127.0.0.1 -p 55432 -d postgres -c "CREATE DATABASE intelligence"
echo "postgres ready on 127.0.0.1:55432"

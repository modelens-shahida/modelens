#!/bin/sh
# API container start: migrate to head, then serve. If the migration fails the
# app is not started on a half-migrated schema; print where the DB stands and
# where the recovery steps are, then exit non-zero.
set -u

if ! alembic upgrade head; then
    echo "" >&2
    echo "[start-api] alembic upgrade head FAILED - the API was not started." >&2
    echo "[start-api] Recorded DB revision:" >&2
    alembic current >&2 2>&1 || true
    echo "[start-api] Repository head(s):" >&2
    alembic heads >&2 2>&1 || true
    echo "[start-api] See 'If local migrations fail' in README.md for recovery steps." >&2
    exit 1
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"

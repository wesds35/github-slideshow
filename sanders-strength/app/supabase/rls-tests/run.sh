#!/usr/bin/env bash
# Runs the row-level-security test suite against a throwaway Postgres in Docker.
# Applies the real supabase/schema.sql behind faithful shims of Supabase's auth machinery
# (auth.users, auth.uid(), auth.jwt(), the `authenticated` role), then exercises every policy
# as coach / athlete A / athlete B / anonymous. Every check prints PASS or FAIL.
#
# Usage: ./run.sh   (requires Docker; leaves no container behind)
set -euo pipefail
cd "$(dirname "$0")"

CONTAINER=ss-rls-test-$$

cleanup() { docker rm -f "$CONTAINER" > /dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$CONTAINER" -e POSTGRES_PASSWORD=test postgres:15-alpine > /dev/null
until docker exec "$CONTAINER" pg_isready -U postgres > /dev/null 2>&1; do sleep 0.5; done

psql_run() { docker exec -i "$CONTAINER" psql -U postgres "$@"; }

psql_run -v ON_ERROR_STOP=1 -q -f - < 00-shim-pre.sql
psql_run -v ON_ERROR_STOP=1 -q -f - < ../schema.sql
psql_run -v ON_ERROR_STOP=1 -q -f - < 02-shim-post.sql

OUTPUT=$(psql_run -f - < 03-tests.sql 2>&1)
echo "$OUTPUT" | grep -E "PASS|FAIL|ERROR" | sed 's/^ *//;s/^psql:<stdin>:[0-9]*: NOTICE: *//'

if echo "$OUTPUT" | grep -qE "FAIL|ERROR"; then
  echo "--- RLS TEST SUITE FAILED ---"
  exit 1
fi
echo "--- RLS TEST SUITE PASSED ---"

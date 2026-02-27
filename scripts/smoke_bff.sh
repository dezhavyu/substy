#!/usr/bin/env bash
set -euo pipefail

BFF_URL="${BFF_URL:-http://localhost:8070}"
EMAIL="${EMAIL:-smoke-$(date +%s)@example.com}"
PASSWORD="${PASSWORD:-VeryStrongPassword123}"

RESPONSE_BODY=""
RESPONSE_CODE=""
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

request() {
  local method="$1"
  shift
  local url="$1"
  shift
  local body="${1-__NO_BODY__}"
  if [[ $# -gt 0 ]]; then
    shift
  fi

  local tmp
  tmp="$(mktemp)"

  if [[ "$body" == "__NO_BODY__" ]]; then
    RESPONSE_CODE="$(curl -sS -o "$tmp" -w '%{http_code}' -X "$method" "$url" "$@")"
  else
    RESPONSE_CODE="$(curl -sS -o "$tmp" -w '%{http_code}' -X "$method" "$url" -H 'Content-Type: application/json' "$@" -d "$body")"
  fi

  RESPONSE_BODY="$(cat "$tmp")"
  rm -f "$tmp"
}

expect_code() {
  local actual="$1"
  shift
  for expected in "$@"; do
    if [[ "$actual" == "$expected" ]]; then
      return 0
    fi
  done

  echo "Unexpected status: got $actual, expected one of: $*"
  echo "Response body: $RESPONSE_BODY"
  exit 1
}

json_get() {
  local key="$1"
  JSON="$RESPONSE_BODY" KEY="$key" python3 - <<'PY'
import json
import os

try:
    data = json.loads(os.environ["JSON"])
except Exception:
    print("")
    raise SystemExit(0)

value = data
for part in os.environ["KEY"].split('.'):
    if isinstance(value, dict):
        value = value.get(part, "")
    else:
        value = ""
        break

if value is None:
    print("")
elif isinstance(value, (dict, list)):
    print(json.dumps(value))
else:
    print(value)
PY
}

echo "[1/6] Register: $EMAIL"
request POST "$BFF_URL/api/auth/register" "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}"
expect_code "$RESPONSE_CODE" 200 201
echo "$RESPONSE_BODY"

echo "[2/6] Login"
request POST "$BFF_URL/api/auth/login" "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" -c "$COOKIE_JAR"
expect_code "$RESPONSE_CODE" 200
echo "$RESPONSE_BODY"
ACCESS_TOKEN="$(json_get access_token)"
if [[ -z "$ACCESS_TOKEN" ]]; then
  echo "Login failed: access_token missing"
  exit 1
fi

echo "[3/6] Open protected page (/api/me)"
request GET "$BFF_URL/api/me" __NO_BODY__ -H "Authorization: Bearer $ACCESS_TOKEN"
expect_code "$RESPONSE_CODE" 200
echo "$RESPONSE_BODY"

echo "[4/6] Force expired/invalid access token -> expect 401"
request GET "$BFF_URL/api/me" __NO_BODY__ -H "Authorization: Bearer invalid-token"
expect_code "$RESPONSE_CODE" 401
echo "$RESPONSE_BODY"

echo "[5/6] Refresh with HttpOnly cookie and retry protected call"
request POST "$BFF_URL/api/auth/refresh" "{}" -b "$COOKIE_JAR" -c "$COOKIE_JAR"
expect_code "$RESPONSE_CODE" 200
echo "$RESPONSE_BODY"
NEW_ACCESS_TOKEN="$(json_get access_token)"
if [[ -z "$NEW_ACCESS_TOKEN" ]]; then
  echo "Refresh failed: access_token missing"
  exit 1
fi

request GET "$BFF_URL/api/me" __NO_BODY__ -H "Authorization: Bearer $NEW_ACCESS_TOKEN"
expect_code "$RESPONSE_CODE" 200
echo "$RESPONSE_BODY"

echo "[6/6] First topics screen (/api/topics)"
request GET "$BFF_URL/api/topics?limit=10" __NO_BODY__ -H "Authorization: Bearer $NEW_ACCESS_TOKEN"
expect_code "$RESPONSE_CODE" 200
echo "$RESPONSE_BODY"

echo "Smoke test passed"

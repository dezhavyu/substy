#!/usr/bin/env bash
set -euo pipefail

BFF_URL="${BFF_URL:-http://localhost:8070}"
AUTH_URL="${AUTH_URL:-http://localhost:8080}"
SUBSCRIPTIONS_URL="${SUBSCRIPTIONS_URL:-http://localhost:8090}"
NOTIFICATIONS_URL="${NOTIFICATIONS_URL:-http://localhost:8091}"
DELIVERY_URL="${DELIVERY_URL:-http://localhost:8092}"

EMAIL="${EMAIL:-smoke-all-$(date +%s)@example.com}"
PASSWORD="${PASSWORD:-VeryStrongPassword123}"
TOPIC_ID="${TOPIC_ID:-}"
ADMIN_USER_ID="${ADMIN_USER_ID:-$(python3 -c 'import uuid; print(uuid.uuid4())')}"

RESPONSE_BODY=""
RESPONSE_CODE=""

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

assert_notification_present() {
  local notification_id="$1"
  JSON="$RESPONSE_BODY" NOTIFICATION_ID="$notification_id" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["JSON"])
items = payload.get("items", [])
if not isinstance(items, list):
    raise SystemExit(1)

found = any(isinstance(item, dict) and item.get("id") == os.environ["NOTIFICATION_ID"] for item in items)
raise SystemExit(0 if found else 1)
PY
}

echo "[0/7] Health checks"
for service in \
  "auth:$AUTH_URL" \
  "subscriptions:$SUBSCRIPTIONS_URL" \
  "notifications:$NOTIFICATIONS_URL" \
  "delivery:$DELIVERY_URL" \
  "bff:$BFF_URL"; do
  name="${service%%:*}"
  base_url="${service#*:}"
  request GET "$base_url/health"
  expect_code "$RESPONSE_CODE" 200
  echo "  - $name ok"
done

echo "[1/7] Register via BFF: $EMAIL"
request POST "$BFF_URL/auth/register" "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}"
expect_code "$RESPONSE_CODE" 200 201

echo "$RESPONSE_BODY"

echo "[2/7] Login via BFF"
request POST "$BFF_URL/auth/login" "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}"
expect_code "$RESPONSE_CODE" 200

echo "$RESPONSE_BODY"
ACCESS_TOKEN="$(json_get access_token)"
if [[ -z "$ACCESS_TOKEN" ]]; then
  echo "Login failed: access_token missing"
  exit 1
fi

if [[ -z "$TOPIC_ID" ]]; then
  echo "[3/7] Create topic in subscriptions-service (admin header)"

  TOPIC_KEY="smoke.$(date +%s)"
  TOPIC_NAME="Smoke Topic $(date +%s)"
  TOPIC_PAYLOAD="$(TOPIC_KEY="$TOPIC_KEY" TOPIC_NAME="$TOPIC_NAME" python3 - <<'PY'
import json
import os

print(json.dumps({
    "key": os.environ["TOPIC_KEY"],
    "name": os.environ["TOPIC_NAME"],
    "description": "Automated monorepo smoke topic"
}))
PY
)"

  request POST "$SUBSCRIPTIONS_URL/topics" "$TOPIC_PAYLOAD" -H "X-User-Id: $ADMIN_USER_ID" -H "X-User-Roles: admin"
  expect_code "$RESPONSE_CODE" 201

  echo "$RESPONSE_BODY"
  TOPIC_ID="$(json_get id)"
  if [[ -z "$TOPIC_ID" ]]; then
    echo "Topic creation failed: id missing"
    exit 1
  fi
else
  echo "[3/7] Use provided TOPIC_ID: $TOPIC_ID"
fi

echo "[4/7] Subscribe via BFF"
request POST "$BFF_URL/subscriptions" "{\"topic_id\":\"$TOPIC_ID\"}" -H "Authorization: Bearer $ACCESS_TOKEN"
expect_code "$RESPONSE_CODE" 200 201

echo "$RESPONSE_BODY"

echo "[5/7] Create notification via BFF"
IDEMPOTENCY_KEY="smoke-all-$(date +%s)"
request POST "$BFF_URL/notifications" "{\"topic_id\":\"$TOPIC_ID\",\"payload\":{\"title\":\"smoke\",\"source\":\"smoke_all\"},\"idempotency_key\":\"$IDEMPOTENCY_KEY\"}" -H "Authorization: Bearer $ACCESS_TOKEN"
expect_code "$RESPONSE_CODE" 200 201

echo "$RESPONSE_BODY"
NOTIFICATION_ID="$(json_get id)"
if [[ -z "$NOTIFICATION_ID" ]]; then
  echo "Notification creation failed: id missing"
  exit 1
fi

echo "[6/7] List notifications via BFF"
request GET "$BFF_URL/notifications/me?limit=10" __NO_BODY__ -H "Authorization: Bearer $ACCESS_TOKEN"
expect_code "$RESPONSE_CODE" 200

echo "$RESPONSE_BODY"
if ! assert_notification_present "$NOTIFICATION_ID"; then
  echo "Created notification is missing in /notifications/me"
  exit 1
fi

echo "[7/7] Smoke test passed"
echo "notification_id=$NOTIFICATION_ID"
echo "topic_id=$TOPIC_ID"

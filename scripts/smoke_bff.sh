#!/usr/bin/env bash
set -euo pipefail

BFF_URL="${BFF_URL:-http://localhost:8070}"
EMAIL="${EMAIL:-smoke-$(date +%s)@example.com}"
PASSWORD="${PASSWORD:-VeryStrongPassword123}"
TOPIC_ID="${TOPIC_ID:-}"

if [[ -z "$TOPIC_ID" ]]; then
  echo "TOPIC_ID is required. Example: TOPIC_ID=<uuid> ./scripts/smoke_bff.sh"
  exit 1
fi

echo "[1/5] Register: $EMAIL"
REGISTER_RESP=$(curl -sS -X POST "$BFF_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
echo "$REGISTER_RESP"

echo "[2/5] Login"
LOGIN_RESP=$(curl -sS -X POST "$BFF_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")

echo "$LOGIN_RESP"
ACCESS_TOKEN=$(echo "$LOGIN_RESP" | python3 -c 'import sys, json; d=json.load(sys.stdin); print(d.get("access_token", ""))')
if [[ -z "$ACCESS_TOKEN" ]]; then
  echo "Login failed: access_token missing"
  exit 1
fi

echo "[3/5] Subscribe to topic: $TOPIC_ID"
SUB_RESP=$(curl -sS -X POST "$BFF_URL/subscriptions" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"topic_id\":\"$TOPIC_ID\"}")
echo "$SUB_RESP"

echo "[4/5] Create notification"
NOTIF_RESP=$(curl -sS -X POST "$BFF_URL/notifications" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"topic_id\":\"$TOPIC_ID\",\"payload\":{\"title\":\"smoke\",\"source\":\"bff\"},\"idempotency_key\":\"smoke-$(date +%s)\"}")
echo "$NOTIF_RESP"

NOTIF_ID=$(echo "$NOTIF_RESP" | python3 -c 'import sys, json; d=json.load(sys.stdin); print(d.get("id", ""))')
if [[ -z "$NOTIF_ID" ]]; then
  echo "Notification creation failed: id missing"
  exit 1
fi

echo "[5/5] Get my notifications"
ME_RESP=$(curl -sS "$BFF_URL/notifications/me?limit=5" \
  -H "Authorization: Bearer $ACCESS_TOKEN")
echo "$ME_RESP"

echo "Smoke test passed"

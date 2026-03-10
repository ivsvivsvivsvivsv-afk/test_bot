#!/usr/bin/env bash
# ==============================================================
# HYDRA BOT — Sandbox smoke checks
# ==============================================================
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/hydra_bot_sandbox}"
ENV_FILE="${PROJECT_DIR}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "[FAIL] ${ENV_FILE} not found"
    exit 1
fi

# shellcheck source=/dev/null
source "${ENV_FILE}"

echo "[STEP] systemd services"
systemctl is-active --quiet hydra-bot-sandbox || { echo "[FAIL] hydra-bot-sandbox is not active"; exit 1; }
systemctl is-active --quiet hydra-worker-sandbox || { echo "[FAIL] hydra-worker-sandbox is not active"; exit 1; }
echo "[OK]   sandbox services are active"

echo "[STEP] local health endpoint"
HEALTH_JSON="$(curl -sS -m 5 "http://127.0.0.1:18443/health")"
echo "       ${HEALTH_JSON}"
echo "${HEALTH_JSON}" | grep -q '"status":\s*"ok"' || {
    echo "[FAIL] local sandbox /health returned degraded status"
    exit 1
}
echo "[OK]   local health is ok"

echo "[STEP] public health endpoint"
PUBLIC_URL="${WEBHOOK_HOST%/}/health"
PUBLIC_BODY="$(curl -sS -m 10 "${PUBLIC_URL}")"
echo "       ${PUBLIC_BODY}"
echo "${PUBLIC_BODY}" | grep -q '"status":\s*"ok"' || {
    echo "[FAIL] public sandbox /health returned degraded status"
    exit 1
}
echo "[OK]   public health is ok"

echo "[STEP] telegram webhook info"
WEBHOOK_INFO="$(curl -sS -m 10 "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo")"
echo "       ${WEBHOOK_INFO}"
EXPECTED_URL="${WEBHOOK_HOST%/}${WEBHOOK_PATH}"
echo "${WEBHOOK_INFO}" | grep -q "\"url\":\"${EXPECTED_URL}\"" || {
    echo "[FAIL] Telegram webhook URL mismatch. Expected: ${EXPECTED_URL}"
    exit 1
}
echo "[OK]   Telegram webhook URL matches"

echo "[PASS] sandbox smoke checks passed"

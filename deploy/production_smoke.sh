#!/usr/bin/env bash
# ==============================================================
# HYDRA BOT — Production smoke checks (run on server)
# ==============================================================
# Usage:
#   sudo bash deploy/production_smoke.sh
# Requirements:
#   - /opt/hydra_bot/.env exists
#   - hydra-bot and hydra-worker services are installed
# ==============================================================
set -euo pipefail

PROJECT_DIR="/opt/hydra_bot"
ENV_FILE="${PROJECT_DIR}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "[FAIL] ${ENV_FILE} not found"
    exit 1
fi

# shellcheck source=/dev/null
source "${ENV_FILE}"

echo "[STEP] systemd services"
systemctl is-active --quiet hydra-bot || { echo "[FAIL] hydra-bot is not active"; exit 1; }
systemctl is-active --quiet hydra-worker || { echo "[FAIL] hydra-worker is not active"; exit 1; }
echo "[OK]   hydra-bot and hydra-worker are active"

echo "[STEP] local health endpoint"
HEALTH_JSON="$(curl -sS -m 5 "http://127.0.0.1:8443/health")"
echo "       ${HEALTH_JSON}"
echo "${HEALTH_JSON}" | grep -q '"status":\s*"ok"' || {
    echo "[FAIL] local /health returned degraded status"
    exit 1
}
echo "[OK]   local health is ok"

echo "[STEP] public health endpoint"
PUBLIC_URL="${WEBHOOK_HOST%/}/health"
PUBLIC_BODY="$(curl -sS -m 10 "${PUBLIC_URL}")"
echo "       ${PUBLIC_BODY}"
echo "${PUBLIC_BODY}" | grep -q '"status":\s*"ok"' || {
    echo "[FAIL] public /health returned degraded status"
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

echo "[STEP] quick infrastructure probes"
redis-cli ping | grep -q "PONG" || { echo "[FAIL] redis ping failed"; exit 1; }
PGPASSWORD="${DB_PASSWORD}" psql -U "${DB_USER}" -d "${DB_NAME}" -h "${DB_HOST}" -c "SELECT 1;" >/dev/null
echo "[OK]   Redis and PostgreSQL probes passed"

echo "[PASS] production smoke checks passed"

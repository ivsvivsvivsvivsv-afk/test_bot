#!/usr/bin/env bash
# ==============================================================
# HYDRA BOT — Guarded deploy (anti-mixup)
# ==============================================================
# Usage examples:
#   bash deploy/guarded_deploy.sh --env production --project-dir /opt/hydra_bot
#   bash deploy/guarded_deploy.sh --env sandbox --project-dir /opt/hydra_bot_sandbox
# ==============================================================
set -euo pipefail

ENVIRONMENT=""
PROJECT_DIR=""
STRICT_PROD="0"
RUN_SMOKE="1"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env)
            ENVIRONMENT="${2:-}"
            shift 2
            ;;
        --project-dir)
            PROJECT_DIR="${2:-}"
            shift 2
            ;;
        --strict-prod)
            STRICT_PROD="1"
            shift
            ;;
        --no-smoke)
            RUN_SMOKE="0"
            shift
            ;;
        *)
            echo "Unknown arg: $1"
            exit 1
            ;;
    esac
done

if [[ -z "${ENVIRONMENT}" || -z "${PROJECT_DIR}" ]]; then
    echo "Usage: $0 --env <production|sandbox> --project-dir <path> [--strict-prod] [--no-smoke]"
    exit 1
fi

if [[ "${ENVIRONMENT}" != "production" && "${ENVIRONMENT}" != "sandbox" ]]; then
    echo "[FAIL] --env must be production|sandbox"
    exit 1
fi

if [[ ! -d "${PROJECT_DIR}" ]]; then
    echo "[FAIL] Project dir not found: ${PROJECT_DIR}"
    exit 1
fi

cd "${PROJECT_DIR}"

if [[ ! -f ".env" ]]; then
    echo "[FAIL] .env not found in ${PROJECT_DIR}"
    exit 1
fi

# shellcheck source=/dev/null
source .env

echo "[STEP] deployment target summary"
echo "       ENV=${ENVIRONMENT}"
echo "       PROJECT_DIR=${PROJECT_DIR}"
echo "       APP_ENV=${APP_ENV:-}"
echo "       APP_INSTANCE=${APP_INSTANCE:-}"
echo "       WEBHOOK_HOST=${WEBHOOK_HOST:-}"

if [[ "${APP_ENV:-}" != "${ENVIRONMENT}" ]]; then
    echo "[FAIL] APP_ENV mismatch. .env has '${APP_ENV:-}', expected '${ENVIRONMENT}'"
    exit 1
fi

if [[ ! -f ".deploy-target" ]]; then
    echo "[FAIL] .deploy-target is missing in ${PROJECT_DIR}"
    exit 1
fi

# shellcheck source=/dev/null
source .deploy-target
if [[ "${TARGET_ENV:-}" != "${ENVIRONMENT}" ]]; then
    echo "[FAIL] .deploy-target TARGET_ENV='${TARGET_ENV:-}' mismatch"
    exit 1
fi

if [[ -z "${APP_INSTANCE:-}" || -z "${TARGET_INSTANCE:-}" || "${APP_INSTANCE}" != "${TARGET_INSTANCE}" ]]; then
    echo "[FAIL] APP_INSTANCE and .deploy-target TARGET_INSTANCE mismatch"
    exit 1
fi

if [[ "${ENVIRONMENT}" == "production" ]]; then
    if [[ "${WEBHOOK_HOST:-}" != "https://bot.neurounit.fun" ]]; then
        echo "[FAIL] Production WEBHOOK_HOST must be https://bot.neurounit.fun"
        exit 1
    fi
else
    if [[ "${WEBHOOK_HOST:-}" == "https://bot.neurounit.fun" ]]; then
        echo "[FAIL] Sandbox must not use production WEBHOOK_HOST"
        exit 1
    fi
fi

echo "[STEP] confirm target"
echo "Type exactly '${ENVIRONMENT}:${APP_INSTANCE}' to continue:"
read -r confirm
if [[ "${confirm}" != "${ENVIRONMENT}:${APP_INSTANCE}" ]]; then
    echo "[FAIL] Confirmation mismatch"
    exit 1
fi

echo "[STEP] update code"
git fetch --all --prune
git pull --ff-only

echo "[STEP] install dependencies"
if [[ ! -d "venv" ]]; then
    python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install -q -U pip
pip install -q -r requirements.txt

echo "[STEP] predeploy check"
PREDEPLOY_ARGS=(./venv/bin/python predeploy_check.py --target-env "${ENVIRONMENT}" --check-services)
if [[ "${STRICT_PROD}" == "1" ]]; then
    PREDEPLOY_ARGS+=(--strict-prod)
fi
"${PREDEPLOY_ARGS[@]}"

echo "[STEP] restart services"
if [[ "${ENVIRONMENT}" == "production" ]]; then
    sudo systemctl restart hydra-bot hydra-worker
else
    sudo systemctl restart hydra-bot-sandbox hydra-worker-sandbox
fi

if [[ "${RUN_SMOKE}" == "1" ]]; then
    echo "[STEP] smoke checks"
    if [[ "${ENVIRONMENT}" == "production" ]]; then
        sudo bash deploy/production_smoke.sh
    else
        sudo bash deploy/sandbox_smoke.sh
    fi
fi

echo "[PASS] Guarded deploy completed: ${ENVIRONMENT}/${APP_INSTANCE}"

#!/usr/bin/env bash
# ==============================================================
# HYDRA BOT — Деплой sandbox (запускать НА СЕРВЕРЕ)
# ==============================================================
# Скопировать на сервер и выполнить:
#   scp deploy/deploy_sandbox_now.sh root@82.146.39.44:/root/
#   ssh root@82.146.39.44 'bash /root/deploy_sandbox_now.sh'
#
# Или по SSH вручную:
#   ssh root@82.146.39.44
#   cd /opt/hydra_bot_sandbox 2>/dev/null || (cd /opt && git clone https://github.com/ivsvivsvivsvivsv-afk/test_bot.git hydra_bot_sandbox && cd hydra_bot_sandbox)
#   # ... далее шаги ниже
# ==============================================================
set -euo pipefail

REPO_URL="https://github.com/ivsvivsvivsvivsv-afk/test_bot.git"
SANDBOX_DIR="/opt/hydra_bot_sandbox"
# Токен @Neurounit_Sandbox_bot (вставить при первом запуске)
SANDBOX_BOT_TOKEN="${SANDBOX_BOT_TOKEN:-}"

echo "=== HYDRA BOT: Деплой SANDBOX ==="

# ── 1. Клонировать или обновить код ───────────────────────────
if [[ -d "${SANDBOX_DIR}/.git" ]]; then
    echo "[1] Обновление кода..."
    cd "${SANDBOX_DIR}"
    git fetch --all --prune
    git pull --ff-only origin main
else
    echo "[1] Клонирование репозитория..."
    sudo rm -rf "${SANDBOX_DIR}" 2>/dev/null || true
    sudo git clone "${REPO_URL}" "${SANDBOX_DIR}"
    cd "${SANDBOX_DIR}"
fi

# ── 2. Маркер .deploy-target ───────────────────────────────────
echo "[2] Создание .deploy-target..."
cat > .deploy-target <<'EOF'
TARGET_ENV=sandbox
TARGET_INSTANCE=hydra-sandbox
EOF

# ── 3. .env ───────────────────────────────────────────────────
if [[ ! -f .env ]]; then
    echo "[3] Создание .env из шаблона..."
    cp .env.sandbox.example .env

    # Генерация секретов
    WEBHOOK_SECRET=$(openssl rand -hex 32)
    ADMIN_API_SECRET=$(openssl rand -hex 32)
    SITE_WEBHOOK_SECRET=$(openssl rand -hex 32)

    # DB password (из prod или новый)
    if [[ -f /opt/hydra_bot/.env ]]; then
        source /opt/hydra_bot/.env 2>/dev/null || true
    fi
    PG_PASSWORD="${DB_PASSWORD:-$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)}"

    sed -i "s|WEBHOOK_SECRET=.*|WEBHOOK_SECRET=${WEBHOOK_SECRET}|" .env
    sed -i "s|DB_PASSWORD=.*|DB_PASSWORD=${PG_PASSWORD}|" .env
    sed -i "s|ADMIN_API_SECRET=.*|ADMIN_API_SECRET=${ADMIN_API_SECRET}|" .env
    sed -i "s|SITE_WEBHOOK_SECRET=.*|SITE_WEBHOOK_SECRET=${SITE_WEBHOOK_SECRET}|" .env

    echo ""
    echo "  Вставьте BOT_TOKEN sandbox-бота в .env:"
    echo "  nano ${SANDBOX_DIR}/.env"
    echo "  BOT_TOKEN=<токен от @BotFather для @Neurounit_Sandbox_bot>"
    echo ""
else
    echo "[3] .env уже существует"
fi

# Вставить токен если передан
if [[ -n "${SANDBOX_BOT_TOKEN}" ]]; then
    sed -i "s|^BOT_TOKEN=.*|BOT_TOKEN=${SANDBOX_BOT_TOKEN}|" .env
    echo "  BOT_TOKEN обновлён"
fi

# ── 4. PostgreSQL sandbox ──────────────────────────────────────
echo "[4] Проверка БД hydra_bot_sandbox..."
source .env 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE hydra_bot_sandbox OWNER hydra;" 2>/dev/null || true
PGPASSWORD="${DB_PASSWORD:-}" psql -U hydra -d hydra_bot_sandbox -h localhost -c "SELECT 1;" 2>/dev/null || {
    echo "  Создайте БД вручную: sudo -u postgres psql -c \"CREATE DATABASE hydra_bot_sandbox OWNER hydra;\""
}

# ── 5. Схема ──────────────────────────────────────────────────
echo "[5] Применение schema.sql..."
PGPASSWORD="${DB_PASSWORD:-}" psql -U hydra -d hydra_bot_sandbox -h localhost -f schema.sql 2>/dev/null || echo "  (уже применена или ошибка)"

# ── 6. Python venv и зависимости ────────────────────────────────
echo "[6] venv и зависимости..."
if [[ ! -d venv ]]; then
    python3.12 -m venv venv 2>/dev/null || python3 -m venv venv
fi
source venv/bin/activate
pip install -q -U pip
pip install -q -r requirements.txt

# ── 7. Systemd и NGINX ─────────────────────────────────────────
echo "[7] Systemd и NGINX..."
sudo cp deploy/hydra-bot-sandbox.service /etc/systemd/system/
sudo cp deploy/hydra-worker-sandbox.service /etc/systemd/system/
sudo cp deploy/nginx.sandbox.conf /etc/nginx/sites-available/hydra-bot-sandbox
sudo ln -sf /etc/nginx/sites-available/hydra-bot-sandbox /etc/nginx/sites-enabled/
sudo chown -R www-data:www-data "${SANDBOX_DIR}" 2>/dev/null || true
sudo systemctl daemon-reload
sudo nginx -t && sudo systemctl reload nginx
sudo systemctl enable hydra-bot-sandbox hydra-worker-sandbox

# ── 8. SSL (если ещё нет) ───────────────────────────────────────
if [[ ! -f /etc/letsencrypt/live/bot-sandbox.neurounit.fun/fullchain.pem ]]; then
    echo "[8] Получение SSL для bot-sandbox.neurounit.fun..."
    echo "  certbot --nginx -d bot-sandbox.neurounit.fun"
    sudo certbot --nginx -d bot-sandbox.neurounit.fun --non-interactive --agree-tos --email admin@neurounit.fun 2>/dev/null || true
else
    echo "[8] SSL уже настроен"
fi

# ── 9. Запуск ───────────────────────────────────────────────────
echo "[9] Запуск сервисов..."
sudo systemctl restart hydra-bot-sandbox hydra-worker-sandbox
sleep 3

echo ""
echo "=== Проверка ==="
curl -sS "http://127.0.0.1:18443/health" || true
echo ""
echo "Бот: https://t.me/Neurounit_Sandbox_bot"
echo "Health: https://bot-sandbox.neurounit.fun/health"
echo ""

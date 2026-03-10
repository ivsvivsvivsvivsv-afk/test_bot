#!/usr/bin/env bash
# ==============================================================
# HYDRA BOT — Первоначальная настройка SANDBOX
# ==============================================================
# Запуск на сервере: sudo bash deploy/setup_sandbox.sh
# Требуется: REPO_URL или /opt/hydra_bot с .git
# После: отредактировать .env — вставить BOT_TOKEN sandbox-бота
# ==============================================================
set -euo pipefail

SANDBOX_DIR="/opt/hydra_bot_sandbox"
REPO_URL="${REPO_URL:-}"

echo "=== HYDRA BOT: Настройка SANDBOX ==="

# ── 1. Клонирование/копирование кода ─────────────────────────
echo "[1/9] Подготовка кода в ${SANDBOX_DIR}..."

if [[ -d "${SANDBOX_DIR}/.git" ]]; then
    echo "       Директория уже существует, обновляем..."
    cd "${SANDBOX_DIR}"
    git fetch --all --prune
    git pull --ff-only || true
elif [[ -d "/opt/hydra_bot/.git" ]]; then
    echo "       Клонируем из /opt/hydra_bot..."
    sudo rm -rf "${SANDBOX_DIR}" 2>/dev/null || true
    sudo git clone /opt/hydra_bot "${SANDBOX_DIR}"
    cd "${SANDBOX_DIR}"
    git remote set-url origin "$(cd /opt/hydra_bot && git remote get-url origin 2>/dev/null || echo "https://github.com/your-org/test_bot.git")"
elif [[ -n "${REPO_URL}" ]]; then
    echo "       Клонируем из ${REPO_URL}..."
    sudo rm -rf "${SANDBOX_DIR}" 2>/dev/null || true
    sudo git clone "${REPO_URL}" "${SANDBOX_DIR}"
    cd "${SANDBOX_DIR}"
else
    echo "[FAIL] Нужен либо /opt/hydra_bot с .git, либо REPO_URL=..."
    echo "       Пример: REPO_URL=https://github.com/.../test_bot.git sudo bash deploy/setup_sandbox.sh"
    exit 1
fi

# ── 2. Маркер deploy-target ───────────────────────────────────
echo "[2/9] Создание .deploy-target..."
sudo tee "${SANDBOX_DIR}/.deploy-target" > /dev/null <<'EOF'
TARGET_ENV=sandbox
TARGET_INSTANCE=hydra-sandbox
EOF

# ── 3. PostgreSQL: sandbox БД ─────────────────────────────────
echo "[3/9] Создание БД hydra_bot_sandbox..."

# Берём пароль из prod .env если есть, иначе генерируем
if [[ -f /opt/hydra_bot/.env ]]; then
    # shellcheck source=/dev/null
    source /opt/hydra_bot/.env 2>/dev/null || true
fi
PG_PASSWORD="${DB_PASSWORD:-$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)}"

sudo -u postgres psql -c "CREATE USER hydra WITH PASSWORD '${PG_PASSWORD}';" 2>/dev/null || \
    sudo -u postgres psql -c "ALTER USER hydra WITH PASSWORD '${PG_PASSWORD}';"
sudo -u postgres psql -c "CREATE DATABASE hydra_bot_sandbox OWNER hydra;" 2>/dev/null || true

echo "  -> DB hydra_bot_sandbox создана"

# ── 4. Генерация секретов ─────────────────────────────────────
WEBHOOK_SECRET=$(openssl rand -hex 32)
ADMIN_API_SECRET=$(openssl rand -hex 32)
SITE_WEBHOOK_SECRET=$(openssl rand -hex 32)

# ── 5. .env из шаблона ───────────────────────────────────────
echo "[4/9] Создание .env из шаблона..."

if [[ -f "${SANDBOX_DIR}/.env.sandbox.example" ]]; then
    sudo cp "${SANDBOX_DIR}/.env.sandbox.example" "${SANDBOX_DIR}/.env"
    sudo chown www-data:www-data "${SANDBOX_DIR}/.env" 2>/dev/null || true
else
    echo "[FAIL] .env.sandbox.example не найден"
    exit 1
fi

# Подставляем сгенерированные значения
sudo sed -i "s|WEBHOOK_SECRET=.*|WEBHOOK_SECRET=${WEBHOOK_SECRET}|" "${SANDBOX_DIR}/.env"
sudo sed -i "s|DB_PASSWORD=.*|DB_PASSWORD=${PG_PASSWORD}|" "${SANDBOX_DIR}/.env"
sudo sed -i "s|ADMIN_API_SECRET=.*|ADMIN_API_SECRET=${ADMIN_API_SECRET}|" "${SANDBOX_DIR}/.env"
sudo sed -i "s|SITE_WEBHOOK_SECRET=.*|SITE_WEBHOOK_SECRET=${SITE_WEBHOOK_SECRET}|" "${SANDBOX_DIR}/.env"

echo ""
echo "  ╔══════════════════════════════════════════════════════════════════════╗"
echo "  ║  ВАЖНО: Отредактируйте .env и вставьте BOT_TOKEN sandbox-бота!       ║"
echo "  ║  nano /opt/hydra_bot_sandbox/.env                                    ║"
echo "  ║  BOT_TOKEN=<токен от @BotFather для @Neurounit_Sandbox_bot>           ║"
echo "  ╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# ── 6. Python venv и зависимости ───────────────────────────────
echo "[5/9] Python venv и зависимости..."
cd "${SANDBOX_DIR}"
if [[ ! -d "venv" ]]; then
    sudo python3.12 -m venv venv 2>/dev/null || sudo python3 -m venv venv
fi
# shellcheck disable=SC1091
sudo -u www-data bash -c "source venv/bin/activate && pip install --upgrade pip -q && pip install -r requirements.txt"

# ── 7. Схема БД ────────────────────────────────────────────────
echo "[6/9] Применение schema.sql..."
PGPASSWORD="${PG_PASSWORD}" psql -U hydra -d hydra_bot_sandbox -h localhost -f "${SANDBOX_DIR}/schema.sql" 2>/dev/null || {
    echo "  -> Если schema.sql не применяется, выполните вручную:"
    echo "     PGPASSWORD='...' psql -U hydra -d hydra_bot_sandbox -f schema.sql"
}

# ── 8. Systemd и NGINX ─────────────────────────────────────────
echo "[7/9] Systemd и NGINX..."

sudo cp "${SANDBOX_DIR}/deploy/hydra-bot-sandbox.service" /etc/systemd/system/
sudo cp "${SANDBOX_DIR}/deploy/hydra-worker-sandbox.service" /etc/systemd/system/
sudo cp "${SANDBOX_DIR}/deploy/nginx.sandbox.conf" /etc/nginx/sites-available/hydra-bot-sandbox
sudo ln -sf /etc/nginx/sites-available/hydra-bot-sandbox /etc/nginx/sites-enabled/
sudo chown -R www-data:www-data "${SANDBOX_DIR}/.git" 2>/dev/null || true
sudo chown -R www-data:www-data "${SANDBOX_DIR}" 2>/dev/null || true

sudo systemctl daemon-reload
sudo nginx -t && sudo systemctl reload nginx
sudo systemctl enable hydra-bot-sandbox hydra-worker-sandbox

# ── 9. SSL для поддомена ───────────────────────────────────────
echo "[8/9] SSL для bot-sandbox.neurounit.fun..."
echo "  В DNS добавьте: bot-sandbox.neurounit.fun → IP сервера"
echo "  Затем выполните: sudo certbot --nginx -d bot-sandbox.neurounit.fun"
echo ""
read -r -p "Запустить certbot сейчас? (y/n): " do_cert
if [[ "${do_cert}" == "y" || "${do_cert}" == "Y" ]]; then
    sudo certbot --nginx -d bot-sandbox.neurounit.fun --non-interactive --agree-tos --email admin@neurounit.fun 2>/dev/null || {
        echo "  -> certbot выполнен вручную или пропущен"
    }
fi

# ── 10. Проверка BOT_TOKEN и запуск ────────────────────────────
echo "[9/9] Запуск сервисов..."

if grep -q "^BOT_TOKEN=123456789:" "${SANDBOX_DIR}/.env" 2>/dev/null; then
    echo ""
    echo "[WARN] BOT_TOKEN не обновлён! Замените на токен @Neurounit_Sandbox_bot"
    echo "       nano ${SANDBOX_DIR}/.env"
    echo "       Затем: sudo systemctl start hydra-bot-sandbox hydra-worker-sandbox"
    echo ""
else
    sudo systemctl start hydra-bot-sandbox hydra-worker-sandbox
    sleep 3
    sudo bash "${SANDBOX_DIR}/deploy/sandbox_smoke.sh" 2>/dev/null || echo "  -> Smoke checks: проверьте вручную"
fi

echo ""
echo "=== SANDBOX ГОТОВ ============================================"
echo ""
echo "Бот: https://t.me/Neurounit_Sandbox_bot"
echo "API: https://bot-sandbox.neurounit.fun/api/admin/stats"
echo "Health: https://bot-sandbox.neurounit.fun/health"
echo ""
echo "Деплой обновлений:"
echo "  cd ${SANDBOX_DIR}"
echo "  bash deploy/guarded_deploy.sh --env sandbox --project-dir ${SANDBOX_DIR}"
echo "  (подтверждение: sandbox:hydra-sandbox)"
echo ""

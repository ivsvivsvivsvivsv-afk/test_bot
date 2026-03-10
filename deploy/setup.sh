#!/usr/bin/env bash
# ==============================================================
# HYDRA BOT — Первоначальная настройка сервера
# ==============================================================
# Целевая платформа: Ubuntu 24.04 (FirstVDS)
# Запуск: sudo bash deploy/setup.sh
# ==============================================================
set -euo pipefail

echo "=== HYDRA BOT: Настройка сервера ==="

# ── 1. Обновление системы ────────────────────────────────────
echo "[1/8] Обновление системы..."
apt update && apt upgrade -y

# ── 2. Установка пакетов ─────────────────────────────────────
echo "[2/8] Установка Python 3.12, PostgreSQL 16, Redis 7, NGINX..."
apt install -y \
    python3.12 python3.12-venv python3-pip \
    postgresql-16 postgresql-contrib \
    redis-server \
    nginx \
    certbot python3-certbot-nginx \
    git htop curl

# ── 3. PostgreSQL ─────────────────────────────────────────────
echo "[3/8] Настройка PostgreSQL..."

# Генерируем надёжный пароль автоматически (не хардкод!)
PG_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║  PG-пароль (СОХРАНИТЕ В .env → DB_PASSWORD): ║"
echo "  ║  $PG_PASSWORD  ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""

sudo -u postgres psql -c "CREATE USER hydra WITH PASSWORD '${PG_PASSWORD}';" 2>/dev/null || \
    sudo -u postgres psql -c "ALTER USER hydra WITH PASSWORD '${PG_PASSWORD}';"
sudo -u postgres psql -c "CREATE DATABASE hydra_bot OWNER hydra;" 2>/dev/null || true

echo "  -> Проверка подключения..."
PGPASSWORD="${PG_PASSWORD}" psql -U hydra -d hydra_bot -h localhost -c "SELECT 1;" > /dev/null 2>&1 \
    && echo "  -> PostgreSQL OK" \
    || echo "  -> ВНИМАНИЕ: Проверьте pg_hba.conf (md5 / scram-sha-256 для localhost)"

# ── 4. Redis ──────────────────────────────────────────────────
echo "[4/8] Настройка Redis..."

REDIS_CONF="/etc/redis/redis.conf"
if [ -f "$REDIS_CONF" ]; then
    # Persistence: сохраняем каждые 5 мин если >= 10 изменений
    sed -i 's/# save 3600 1/save 300 10/' "$REDIS_CONF" 2>/dev/null || true

    # Ограничение памяти (idempotent)
    grep -q "^maxmemory 256mb" "$REDIS_CONF" \
        || echo "maxmemory 256mb" >> "$REDIS_CONF"
    grep -q "^maxmemory-policy allkeys-lru" "$REDIS_CONF" \
        || echo "maxmemory-policy allkeys-lru" >> "$REDIS_CONF"

    systemctl restart redis
    redis-cli ping > /dev/null && echo "  -> Redis OK (PONG)" \
        || echo "  -> ВНИМАНИЕ: Redis не отвечает"
else
    echo "  -> $REDIS_CONF не найден, пропускаем настройку"
fi

# ── 5. Директория проекта ─────────────────────────────────────
echo "[5/8] Создание /opt/hydra_bot..."
mkdir -p /opt/hydra_bot
cd /opt/hydra_bot

# Маркер target для anti-mixup deploy guard
cat > .deploy-target <<'EOF'
TARGET_ENV=production
TARGET_INSTANCE=hydra-prod
EOF

# ── 6. Python venv ────────────────────────────────────────────
echo "[6/8] Создание Python venv..."
if [ ! -d "venv" ]; then
    python3.12 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install --upgrade pip --quiet

# ── 7. SSL-сертификат ─────────────────────────────────────────
echo "[7/8] SSL-сертификат..."
echo "  Запустите вручную: certbot --nginx -d zhurkinigor.fvds.ru"

# ── 8. NGINX ──────────────────────────────────────────────────
echo "[8/8] Установка NGINX-конфига..."
if [ -f deploy/nginx.conf ]; then
    cp deploy/nginx.conf /etc/nginx/sites-available/hydra-bot
    ln -sf /etc/nginx/sites-available/hydra-bot /etc/nginx/sites-enabled/hydra-bot
    # Удаляем default-конфиг, если есть (иначе конфликт по порту 80)
    rm -f /etc/nginx/sites-enabled/default
    nginx -t && systemctl reload nginx \
        && echo "  -> NGINX OK" \
        || echo "  -> ВНИМАНИЕ: Ошибка конфигурации NGINX"
else
    echo "  -> deploy/nginx.conf не найден — сначала залейте код на сервер"
fi

# ── Генерация WEBHOOK_SECRET ──────────────────────────────────
WEBHOOK_SECRET=$(openssl rand -hex 32)

echo ""
echo "=== ГОТОВО! ============================================"
echo ""
echo "Сгенерированные секреты:"
echo "  DB_PASSWORD     = ${PG_PASSWORD}"
echo "  WEBHOOK_SECRET  = ${WEBHOOK_SECRET}"
echo ""
echo "Следующие шаги:"
echo "  1. Залейте код на сервер:"
echo "     git clone <repo> /opt/hydra_bot"
echo "  2. Скопируйте .env.example в .env и заполните секретами:"
echo "     cp .env.example .env && nano .env"
echo "  3. Установите зависимости:"
echo "     source venv/bin/activate && pip install -r requirements.txt"
echo "  4. Примените схему БД:"
echo "     PGPASSWORD='${PG_PASSWORD}' psql -U hydra -d hydra_bot -f schema.sql"
echo "  5. Получите SSL:"
echo "     certbot --nginx -d zhurkinigor.fvds.ru"
echo "  6. Установите systemd-юниты:"
echo "     cp deploy/hydra-bot.service /etc/systemd/system/"
echo "     cp deploy/hydra-worker.service /etc/systemd/system/"
echo "     systemctl daemon-reload"
echo "     systemctl enable hydra-bot hydra-worker"
echo "  7. Запустите:"
echo "     systemctl start hydra-bot hydra-worker"
echo "     journalctl -u hydra-bot -f"

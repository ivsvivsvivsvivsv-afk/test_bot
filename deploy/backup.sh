#!/usr/bin/env bash
# ==============================================================
# HYDRA BOT — Бекап перед обновлением (Patch 2)
# ==============================================================
# Запуск: sudo deploy/backup.sh
# Вызывается ПЕРЕД каждым деплоем. Бекапы защищены chattr +i.
# Разблокировка: sudo deploy/unlock_backups.sh
# ==============================================================
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/hydra_bot}"
PROJECT_DIR="${PROJECT_DIR:-/opt/hydra_bot}"
TS=$(date +%Y%m%d_%H%M%S)

echo "=== HYDRA BOT: Backup ($TS) ==="

mkdir -p "$BACKUP_ROOT"/{db,redis,code}

# ── PostgreSQL ─────────────────────────────────────────────
echo "[1/4] PostgreSQL dump..."
pg_dump -U hydra hydra_bot -Fc -f "$BACKUP_ROOT/db/hydra_${TS}.dump"

# ── Redis ───────────────────────────────────────────────────
echo "[2/4] Redis snapshot..."
redis-cli BGSAVE 2>/dev/null || true
sleep 2
REDIS_DUMP="${REDIS_DUMP:-/var/lib/redis/dump.rdb}"
if [ -f "$REDIS_DUMP" ]; then
    cp "$REDIS_DUMP" "$BACKUP_ROOT/redis/dump_${TS}.rdb"
else
    echo "  WARNING: Redis dump not found at $REDIS_DUMP"
fi

# ── Код ─────────────────────────────────────────────────────
echo "[3/4] Code archive..."
if [ -d "$PROJECT_DIR" ]; then
    (cd "$PROJECT_DIR" && tar czf "$BACKUP_ROOT/code/hydra_${TS}.tar.gz" \
        --exclude=venv --exclude=__pycache__ --exclude=.git \
        . 2>/dev/null || true)
else
    echo "  WARNING: Project dir $PROJECT_DIR not found"
fi

# ── .env ────────────────────────────────────────────────────
echo "[4/4] .env backup..."
if [ -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env" "$BACKUP_ROOT/.env.backup_${TS}"
fi

# ── Immutable (только root может снять через unlock_backups.sh) ─
echo "Setting immutable flag on backups..."
for f in "$BACKUP_ROOT/db/hydra_${TS}.dump" \
         "$BACKUP_ROOT/redis/dump_${TS}.rdb" \
         "$BACKUP_ROOT/code/hydra_${TS}.tar.gz"; do
    [ -f "$f" ] && chattr +i "$f" 2>/dev/null || true
done
[ -f "$BACKUP_ROOT/.env.backup_${TS}" ] && chattr +i "$BACKUP_ROOT/.env.backup_${TS}" 2>/dev/null || true

echo "=== Backup done: $TS ==="
echo "To restore: sudo deploy/rollback.sh $TS"
echo "To unlock for deletion: sudo deploy/unlock_backups.sh"

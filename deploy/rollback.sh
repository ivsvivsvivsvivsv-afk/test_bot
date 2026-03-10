#!/usr/bin/env bash
# ==============================================================
# HYDRA BOT — Откат на предыдущую версию (Patch 2)
# ==============================================================
# Использование:
#   sudo deploy/rollback.sh 20260304_120000
#   sudo deploy/rollback.sh latest
# ==============================================================
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/hydra_bot}"
PROJECT_DIR="${PROJECT_DIR:-/opt/hydra_bot}"
REDIS_DUMP="${REDIS_DUMP:-/var/lib/redis/dump.rdb}"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <timestamp|latest>"
    echo "Example: $0 20260304_120000"
    echo "Available backups:"
    ls -la "$BACKUP_ROOT/db/" 2>/dev/null | tail -5 || echo "No backups found"
    exit 1
fi

TS="$1"
if [ "$TS" = "latest" ]; then
    TS=$(ls -t "$BACKUP_ROOT/db"/hydra_*.dump 2>/dev/null | head -1 | sed 's/.*hydra_\(.*\)\.dump/\1/')
    [ -z "$TS" ] && { echo "No backups found"; exit 1; }
    echo "Using latest: $TS"
fi

DB_FILE="$BACKUP_ROOT/db/hydra_${TS}.dump"
REDIS_FILE="$BACKUP_ROOT/redis/dump_${TS}.rdb"
CODE_FILE="$BACKUP_ROOT/code/hydra_${TS}.tar.gz"

echo "=== HYDRA BOT: Rollback to $TS ==="
echo "WARNING: This will STOP services and RESTORE database/code."
read -p "Continue? (yes/no): " confirm
[ "$confirm" != "yes" ] && { echo "Aborted"; exit 0; }

# ── Stop services ───────────────────────────────────────────
echo "[1/5] Stopping services..."
systemctl stop hydra-bot hydra-worker 2>/dev/null || true

# ── Restore PostgreSQL ───────────────────────────────────────
if [ -f "$DB_FILE" ]; then
    echo "[2/5] Restoring PostgreSQL..."
    chattr -i "$DB_FILE" 2>/dev/null || true
    pg_restore -U hydra -d hydra_bot -c --if-exists -Fc "$DB_FILE" 2>/dev/null || true
    chattr +i "$DB_FILE" 2>/dev/null || true
else
    echo "  WARNING: DB backup not found: $DB_FILE"
fi

# ── Restore Redis ─────────────────────────────────────────────
if [ -f "$REDIS_FILE" ]; then
    echo "[3/5] Restoring Redis..."
    chattr -i "$REDIS_FILE" 2>/dev/null || true
    systemctl stop redis 2>/dev/null || true
    cp "$REDIS_FILE" "$REDIS_DUMP"
    chattr +i "$REDIS_FILE" 2>/dev/null || true
    systemctl start redis 2>/dev/null || true
else
    echo "  WARNING: Redis backup not found: $REDIS_FILE"
fi

# ── Restore code ──────────────────────────────────────────────
if [ -f "$CODE_FILE" ] && [ -d "$PROJECT_DIR" ]; then
    echo "[4/5] Restoring code..."
    chattr -i "$CODE_FILE" 2>/dev/null || true
    (cd "$PROJECT_DIR" && tar xzf "$CODE_FILE")
    chattr +i "$CODE_FILE" 2>/dev/null || true
else
    echo "  WARNING: Code backup not found or project dir missing"
fi

# ── Start services ────────────────────────────────────────────
echo "[5/5] Starting services..."
systemctl start hydra-bot hydra-worker

echo "=== Rollback complete ==="
echo "Check: systemctl status hydra-bot hydra-worker"
echo "Check: curl https://bot.neurounit.fun/health"

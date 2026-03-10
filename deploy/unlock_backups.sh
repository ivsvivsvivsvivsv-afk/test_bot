#!/usr/bin/env bash
# ==============================================================
# HYDRA BOT — Разблокировка бекапов для удаления (Patch 2)
# ==============================================================
# Бекапы защищены chattr +i. Этот скрипт снимает защиту.
# Запуск: sudo deploy/unlock_backups.sh
# ВНИМАНИЕ: Только для владельца сервера. Логируйте действия.
# ==============================================================
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/hydra_bot}"

echo "=== HYDRA BOT: Unlock backups ==="
echo "This removes immutable flag. Files can then be deleted."
echo ""
echo "Available backups (db):"
ls -la "$BACKUP_ROOT/db/" 2>/dev/null || echo "No db backups"
echo ""
echo "Enter timestamp to unlock (YYYYMMDD_HHMMSS), 'all', or 'q' to quit:"
read -r input

[ "$input" = "q" ] && exit 0

unlock_one() {
    local f="$1"
    if [ -f "$f" ]; then
        if chattr -i "$f" 2>/dev/null; then
            echo "  Unlocked: $f"
        else
            echo "  Failed or already unlocked: $f"
        fi
    fi
}

if [ "$input" = "all" ]; then
    echo "Unlocking ALL backups..."
    for f in "$BACKUP_ROOT"/db/hydra_*.dump \
             "$BACKUP_ROOT"/redis/dump_*.rdb \
             "$BACKUP_ROOT"/code/hydra_*.tar.gz \
             "$BACKUP_ROOT"/.env.backup_*; do
        unlock_one "$f"
    done
else
    TS="$input"
    unlock_one "$BACKUP_ROOT/db/hydra_${TS}.dump"
    unlock_one "$BACKUP_ROOT/redis/dump_${TS}.rdb"
    unlock_one "$BACKUP_ROOT/code/hydra_${TS}.tar.gz"
    unlock_one "$BACKUP_ROOT/.env.backup_${TS}"
fi

echo "Done. You can now delete unlocked files if needed."

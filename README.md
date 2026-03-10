# 🐉 НЕЙРО-ЮНИТ: КВЕСТ «ГИДРА СИНГУЛЯРНОСТИ»

Актуальная backend-версия Telegram-бота с webhook, PostgreSQL, Redis, YooKassa и отдельным worker-процессом.

## Production Snapshot

- **Домен:** `https://bot.neurounit.fun`
- **Сервер:** `82.146.39.44` (Ubuntu 24.04)
- **Папка проекта:** `/opt/hydra_bot`
- **Сервисы:** `hydra-bot`, `hydra-worker`
- **Режим:** webhook-only (без polling в production)
- **Медиа:** только Telegram `file_id` (без локального хранения изображений)

## Source Of Truth

- Основной документ по архитектуре и бизнес-логике: `TZ.md` (текущая версия `v7.7`).
- **Patch 2:** единая админка neurounit.fun/admin — `plan/PATCH_2_*.md`, `plan/UNIFIED_ADMIN_SPEC.md`.
- **Для лендинга:** `plan/REQUIREMENTS_FOR_LANDING.md` — что реализовать на neurounit.fun.
- Пошаговый операционный деплой: `deploy/DEPLOY_GUIDE.md`.
- Изоляция окружений (sandbox/prod): `deploy/SANDBOX_STRATEGY.md`.
- Этапные файлы в `plan/` — проектная история; при конфликте приоритет у `TZ.md`.

## Быстрый запуск (локально)

```bash
python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

## Production Commands

```bash
# Статусы
systemctl status hydra-bot
systemctl status hydra-worker

# Логи
journalctl -u hydra-bot -f
journalctl -u hydra-worker -f

# Проверка здоровья
curl -sS https://bot.neurounit.fun/health
```

## Базовые команды бота

- `/start` — старт воронки
- `/status` — текущий прогресс
- `/help` — справка
- `/restart` для обычного пользователя отсутствует по архитектуре one-shot квеста

## Документационная дисциплина

- Любая правка логики/контента/инфры фиксируется в `TZ.md` отдельной ревизией.
- После изменений код и docs синхронизируются в одном цикле деплоя.
- Нельзя оставлять расхождения между `content/texts.json`, `handlers/*` и описанием в `TZ.md`.

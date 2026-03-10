# Деплой: сначала Sandbox, потом Production

## Приоритет: Sandbox → Production

1. **Сначала** накатываем и тестируем в sandbox.
2. **После** проверки — деплой на production.

---

## Sandbox: первый запуск

### Предусловия

- Сервер с Ubuntu (PostgreSQL, Redis, NGINX, Python 3.12)
- Домен `neurounit.fun` привязан к серверу
- DNS: A-запись `bot-sandbox.neurounit.fun` → IP сервера
- Создан бот в BotFather: **@Neurounit_Sandbox_bot** (токен сохранён)

### Шаг 1: Клонировать prod (если ещё нет)

```bash
cd /opt
git clone <URL_РЕПОЗИТОРИЯ> hydra_bot
cd hydra_bot
# Настроить prod .env, systemd и т.д. (см. deploy/setup.sh)
```

### Шаг 2: Запустить setup sandbox

```bash
cd /opt/hydra_bot
sudo bash deploy/setup_sandbox.sh
```

Скрипт:
- Клонирует/копирует код в `/opt/hydra_bot_sandbox`
- Создаёт БД `hydra_bot_sandbox`
- Генерирует секреты (WEBHOOK_SECRET, ADMIN_API_SECRET)
- Создаёт `.env` из `.env.sandbox.example`
- Устанавливает systemd, NGINX, certbot

### Шаг 3: Вставить BOT_TOKEN sandbox-бота

```bash
nano /opt/hydra_bot_sandbox/.env
```

Заменить:
```
BOT_TOKEN=123456789:ABCdef...
```
на токен от @Neurounit_Sandbox_bot (из сообщения BotFather при создании бота).

### Шаг 4: Запустить сервисы

```bash
sudo systemctl start hydra-bot-sandbox hydra-worker-sandbox
sudo systemctl status hydra-bot-sandbox hydra-worker-sandbox
journalctl -u hydra-bot-sandbox -f
```

### Шаг 5: Проверка

1. **Telegram:** открыть https://t.me/Neurounit_Sandbox_bot, написать `/start`
2. **Health:** https://bot-sandbox.neurounit.fun/health
3. **Admin API:** `curl -H "X-Admin-Secret: <ADMIN_API_SECRET>" https://bot-sandbox.neurounit.fun/api/admin/stats`

---

## Sandbox: обновление кода

```bash
cd /opt/hydra_bot_sandbox
bash deploy/guarded_deploy.sh --env sandbox --project-dir /opt/hydra_bot_sandbox
```

При запросе подтверждения ввести: `sandbox:hydra-sandbox`

---

## Production: деплой после проверки в sandbox

```bash
cd /opt/hydra_bot
bash deploy/guarded_deploy.sh --env production --project-dir /opt/hydra_bot --strict-prod
```

Подтверждение: `production:hydra-prod`

---

## Что реализовано по ТЗ (Patch 2)

| Компонент | Статус |
|-----------|--------|
| HTTP API `/api/admin/*` | ✅ |
| Auth X-Admin-Secret + rate limit | ✅ |
| Сегменты, рассылки, scheduled | ✅ |
| Лиды, заметки, статусы | ✅ |
| Button click метрики | ✅ |
| Notification rules (scheduled_once, recurring) | ✅ |
| Webhook `/api/webhook/site` | ✅ |
| Sandbox/prod изоляция | ✅ |
| UI neurounit.fun/admin | ⏳ На стороне лендинга |

Бот предоставляет API. UI админки — на лендинге (Flask), который вызывает `BOT_API_URL` с `X-Admin-Secret`.

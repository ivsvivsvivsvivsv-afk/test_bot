# Sandbox: как смотреть бота и пользоваться на практике

## Кратко

- **Sandbox** — копия бота на **поддомене** (`bot-sandbox.neurounit.fun`) с **отдельным Telegram-ботом** (новый токен от BotFather).
- Один и тот же код, разные `.env`, БД, Redis DB, systemd-сервисы.
- Сначала тестируем в sandbox, затем деплоим на prod.

---

## 1. Поддомен для sandbox

Да, бота можно развернуть на поддомене и там смотреть.

| Окружение | Домен | Порт Gunicorn |
|-----------|-------|---------------|
| Production | `bot.neurounit.fun` | 8443 |
| Sandbox | `bot-sandbox.neurounit.fun` | 18443 |

В DNS добавляете A-запись:
```
bot-sandbox.neurounit.fun → 82.146.39.44
```

SSL:
```bash
certbot --nginx -d bot-sandbox.neurounit.fun
```

---

## 2. Новый Telegram-бот для sandbox

**Да, нужен отдельный бот.**

1. Открыть [@BotFather](https://t.me/BotFather).
2. `/newbot` → имя, например `Neurounit Sandbox`.
3. Получить токен вида `123456789:ABCdef...`.
4. Использовать этот токен **только** в `.env` sandbox-инстанса.

Один код, два бота:
- Prod: `@neurounit_bot` (токен в `/opt/hydra_bot/.env`)
- Sandbox: `@neurounit_sandbox_bot` (токен в `/opt/hydra_bot_sandbox/.env`)

---

## 3. Практический сценарий

### Шаг 1: Клонировать проект в sandbox-директорию

```bash
cd /opt
git clone <repo_url> hydra_bot_sandbox
cd /opt/hydra_bot_sandbox
```

### Шаг 2: Маркер и env

```bash
cat > .deploy-target <<'EOF'
TARGET_ENV=sandbox
TARGET_INSTANCE=hydra-sandbox
EOF

cp .env.sandbox.example .env
nano .env
```

Заполнить:
- `BOT_TOKEN` — токен sandbox-бота от BotFather
- `WEBHOOK_HOST=https://bot-sandbox.neurounit.fun`
- `WEBHOOK_PORT=18443`
- `DB_NAME=hydra_bot_sandbox`
- `REDIS_URL=redis://localhost:6379/1`
- `APP_ENV=sandbox`
- `APP_INSTANCE=hydra-sandbox`
- `ADMIN_API_SECRET` — свой секрет (отдельный от prod)
- `DB_PASSWORD` — пароль для sandbox-БД

### Шаг 3: БД и Redis

```bash
sudo -u postgres psql -c "CREATE DATABASE hydra_bot_sandbox OWNER hydra;"
PGPASSWORD='...' psql -U hydra -d hydra_bot_sandbox -f schema.sql
```

Redis DB 1 используется по умолчанию (`redis://localhost:6379/1`).

### Шаг 4: Systemd и NGINX

```bash
sudo cp deploy/hydra-bot-sandbox.service /etc/systemd/system/
sudo cp deploy/hydra-worker-sandbox.service /etc/systemd/system/
sudo cp deploy/nginx.sandbox.conf /etc/nginx/sites-available/hydra-bot-sandbox
sudo ln -sf /etc/nginx/sites-available/hydra-bot-sandbox /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo systemctl daemon-reload
sudo systemctl enable hydra-bot-sandbox hydra-worker-sandbox
sudo systemctl start hydra-bot-sandbox hydra-worker-sandbox
```

### Шаг 5: Webhook Telegram

После старта сервисов Telegram сам начнёт слать обновления на:
`https://bot-sandbox.neurounit.fun/webhook/bot`

Проверка:
```bash
curl "https://api.telegram.org/bot<SANDBOX_TOKEN>/getWebhookInfo"
# url должен быть https://bot-sandbox.neurounit.fun/webhook/bot
```

### Шаг 6: Тестирование

1. Открыть sandbox-бота в Telegram.
2. Написать `/start` — должно прийти приветствие.
3. Пройти квест, проверить рассылки, API.
4. Админка на сайте: `BOT_API_URL=https://bot-sandbox.neurounit.fun` — смотреть данные sandbox-бота.

---

## 4. Деплой на prod после проверки в sandbox

```bash
cd /opt/hydra_bot
bash deploy/guarded_deploy.sh --env production --project-dir /opt/hydra_bot --strict-prod
```

Скрипт запросит подтверждение `production:hydra-prod` и выполнит predeploy-check, обновление кода, рестарт сервисов и smoke.

---

## 5. Важно

- Prod и sandbox **никогда** не используют один и тот же `BOT_TOKEN`.
- Prod и sandbox — разные БД (`hydra_bot` и `hydra_bot_sandbox`).
- Prod и sandbox — разные Redis DB (0 и 1).
- Секреты (`ADMIN_API_SECRET`, `SITE_WEBHOOK_SECRET`) — разные для prod и sandbox.

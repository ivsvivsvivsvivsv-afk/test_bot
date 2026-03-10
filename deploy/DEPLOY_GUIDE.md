# 🚀 Инструкция по деплою Hydra Bot — для новичков

> Актуальность: production-окружение `bot.neurounit.fun` (`82.146.39.44`), путь `/opt/hydra_bot`.
> Если текст в этом гайде конфликтует с `TZ.md`, приоритет у `TZ.md`.

Подробная пошаговая инструкция. Выполнять **на VDS-сервере** (FirstVDS и др.), а не на локальном компьютере.

---

## Рекомендуемый порядок: сначала sandbox, потом production

1. Поднять **песочницу** на отдельном пути `/opt/hydra_bot_sandbox`, отдельном домене (`bot-sandbox.neurounit.fun`) и отдельных service-именах (`hydra-bot-sandbox`, `hydra-worker-sandbox`).
2. Прогнать интеграционные проверки и smoke в sandbox.
3. Только после этого деплоить production.

Анти-путаница встроена:
- `.deploy-target` (маркер инстанса),
- `.env` c `APP_ENV` и `APP_INSTANCE`,
- `deploy/guarded_deploy.sh` блокирует mismatched target.

---

## Что нужно ПЕРЕД началом

| Данные | Где взять |
|--------|-----------|
| **Домен** | Админка VDS: bot.neurounit.fun или ваш домен, привязанный к серверу |
| **BOT_TOKEN** | @BotFather → /mybots → ваш бот → API Token |
| **ADMIN_IDS** | 190421400, 758800494 (уже указаны) |
| **YooKassa Shop ID** | 390540012 |
| **YooKassa Secret Key** | Личный кабинет ЮKassa → Настройки → Секретные ключи → Live (полная строка типа `live_89296_xxxxxxxx`) |
| **SSH-доступ** | Логин/пароль или ключ для входа на VDS |

---

## Шаг 1: Подключиться к серверу

```bash
ssh root@82.146.39.44
# или: ssh пользователь@ваш_домен
```

Замените IP/домен на реальный адрес вашего VDS из админ-панели.

---

## Шаг 1.1: (РЕКОМЕНДУЕТСЯ) Подготовить sandbox-клон

```bash
cd /opt
git clone <repo_url> hydra_bot_sandbox
cd /opt/hydra_bot_sandbox

# Маркер цели деплоя
cat > .deploy-target <<'EOF'
TARGET_ENV=sandbox
TARGET_INSTANCE=hydra-sandbox
EOF

# env для sandbox
cp .env.sandbox.example .env
nano .env
```

Минимум для sandbox:
- `APP_ENV=sandbox`
- `APP_INSTANCE=hydra-sandbox`
- `WEBHOOK_HOST=https://bot-sandbox.neurounit.fun`
- `WEBHOOK_PORT=18443`
- отдельная БД (`hydra_bot_sandbox`) и Redis DB (`redis://localhost:6379/1`)

Установить sandbox юниты:
```bash
cp deploy/hydra-bot-sandbox.service /etc/systemd/system/
cp deploy/hydra-worker-sandbox.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable hydra-bot-sandbox hydra-worker-sandbox
systemctl start hydra-bot-sandbox hydra-worker-sandbox
```

Sandbox smoke:
```bash
sudo bash deploy/sandbox_smoke.sh
```

---

## Шаг 2: Загрузить код и запустить скрипт настройки (PostgreSQL, Redis, NGINX)

Скрипт установит PostgreSQL, Redis, Python, NGINX и **создаст БД с пользователем hydra**. Пароль PostgreSQL генерируется автоматически.

```bash
# Загружаем код на сервер (выберите один способ):

# Вариант А: git clone (если репозиторий на GitHub)
cd /opt
git clone https://github.com/ваш_логин/test_bot.git hydra_bot

# Вариант Б: скопировать с локального компьютера
# На вашем ПК: scp -r "c:\Users\zhurk\Documents\GitHub\test_bot — копия" user@IP_сервера:/opt/hydra_bot

cd /opt/hydra_bot
sudo bash deploy/setup.sh
```

**Важно:** В конце скрипт выведет:
```
DB_PASSWORD     = <сгенерированный_пароль>
WEBHOOK_SECRET  = <сгенерированная_строка>
```
**Сохраните их** — они понадобятся для .env.

---

## Шаг 3: WEBHOOK_HOST — что это и откуда брать

**WEBHOOK_HOST** — это публичный HTTPS-адрес вашего сервера, куда Telegram и YooKassa будут слать запросы.

- Если в админке FirstVDS указан домен `bot.neurounit.fun` — используйте: `https://bot.neurounit.fun`
- Если другой домен — подставьте его: `https://ваш_домен.ru`

**Почему нельзя «сделать самому»:** Я не имею доступа к вашему серверу и не знаю, какой домен к нему привязан. Вы указываете его в .env вручную.

**Проверка:** После SSL (шаг 6) откройте в браузере `https://bot.neurounit.fun/health` — должно вернуться `{"status":"ok"}`.

---

## Шаг 4: Создать и заполнить .env

```bash
cd /opt/hydra_bot
cp .env.example .env
nano .env
```

Заполните по образцу (подставьте свои значения):

```env
# Telegram — токен от @BotFather
BOT_TOKEN=<ваш_токен_из_BotFather>
ADMIN_IDS=190421400,758800494
ADMIN_USERNAME=ваш_telegram_username

# Webhook — замените домен, если отличается
WEBHOOK_HOST=https://bot.neurounit.fun
WEBHOOK_PATH=/webhook/bot
WEBHOOK_PORT=8443
WEBHOOK_SECRET=<из шага 2 — строка вида a1b2c3d4...>

# PostgreSQL — пароль из шага 2
DB_HOST=localhost
DB_PORT=5432
DB_NAME=hydra_bot
DB_USER=hydra
DB_PASSWORD=<пароль из вывода setup.sh>
DB_POOL_MIN=2
DB_POOL_MAX=10

# Redis
REDIS_URL=redis://localhost:6379/0

# YooKassa Live — полный секретный ключ из ЛК
YOOKASSA_SHOP_ID=390540012
YOOKASSA_SECRET_KEY=live_89296_xxxxxxxxxxxxxxxxxx
YOOKASSA_RETURN_URL=https://t.me/ваш_бот

# Ссылки (по необходимости)
GENERATOR_BOT_URL=https://t.me/video_generator_bot
WORKSHOP_URL=https://ваш_воркшоп.com
PROMO_CODE=HYDRA50

# Дожим
FOLLOWUP_IDLE_MINUTES=5
FOLLOWUP_DAYS=5
```

Сохраните: `Ctrl+O`, `Enter`, `Ctrl+X`.

---

## Шаг 5: Применить схему БД (таблицы users, payments, config)

PostgreSQL уже установлен скриптом; таблицы создаются отдельно:

```bash
cd /opt/hydra_bot

# Вариант А: пароль в переменной
export PGPASSWORD='<DB_PASSWORD из шага 2>'
psql -U hydra -d hydra_bot -h localhost -f schema.sql

# Вариант Б: ввести пароль по запросу
psql -U hydra -d hydra_bot -h localhost -f schema.sql
```

Проверка:
```bash
psql -U hydra -d hydra_bot -h localhost -c "SELECT COUNT(*) FROM users;"
# Должно вернуть 0 (таблица пустая)
```

---

## Шаг 6: SSL-сертификат (обязательно для Telegram webhook)

Telegram принимает только HTTPS. Certbot получит бесплатный сертификат Let's Encrypt:

```bash
# Замените домен на ваш!
certbot --nginx -d bot.neurounit.fun
```

Следуйте подсказкам (email, согласие с условиями). После этого NGINX будет использовать SSL.

---

## Шаг 7: Обновить NGINX, если домен другой

Если домен не bot.neurounit.fun — отредактируйте конфиг:

```bash
nano /etc/nginx/sites-available/hydra-bot
```

Замените все вхождения `bot.neurounit.fun` на ваш домен. Проверка:

```bash
nginx -t
systemctl reload nginx
```

---

## Шаг 8: Установить Python-зависимости

```bash
cd /opt/hydra_bot
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

---

## Шаг 9: Прогнать predeploy-check (обязательно)

```bash
cd /opt/hydra_bot
source venv/bin/activate
python predeploy_check.py --strict-prod --check-services
```

Если есть `[FAIL]`, запуск в прод **останавливаем** и исправляем причину.

Рекомендуемый guarded-run (чтобы не перепутать инстанс):
```bash
bash deploy/guarded_deploy.sh --env production --project-dir /opt/hydra_bot --strict-prod
```

---

## Шаг 10: Запустить бота и worker

```bash
# Systemd-юниты (если ещё не установлены)
sudo cp deploy/hydra-bot.service /etc/systemd/system/
sudo cp deploy/hydra-worker.service /etc/systemd/system/
sudo systemctl daemon-reload

# Включить автозапуск
sudo systemctl enable hydra-bot hydra-worker

# Запустить
sudo systemctl start hydra-bot
sudo systemctl start hydra-worker

# Проверить статус
sudo systemctl status hydra-bot
sudo systemctl status hydra-worker
```

Оба сервиса должны быть `active (running)`.

---

## Шаг 11: Smoke-проверка после старта сервисов

```bash
cd /opt/hydra_bot
sudo bash deploy/production_smoke.sh
```

Скрипт проверит:
- `systemd` статусы `hydra-bot` и `hydra-worker`
- локальный `/health` (`127.0.0.1:8443`)
- публичный `/health` (`WEBHOOK_HOST/health`)
- `getWebhookInfo` Telegram (URL webhook должен совпадать)
- простые проверки Redis и PostgreSQL

---

## Шаг 12: Настроить webhook YooKassa и проверить бота

### YooKassa webhook

1. Войдите в [ЛК ЮKassa](https://yookassa.ru/)
2. Настройки → HTTP-уведомления
3. URL: `https://bot.neurounit.fun/yookassa/webhook` (или ваш домен)

### Проверка бота

1. Откройте бота в Telegram.
2. Напишите `/start` — должно прийти приветствие.
3. Пройдите квест до конца (класс → оружие → 3 раунда).
4. В боте напишите `/stats` (от имени админа) — должна появиться статистика.
5. Проверьте `/slots`, `/export_leads`.

### Логи при проблемах

```bash
journalctl -u hydra-bot -f
journalctl -u hydra-worker -f
```

---

## FAQ

### PostgreSQL — настроена ли она локально?

Нет. PostgreSQL работает **только на VDS**.  
Скрипт `deploy/setup.sh` ставит PostgreSQL на сервер и создаёт пользователя `hydra` с автоматическим паролем. Пароль выводится в консоль — его нужно вписать в .env как `DB_PASSWORD`.

### Можно ли запустить бота локально для теста?

Да, в режиме polling:

```bash
python bot.py
```

Потребуется .env с теми же переменными (можно использовать тестовый YooKassa и локальные PostgreSQL/Redis, если установлены).

### Где взять полный YooKassa Secret Key?

1. Войдите на [yookassa.ru](https://yookassa.ru/)
2. Меню → **Настройки** → **Секретные ключи**
3. Секция **Live** (боевой режим) → кнопка **Скопировать**
4. Вставьте в .env как `YOOKASSA_SECRET_KEY=live_89296_xxxxxxxx...` (без кавычек)

Формат: `live_89296_` + длинный хвост. Цифры «89296» — только часть, нужна вся строка.

---

## Чек-лист перед боевым трафиком

- [ ] YooKassa переключена на LIVE (не TEST)
- [ ] Webhook YooKassa настроен
- [ ] `python predeploy_check.py --strict-prod --check-services` завершился c `[PASS]`
- [ ] `sudo bash deploy/production_smoke.sh` завершился c `[PASS]`
- [ ] `FOLLOWUP_IDLE_MINUTES=5` (не 1)
- [ ] Выполнен `/reset_all` в боте (чистый старт)
- [ ] Пройден полный квест от /start до финала
- [ ] `/stats`, `/slots`, `/export_leads` работают

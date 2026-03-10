# ЭТАП 1: Инфраструктура и фундамент проекта

## САММАРИ

**Цель:** Подготовить сервер VDS и реструктуризировать проект под production-архитектуру.

**Что делаем:**
- Устанавливаем и настраиваем PostgreSQL 16, Redis 7, Python 3.12, NGINX на VDS (bot.neurounit.fun)
- Переносим структуру проекта с плоской (текущей) на модульную (по ТЗ v7.3)
- Создаём schema.sql для PostgreSQL (полная замена SQLite)
- Настраиваем SSL через Let's Encrypt
- Создаём systemd-юниты (заглушки) для двух процессов: бот + воркер
- Настраиваем .env и конфигурацию

**Что НЕ теряем:**
- Файлы `statements/*.txt` — копируются без изменений
- Все тексты из `texts.py` — мигрируются в `content/texts.json` на этапе 2
- Логика handlers — мигрируется на этапах 3-5

**Ключевые решения:**
- PostgreSQL вместо SQLite (ACID, connection pooling, конкурентность для 10K CCU)
- Redis для FSM, throttle, activity, slot holds, file_id cache (не для основных данных)
- Два systemd-процесса: Gunicorn (4 воркера) + worker.py (1 экземпляр)
- NGINX без rate limit на webhook (IP whitelist Telegram/YooKassa)
- DB_POOL_MAX = 10 на воркер (4×10 = 40 < PG default 100)

**Риски:**
- Первоначальная настройка PG может занять время при ошибках в pg_hba.conf
- Redis нужно настроить maxmemory (256MB) и persistence (save 300 10)

---

## 1. ТЕКУЩЕЕ СОСТОЯНИЕ

### Что есть сейчас
```
test_bot/
├── bot.py                  # Монолитная точка входа (polling + webhook)
├── config.py               # Settings dataclass
├── database.py             # SQLite + PostgreSQL (interface + 2 impl)
├── texts.py                # Хардкод текстов
├── handlers/               # 5 роутеров
├── keyboards/inline.py     # Клавиатуры
├── utils/                  # statements, validation, notifications
├── statements/             # 7 txt-файлов с утверждениями
├── Procfile                # Amvera (больше не нужен)
└── requirements.txt        # aiogram 3.4.1, aiosqlite, asyncpg, redis
```

### Проблемы текущей инфраструктуры
1. **SQLite** — не поддерживает конкурентную запись (1 writer), не масштабируется
2. **Один процесс** — и бот, и потенциальный scheduler в одном процессе
3. **Нет NGINX** — бот напрямую принимает webhook
4. **Нет systemd** — процесс не восстанавливается при падении
5. **Amvera-зависимость** — Procfile, нет контроля над инфраструктурой
6. **Нет SSL** — webhook Telegram требует HTTPS
7. **database.py** вызывает методы, которые не реализованы (update_user_class и др.)

---

## 2. ЦЕЛЕВАЯ СТРУКТУРА ПРОЕКТА

```
hydra_bot/
├── bot.py                          # Webhook-сервер (Gunicorn)
├── worker.py                       # Scheduler (отдельный процесс)
├── config.py                       # Настройки из .env
├── db.py                           # PostgreSQL: asyncpg pool
├── redis_client.py                 # Redis: подключение
│
├── handlers/                       # Роутеры aiogram
│   ├── __init__.py
│   ├── start.py
│   ├── quest.py
│   ├── contacts.py
│   ├── arena.py
│   ├── payment.py
│   ├── payment_webhook.py
│   ├── upsell.py
│   └── admin.py
│
├── middlewares/
│   ├── __init__.py
│   ├── throttle.py
│   ├── activity.py
│   ├── db_middleware.py
│   └── logging_mw.py
│
├── services/
│   ├── __init__.py
│   ├── quest_service.py
│   ├── payment_service.py
│   ├── followup_service.py
│   ├── media_service.py
│   ├── broadcast_service.py
│   └── notification_service.py
│
├── models/
│   ├── __init__.py
│   ├── user.py
│   └── payment.py
│
├── keyboards/
│   ├── __init__.py
│   └── inline.py
│
├── utils/
│   ├── __init__.py
│   ├── config_db.py
│   ├── content_manager.py
│   ├── statements.py               # Сохраняется без изменений!
│   └── validation.py
│
├── content/
│   ├── texts.json                   # Все тексты (миграция из texts.py)
│   └── media/
│       ├── miniquest_day1.jpg
│       ├── miniquest_day2.jpg
│       ├── miniquest_day3.jpg
│       ├── miniquest_day4.jpg
│       └── miniquest_day5.jpg
│
├── statements/                      # БЕЗ ИЗМЕНЕНИЙ!
│   ├── marketing.txt
│   ├── analytics.txt
│   ├── copywriting.txt
│   ├── design.txt
│   ├── management.txt
│   ├── video.txt
│   └── other.txt
│
├── schema.sql
├── deploy/
│   ├── nginx.conf
│   ├── hydra-bot.service
│   ├── hydra-worker.service
│   └── setup.sh
│
├── requirements.txt
├── .env.example
└── README.md
```

---

## 3. НАСТРОЙКА СЕРВЕРА VDS

### 3.1 Подключение и обновление
```bash
ssh root@82.146.39.44
apt update && apt upgrade -y
```

### 3.2 Установка компонентов
```bash
apt install -y \
    python3.12 python3.12-venv python3-pip \
    postgresql-16 postgresql-contrib \
    redis-server \
    nginx \
    certbot python3-certbot-nginx \
    git htop curl
```

### 3.3 PostgreSQL
```bash
# Создаём пользователя и базу
sudo -u postgres psql -c "CREATE USER hydra WITH PASSWORD '<STRONG_PASSWORD>';"
sudo -u postgres psql -c "CREATE DATABASE hydra_bot OWNER hydra;"

# Проверяем подключение
psql -U hydra -d hydra_bot -h localhost -c "SELECT 1;"
```

**Важно:** в `pg_hba.conf` должно быть `md5` или `scram-sha-256` для localhost.

### 3.4 Redis
```bash
# Включаем persistence
sed -i 's/# save 3600 1/save 300 10/' /etc/redis/redis.conf

# Ограничиваем память
echo "maxmemory 256mb" >> /etc/redis/redis.conf
echo "maxmemory-policy allkeys-lru" >> /etc/redis/redis.conf

# Перезапускаем
systemctl restart redis
redis-cli ping  # Ожидаем: PONG
```

### 3.5 SSL-сертификат
```bash
certbot --nginx -d bot.neurounit.fun
```

### 3.6 Директория проекта
```bash
mkdir -p /opt/hydra_bot
cd /opt/hydra_bot
python3.12 -m venv venv
source venv/bin/activate
```

---

## 4. SCHEMA.SQL — СОЗДАНИЕ ТАБЛИЦ

Это полная замена текущих таблиц из `database.py`. Ключевые отличия:
- Единая таблица `users` (вместо users + contacts раздельно)
- Поля для квеста, контактов, арены, дожима, upsell — всё в одной таблице
- Таблица `payments` (вместо `promo_messages`)
- Таблица `events` для аналитики
- Таблица `config` для горячей смены параметров

### Миграция данных
Текущая БД (SQLite) содержит минимум данных (бот в разработке). Данные **не переносим** — начинаем с чистой PostgreSQL.

### Что сохраняется из текущей схемы
| Текущее поле | Новое поле | Примечание |
|---|---|---|
| users.user_id | users.user_id | Telegram ID |
| users.username | users.username | @username |
| users.first_name | users.first_name | Имя |
| users.specialization | users.player_class | Переименование |
| users.weapon | users.weapon | Без изменений |
| contacts.phone | users.phone | Объединено в users |
| contacts.email | users.email | Объединено в users |
| promo_messages.* | payments.* | Полная переработка |
| settings.* | config.* | Переименование |

---

## 5. REQUIREMENTS.TXT

Обновление зависимостей с текущих на production:

| Пакет | Было | Стало | Зачем |
|-------|------|-------|-------|
| aiogram | 3.4.1 | 3.14.0 | Последняя стабильная, webhook improvements |
| aiohttp | 3.9.1 | 3.10.0 | Совместимость с Gunicorn |
| asyncpg | 0.29.0 | 0.30.0 | Connection pool improvements |
| redis | 5.0.1 | 5.2.0[hiredis] | hiredis для 3x скорости парсинга |
| yookassa | 3.2.0 | 3.4.0 | Bugfixes |
| gunicorn | - | 22.0.0 | **Новый**: multi-worker webhook |
| APScheduler | - | 3.10.4 | **Новый**: scheduler в worker.py |
| pydantic | - | 2.10.0 | **Новый**: валидация моделей |
| structlog | - | 24.4.0 | **Новый**: структурированные логи |
| python-dotenv | 1.0.0 | 1.0.1 | Bugfixes |
| aiosqlite | 0.19.0 | **удалён** | SQLite больше не используется |

---

## 6. DEPLOY ФАЙЛЫ

### 6.1 deploy/nginx.conf
- SSL-терминация (Let's Encrypt)
- `/webhook/` — проксирование на Gunicorn:8443, whitelist IP Telegram
- `/yookassa/` — проксирование, whitelist IP YooKassa
- `/ ` — return 444 (закрыто)
- **БЕЗ `limit_req`** — Telegram сам контролирует частоту

### 6.2 deploy/hydra-bot.service
- Gunicorn с 4 воркерами (aiohttp.GunicornWebWorker)
- Bind на 127.0.0.1:8443
- Restart=always, RestartSec=5
- EnvironmentFile=/opt/hydra_bot/.env

### 6.3 deploy/hydra-worker.service
- python worker.py (1 экземпляр!)
- Restart=always, RestartSec=10
- WatchdogSec=60

### 6.4 deploy/setup.sh
- Автоматизация всех шагов из раздела 3

---

## 7. КОНФИГУРАЦИЯ (.env)

Миграция с текущего `config.py` (Settings dataclass) на `.env` + простой модуль:

| Текущий параметр | Новый параметр | Изменение |
|---|---|---|
| bot_token | BOT_TOKEN | Формат .env |
| admin_ids | ADMIN_IDS | Comma-separated |
| admin_username | ADMIN_USERNAME | Без изменений |
| database_path | — | Удалено (SQLite) |
| database_url | DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD | Раздельные поля |
| webhook_host | WEBHOOK_HOST | Без изменений |
| webhook_path | WEBHOOK_PATH | Без изменений |
| redis_url | REDIS_URL | Без изменений |
| yookassa_* | YOOKASSA_* | Без изменений |
| — | WEBHOOK_SECRET | **Новый**: secret_token для безопасности |
| — | WEBHOOK_PORT | **Новый**: порт Gunicorn |
| — | DB_POOL_MIN/MAX | **Новый**: управление пулом |
| — | FOLLOWUP_* | **Новый**: настройки дожима |

---

## 8. УЛУЧШЕНИЯ ЭТОГО ЭТАПА

### 8.1 Технологические
- **Connection pooling** — asyncpg pool вместо единичных подключений SQLite
- **Redis persistence** — FSM не теряется при перезапуске бота
- **Graceful restart** — systemd watchdog + Gunicorn graceful reload
- **SSL/TLS** — обязательно для webhook Telegram
- **IP whitelist** — защита от DDoS на webhook endpoints

### 8.2 Функциональные
- **Горячая смена параметров** — таблица `config` в PostgreSQL (цена, количество слотов, флаги) без перезапуска бота
- **Таблица events** — каждое действие пользователя логируется для аналитики
- **Единая таблица users** — контакты, прогресс, дожим в одном месте (нет JOIN при каждом запросе)

### 8.3 Для вовлечённости (закладка на будущее)
- Поля `utm_source` и `referrer` в таблице users — отслеживание источника трафика с первого дня
- Индексы на `quest_state`, `workshop_registered`, `followup_stage` — быстрые выборки для дожима
- Поле `created_at` с индексом — когорный анализ пользователей

---

## 9. ЧЕК-ЛИСТ ЭТАПА

- [ ] SSH доступ к VDS (82.146.39.44)
- [ ] Установлен Python 3.12 + venv
- [ ] Установлен и настроен PostgreSQL 16
- [ ] Установлен и настроен Redis 7
- [ ] Установлен NGINX + SSL (certbot)
- [ ] Создана директория /opt/hydra_bot
- [ ] Создан schema.sql и применён к БД
- [ ] Создан .env.example с описанием всех переменных
- [ ] Создан config.py (чтение из .env)
- [ ] Создан deploy/setup.sh
- [ ] Создан deploy/nginx.conf (whitelist IP Telegram + YooKassa)
- [ ] Создан deploy/hydra-bot.service (Gunicorn, 4 воркера)
- [ ] Создан deploy/hydra-worker.service (scheduler, 1 экземпляр)
- [ ] Обновлён requirements.txt
- [ ] Файлы statements/*.txt скопированы без изменений
- [ ] Procfile удалён (Amvera больше не используется)

---

## 10. ЗАВИСИМОСТИ ОТ ДРУГИХ ЭТАПОВ

- **Этот этап** → ничего не зависит, можно начинать сразу
- **Этап 2** зависит от: schema.sql, config.py, requirements.txt
- **Этапы 3-8** зависят от: полной инфраструктуры этого этапа

# 🐉 НЕЙРО-ЮНИТ: КВЕСТ «ГИДРА СИНГУЛЯРНОСТИ»

**Highload Telegram Bot для 100K+ пользователей**

## 🏗 Архитектура

```
┌──────────────────────────────────────────────────────────────┐
│                         AMVERA                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │ Instance 1  │  │ Instance 2  │  │ Instance 3  │  ← Авто-  │
│  │  (aiohttp)  │  │  (aiohttp)  │  │  (aiohttp)  │    скейл  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘           │
│         └────────────────┼────────────────┘                  │
│                          │                                    │
│         ┌────────────────┴────────────────┐                  │
│         ▼                                 ▼                  │
│  ┌─────────────┐                  ┌──────────────┐           │
│  │    Redis    │                  │  PostgreSQL  │           │
│  │ (FSM+Locks) │                  │    (data)    │           │
│  └─────────────┘                  └──────────────┘           │
└──────────────────────────────────────────────────────────────┘
```

**Ключевые особенности:**
- ✅ **Telegram Webhook** — не polling! Масштабируется горизонтально
- ✅ **Redis** — FSM состояния + distributed locks между инстансами
- ✅ **PostgreSQL** — connection pooling, выдерживает нагрузку
- ✅ **YooKassa** — приём платежей через webhook

---

## 🚀 Деплой на Amvera (Production)

### Шаг 1: Создайте проект

1. Зайдите на [amvera.ru](https://amvera.ru)
2. Создайте новый проект (тип: **Web**)
3. Подключите Git-репозиторий

### Шаг 2: Создайте managed-сервисы

#### PostgreSQL:
1. **Сервисы → Создать → PostgreSQL**
2. Выберите тариф (минимум 1 ГБ RAM для 100K)
3. Запишите `DATABASE_URL` в формате:
   ```
   postgresql://user:password@host:5432/dbname
   ```

#### Redis:
1. **Сервисы → Создать → Redis**
2. Выберите тариф
3. Запишите `REDIS_URL` в формате:
   ```
   redis://default:password@host:6379/0
   ```

### Шаг 3: Настройте переменные окружения

В настройках проекта → **Переменные окружения**:

```bash
# === ОБЯЗАТЕЛЬНЫЕ ===
BOT_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi
ADMIN_IDS=123456789,987654321

# === WEBHOOK (ОБЯЗАТЕЛЬНО для production!) ===
WEBHOOK_HOST=https://your-project.amvera.io

# === БАЗА ДАННЫХ ===
DATABASE_URL=postgresql://user:password@host:5432/dbname

# === REDIS (ОБЯЗАТЕЛЬНО для масштабирования!) ===
REDIS_URL=redis://default:password@host:6379/0

# === YooKassa ===
YOOKASSA_SHOP_ID=123456
YOOKASSA_SECRET_KEY=live_xxxxxxxxxxxxxx
YOOKASSA_RETURN_URL=https://t.me/your_bot
```

### Шаг 4: Настройте YooKassa Webhook

1. Зайдите в [личный кабинет YooKassa](https://yookassa.ru/my)
2. **Интеграция → HTTP-уведомления**
3. Добавьте URL:
   ```
   https://your-project.amvera.io/webhook/yookassa
   ```
4. Выберите события: `payment.succeeded`, `payment.canceled`

### Шаг 5: Деплой

```bash
git add .
git commit -m "Deploy to Amvera"
git push amvera main
```

### Шаг 6: Проверка

1. Откройте `https://your-project.amvera.io/health`
2. Должны увидеть:
   ```json
   {"status": "ok", "service": "neuro-unit-bot", "mode": "webhook"}
   ```

---

## 💻 Локальная разработка

### 1. Клонируйте и настройте

```bash
git clone <your-repo>
cd hydra_bot_v2
cp .env.example .env
# Отредактируйте .env — укажите BOT_TOKEN и ADMIN_IDS
```

### 2. Установите зависимости

```bash
pip install -r requirements.txt
```

### 3. Запустите (polling mode)

```bash
python bot.py
```

⚠️ **Важно:** Без `WEBHOOK_HOST` бот запускается в polling mode. Это только для разработки!

---

## 📁 Структура проекта

```
hydra_bot_v2/
├── bot.py              # Главный файл (webhook + polling)
├── config.py           # Конфигурация
├── database.py         # PostgreSQL + SQLite (factory pattern)
├── texts.py            # Тексты бота
├── handlers/
│   ├── start.py        # /start, /help, /restart
│   ├── quest.py        # Логика квеста
│   ├── contacts.py     # Сбор контактов
│   ├── arena.py        # Арена
│   └── promo.py        # Промо-акция + YooKassa
├── keyboards/
│   └── inline.py       # Клавиатуры
├── utils/
│   ├── validation.py   # Валидация телефона/email
│   ├── notifications.py # Уведомления админам
│   └── statements.py   # Загрузка утверждений
├── statements/         # Файлы с утверждениями
├── Procfile            # web: python bot.py
├── requirements.txt
└── .env.example
```

---

## ⚙️ Как работает highload

### Telegram Webhook vs Polling

| | Polling | Webhook |
|--|---------|---------|
| Как работает | Бот спрашивает Telegram каждые N сек | Telegram сам отправляет updates |
| Масштабирование | ❌ 1 процесс | ✅ Любое кол-во инстансов |
| Задержка | 1-5 сек | ~0 мс |
| Для 100K | ❌ Захлебнётся | ✅ Легко |

### Redis для FSM

**Без Redis:** Состояние в памяти → При рестарте теряется → При нескольких инстансах ломается

**С Redis:** Состояние в Redis → Персистентно → Шарится между инстансами

### Distributed Locks

**Проблема:** Два инстанса одновременно обрабатывают оплату → Race condition → Двойное списание слотов

**Решение:** Redis distributed lock с `SET NX EX`

```python
# Только один инстанс может войти
async with RedisLock(redis, "promo_payment:123"):
    slots = await db.decrement_promo_slots()
```

### PostgreSQL Connection Pooling

**Без пула:** Каждый запрос = новое соединение = медленно + лимиты

**С пулом:** 5-20 соединений переиспользуются = быстро + стабильно

```python
pool = await asyncpg.create_pool(
    dsn, min_size=5, max_size=20
)
```

---

## 🔧 Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Начать квест |
| `/restart` | Сбросить прогресс |
| `/status` | Показать статус |
| `/help` | Справка |

---

## 📊 Мониторинг

### Health Check

```
GET https://your-project.amvera.io/health
```

### Логи в Amvera

**Консоль → Логи** — смотрите в реальном времени

### Метрики (рекомендуется)

Добавьте Prometheus endpoint и Grafana для production.

---

## 🆘 Troubleshooting

### Бот не отвечает

1. Проверьте логи в Amvera
2. Проверьте `WEBHOOK_HOST` — должен быть HTTPS
3. Проверьте что webhook установлен:
   ```
   https://api.telegram.org/bot<TOKEN>/getWebhookInfo
   ```

### YooKassa не приходят уведомления

1. Проверьте URL в настройках YooKassa
2. Проверьте что `/webhook/yookassa` доступен извне
3. Смотрите логи на 400/500 ошибки

### Redis connection refused

1. Проверьте `REDIS_URL`
2. Проверьте что Redis сервис запущен
3. Проверьте firewall между сервисами

### PostgreSQL too many connections

1. Увеличьте `max_size` в пуле (но не больше лимита сервера)
2. Проверьте что connection leak нет
3. Увеличьте тариф PostgreSQL

---

## 📄 Лицензия

Проприетарное ПО. © НЕЙРО-ЮНИТ 2025

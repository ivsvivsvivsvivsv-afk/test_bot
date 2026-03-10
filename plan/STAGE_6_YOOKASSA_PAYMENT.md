# ЭТАП 6: Интеграция YooKassa и платёжная логика

## САММАРИ

**Цель:** Реализовать надёжную, атомарную систему оплаты «Разбор бизнеса» через YooKassa с защитой от race conditions при 1000+ одновременных пользователей.

**Что делаем:**
- `services/payment_service.py` — атомарное резервирование слотов через Lua-скрипты в Redis
- `handlers/payment.py` — создание платежа, кнопка "Оплатить"
- `handlers/payment_webhook.py` — обработка webhook от YooKassa (aiohttp endpoint)
- Lua-скрипты: HOLD_SLOT_LUA (атомарная проверка + бронь), CHECK_LIMIT_LUA (подсчёт)
- Zombie-payment protection: автовозврат если 10/10
- Идемпотентность webhook: UPDATE WHERE status != 'succeeded' RETURNING id

**Что ОБЯЗАТЕЛЬНО сохраняем из текущего кода:**
- Создание платежа через yookassa SDK (Payment.create)
- Distributed lock при оплате (RedisLock → Lua-скрипт)
- Подтверждение оплаты через webhook
- Уведомление пользователя и админов
- Cleanup промо-сообщений при исчерпании слотов

## РЕШЕНИЕ ПО ТИПУ ИНТЕГРАЦИИ (для коммуникации с YooKassa)

**Выбранный путь:** сторонняя интеграция через API YooKassa (redirect + HTTP webhook), НЕ Telegram Payments `sendInvoice`.

**Почему:**
- В проекте уже реализован production-контур: `services/payment_service.py` + `handlers/payment_webhook.py`.
- Нужна собственная highload-логика бронирования слотов (Redis Lua hold), идемпотентность webhook и auto-refund для zombie-платежей.
- Эта логика находится на нашей стороне приложения и не покрывается базовым сценарием подключения через BotFather payment provider token.

**Что это означает для поддержки YooKassa:**
- Магазин должен быть на протоколе API.
- Мы используем `shop_id` + `secret_key`, создаём платежи через SDK/API.
- Webhook событий (`payment.succeeded`, `payment.canceled`) принимаем на endpoint проекта.

**Критические архитектурные правила (ТЗ v7.3):**
1. YooKassa SDK **синхронный** — все вызовы через `asyncio.to_thread()`
2. HOLD слота ПЕРЕД генерацией ссылки — атомарный Lua (не два Redis-вызова)
3. Zombie-платежи: если paid_count > total_slots → auto Refund.create + уведомление
4. Идемпотентность: UPDATE payments SET status='succeeded' WHERE status != 'succeeded' RETURNING id
5. НИКОГДА не использовать redis.keys() — Sorted Set + ZCARD
6. Sorted Set для holds: ZADD holds_key score=expire_timestamp member=user_id, ZREMRANGEBYSCORE для cleanup

**Отличия от текущей реализации (promo.py):**
| Было (promo.py) | Стало (payment_service.py) |
|---|---|
| Redis SET NX + EXPIRE (два вызова) | Атомарный Lua-скрипт (одна операция) |
| redis.keys("hold:*") для подсчёта | Sorted Set + ZCARD = O(1) |
| Синхронный Payment.create блокирует loop | asyncio.to_thread(Payment.create) |
| Нет zombie-protection | Auto-refund если 10/10 |
| Нет идемпотентности webhook | WHERE status != 'succeeded' RETURNING id |
| decrement_promo_slots в PostgreSQL | Paid count из PG + holds из Redis Sorted Set |

---

## 1. АТОМАРНЫЕ LUA-СКРИПТЫ

### Почему Lua, а не две Redis-команды
При 500 одновременных запросах (TikTok-волна):
```
# БЕЗ Lua (race condition):
User A: ZCARD = 9  (видит 1 свободное место)
User B: ZCARD = 9  (тоже видит 1 место)
User A: ZADD → 10  (забронировал)
User B: ZADD → 11  (тоже забронировал → ПЕРЕБРОНИРОВАНИЕ!)
```

```
# С Lua (атомарно):
User A: Lua script → ZCARD=9, 9<10, ZADD → return 1 (OK)
User B: Lua script → ZCARD=10, 10>=10 → return 0 (НЕТ МЕСТ)
```

### HOLD_SLOT_LUA
```lua
-- Проверка лимита + установка холда (АТОМАРНО)
local holds_key = KEYS[1]        -- "upsell:holds"
local user_id = ARGV[1]          -- ID пользователя
local max_slots = tonumber(ARGV[2])  -- 10
local paid_count = tonumber(ARGV[3]) -- из PostgreSQL
local now = tonumber(ARGV[4])    -- текущее время
local ttl = tonumber(ARGV[5])    -- 900 (15 мин)

-- Чистим expired holds
redis.call('ZREMRANGEBYSCORE', holds_key, '-inf', now)

-- Считаем активные holds
local active_holds = redis.call('ZCARD', holds_key)

-- Проверяем лимит
if (paid_count + active_holds) >= max_slots then return 0 end

-- Устанавливаем hold (score = время истечения)
redis.call('ZADD', holds_key, now + ttl, user_id)
return 1
```

### CHECK_LIMIT_LUA
```lua
-- Подсчёт активных холдов (без блокировки Redis)
local holds_key = KEYS[1]
local now = tonumber(ARGV[1])
redis.call('ZREMRANGEBYSCORE', holds_key, '-inf', now)
return redis.call('ZCARD', holds_key)
```

---

## 2. SERVICES/PAYMENT_SERVICE.PY

### Основные функции
```python
async def get_remaining_slots(pool, redis_conn) -> int
    """Подсчёт: total - paid - held"""
    
async def try_hold_slot(pool, redis_conn, user_id) -> bool
    """Атомарный HOLD через Lua. True = место забронировано."""
    
async def release_hold(redis_conn, user_id)
    """Отпускает бронь (Пропустить / оплата прошла)"""
    
async def create_payment(pool, redis_conn, user_id) -> dict
    """Создаёт платёж в YooKassa. Только если hold установлен."""
```

### create_payment() — подробная логика
```
1. remaining = get_remaining_slots(pool, redis_conn)
2. if remaining <= 0: release_hold → return {"error": "no_slots"}
3. idempotence_key = uuid4()
4. payment = await asyncio.to_thread(Payment.create, {...}, idempotence_key)
   ↑ ОБЯЗАТЕЛЬНО asyncio.to_thread! SDK синхронный.
5. INSERT INTO payments (user_id, yookassa_payment_id, amount, status='pending')
6. return {"url": confirmation_url, "payment_id": payment.id}
```

---

## 3. HANDLERS/PAYMENT.PY

### Обработка кнопки "Оплатить"
```
Пользователь нажимает [💳 Оплатить]:
  1. try_hold_slot() → True/False
  2. if True:
       create_payment() → URL
       Показать: [💳 Перейти к оплате (URL)] [✅ Я оплатил]
  3. if False:
       "К сожалению, места закончились"
```

### Обработка кнопки "Пропустить"
```
Пользователь нажимает [❌ Пропустить]:
  1. release_hold(redis_conn, user_id) → слот возвращается
  2. Показать FINAL экран
```

### Обработка кнопки "Я оплатил"
```
Пользователь нажимает [✅ Я оплатил]:
  Проверяем payments.status для user_id:
  - 'succeeded' → "Оплата подтверждена!"
  - иначе → "Платёж ещё не подтверждён. Подождите 1-2 минуты."
```

---

## 4. HANDLERS/PAYMENT_WEBHOOK.PY

### Endpoint
```python
async def yookassa_webhook_handler(request: web.Request):
    """POST /yookassa/webhook — обработка событий от YooKassa"""
```

Регистрируется в bot.py:
```python
app.router.add_post("/yookassa/webhook", yookassa_webhook_handler)
```

### PAYMENT_SUCCEEDED
```
1. user_id = payment.metadata["user_id"]
2. UPDATE payments SET status='succeeded', paid_at=NOW()
   WHERE yookassa_payment_id=$1 AND status != 'succeeded'
   RETURNING id
3. if result is None → повторный webhook → return 200
4. release_hold(redis_conn, user_id)
5. ZOMBIE CHECK:
   paid_count = SELECT COUNT(*) FROM payments WHERE status='succeeded'
   if paid_count > total_slots:
     asyncio.to_thread(Refund.create, {...})
     UPDATE payments SET status='refunded'
     Уведомить пользователя: "Деньги возвращены"
     Уведомить админов: "CRITICAL: auto-refund"
     return 200
6. Уведомить пользователя: "Оплата прошла!"
7. Уведомить админов: "Новая оплата"
8. log_event(pool, user_id, "payment_succeeded", {amount: 5000})
```

### PAYMENT_CANCELED
```
1. user_id = payment.metadata["user_id"]
2. UPDATE payments SET status='canceled' WHERE yookassa_payment_id=$1 AND status='pending'
3. release_hold(redis_conn, user_id)
```

---

## 5. КАУНТЕР МЕСТ — ФОРМУЛА

```
Мест доступно = TOTAL_SLOTS 
                - COUNT(payments WHERE status='succeeded' AND offer_type='business_review')
                - ZCARD(upsell:holds) после ZREMRANGEBYSCORE(expired)
```

### Почему Sorted Set, а не отдельные ключи
| Подход | Подсчёт | Cleanup | Блокировка |
|--------|---------|---------|------------|
| hold:{user_id} + redis.keys() | O(N) БЛОКИРУЕТ | Ручной cleanup | Весь Redis |
| Sorted Set + ZCARD | O(1) | ZREMRANGEBYSCORE = O(log N) | Нет |

---

## 6. ТЕСТИРОВАНИЕ YOOKASSA

### Тестовый режим
- YOOKASSA_SECRET_KEY с префиксом `test_`
- Тестовые карты:
  - `4111 1111 1111 1111` — успешная оплата
  - `4100 0000 0000 0015` — отклонение
  - `5555 5555 5555 4444` — 3D Secure

### Webhook в тестовом режиме
YooKassa шлёт webhook на URL, указанный в настройках магазина.
Для тестирования на VDS: настроить webhook URL в личном кабинете YooKassa → `https://bot.neurounit.fun/yookassa/webhook`

---

## 7. УЛУЧШЕНИЯ ЭТОГО ЭТАПА

### 7.1 Технологические
- **Lua-скрипты** — атомарные операции, нет race conditions при 4 воркерах
- **Sorted Set** — O(1) подсчёт holds, O(log N) cleanup (вместо O(N) keys)
- **asyncio.to_thread** — синхронный SDK не блокирует event loop
- **Идемпотентность** — повторный webhook не создаёт дубль
- **Auto-refund** — zombie-платежи обрабатываются автоматически

### 7.2 Функциональные
- **Hold 15 минут** — бронь не вечная, освобождается автоматически
- **Каунтер в реальном времени** — "Осталось 3/10 мест" (реальные данные, не захардкоженные)
- **get_config()** — цену и количество слотов можно менять через SQL UPDATE без передеплоя
- **Единая функция upsell** — вызывается из любой точки входа

### 7.3 Для вовлечённости
- **Динамический каунтер** — "Осталось 2/10 мест" (FOMO — fear of missing out)
- **Таймер 15 минут** — "Бронь действует 15 минут!" (urgency)
- **Социальное доказательство** — "7 участников уже забронировали разбор" (подсчёт из payments)
- **Сообщение после оплаты** — "Спасибо! Менеджер свяжется в течение 24 часов" (подтверждение ценности)
- **Уведомление при исчерпании** — пользователям, которые не оплатили, можно отправить "Места закончились" (cleanup_promo_messages из текущего promo.py)

---

## 8. ЧЕК-ЛИСТ ЭТАПА

- [ ] Создан services/payment_service.py (Lua-скрипты, hold, create_payment)
- [ ] Lua: HOLD_SLOT_LUA (атомарная проверка + бронь)
- [ ] Lua: CHECK_LIMIT_LUA (подсчёт holds)
- [ ] get_remaining_slots() → paid (PG) + held (Redis Sorted Set)
- [ ] try_hold_slot() → атомарный Lua
- [ ] release_hold() → ZREM
- [ ] create_payment() → asyncio.to_thread(Payment.create)
- [ ] Создан handlers/payment.py (кнопки: Оплатить, Пропустить, Я оплатил)
- [ ] Создан handlers/payment_webhook.py (PAYMENT_SUCCEEDED, PAYMENT_CANCELED)
- [ ] Идемпотентность webhook: WHERE status != 'succeeded' RETURNING id
- [ ] Zombie-protection: auto-refund если paid_count > total_slots
- [ ] YooKassa webhook endpoint зарегистрирован в bot.py
- [ ] NGINX whitelist IP YooKassa в location /yookassa/
- [ ] Events: payment_created, payment_succeeded, payment_canceled
- [ ] Тест: полный цикл оплаты в тестовом режиме YooKassa
- [ ] Тест: hold слота → 15 мин → слот освобождается
- [ ] Тест: два параллельных пользователя → только один получает последний слот

---

## 9. ЗАВИСИМОСТИ

- **Зависит от Этапов 1-2:** PostgreSQL, Redis, asyncpg pool, config
- **Зависит от Этапа 5:** upsell.py вызывает payment_service
- **Этап 7 зависит:** дожим → воркшоп → upsell → оплата
- **Этап 8 зависит:** админские команды /slots показывают remaining_slots

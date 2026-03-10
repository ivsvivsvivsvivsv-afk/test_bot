# ЭТАП 8: Админ-панель, аналитика, деплой и боевой запуск

## САММАРИ

**Цель:** Реализовать админские инструменты, систему аналитики, провести финальный деплой на VDS и подготовить бота к боевому запуску с трафиком из TikTok.

**Что делаем:**
- `handlers/admin.py` — команды: /stats, /slots, /reset_user, /reset_all, /broadcast, /export_leads
- Аналитика: таблица events, конверсии воронки, когортный анализ
- Финальный деплой: NGINX, systemd, SSL, проверка всех компонентов
- Нагрузочное тестирование (locust, 1000 параллельных пользователей)
- Мониторинг: journalctl, Redis INFO, PostgreSQL pg_stat_activity
- Боевой чек-лист: переключение YooKassa на LIVE, /reset_all, запуск трафика

**Политика уведомлений (антиспам):**
- ❌ **НЕ** уведомлять о каждом новом пользователе (notify_new_user) — при нагрузке админ утонет в сообщениях.
- ✅ Уведомлять **только о лидах** и **оплатах**:
  - `notify_new_contact` — лид из квеста (оставил телефон)
  - `notify_arena_lead` — лид с арены
  - `notify_payment_success` / `notify_auto_refund` — оплаты
- Всё остальное (квест пройден, новый пользователь) — только в статистику, без push.

**Политика аналитики в админке:**
- Внешняя аналитика (без участия сервера) уже считает: каждый шаг воронки + соцдем портрет.
- В админ-панели показываем **только лиды и статусы оплат** — достаточно для оперативного контроля.
- Таблица `events` и внутренняя аналитика **остаются** — для сравнения внутренней и внешней аналитики.

**Критические правила:**
1. admin_only фильтр — все команды только для ADMIN_IDS
2. /reset_user и /reset_all — контакты и платежи НЕ трогаем
3. FSM очистка через scan_iter (не scan(0), не keys())
4. /broadcast — asyncio.sleep(0.05) + TelegramRetryAfter + TelegramForbiddenError
5. Рядовой пользователь НЕ МОЖЕТ сбросить прогресс (нет /reset)

---

## 1. HANDLERS/ADMIN.PY

### Список команд

| Команда | Описание | Подробности |
|---------|----------|-------------|
| `/stats` | Статистика воронки | Общие, квест, воркшоп, арена, платежи, конверсии |
| `/slots` | Места на upsell | paid + held = occupied, remaining |
| `/reset_user <ID>` | Сброс прогресса пользователя | Контакты и платежи сохраняются! |
| `/reset_all` | Сброс прогресса ВСЕХ | Перед запуском нового трафика |
| `/broadcast <текст>` | Рассылка | Rate limited, TelegramRetryAfter |
| `/export_leads` | Экспорт лидов в CSV | user_id, username, phone, email, class, weapon, score |

### /stats — Лиды и оплаты (фокус админки)
> Полная воронка и соцдем — во внешней аналитике. Здесь только оперативный контроль.

```
📊 ЛИДЫ И ОПЛАТЫ

📱 Лиды (телефон/email):
   Квест: 456
   Арена: 89
   Всего: 545

💳 Оплаты:
   Успешно: 7
   В ожидании: 3
   Отменено: 12
   Возвращено: 1

💰 Выручка: 35 000 ₽
🪑 Мест на разбор: 3/10
```

### /reset_user <ID> — Сброс прогресса
```sql
-- Поля, которые СБРАСЫВАЮТСЯ:
UPDATE users SET
    quest_state = 'start',
    quest_completed = FALSE,
    player_class = NULL,
    weapon = NULL,
    score = 0,
    round_number = 0,
    current_statement_hash = NULL,
    current_is_truth = NULL,
    followup_stage = 0,
    followup_completed = FALSE,
    upsell_shown = FALSE
WHERE user_id = $1

-- Поля, которые НИКОГДА НЕ СБРАСЫВАЮТСЯ:
-- user_id, username, first_name, phone, email,
-- workshop_registered, arena_registered, is_blocked,
-- created_at, utm_source, referrer
```

```python
# FSM очистка
async for key in redis_conn.scan_iter(match=f"fsm:{user_id}:*", count=50):
    await redis_conn.delete(key)
```

### /reset_all — Сброс всех
Тот же SQL, но `WHERE quest_completed = TRUE OR quest_state != 'start'`.
FSM: `scan_iter(match="fsm:*", count=500)` — итерирует ВСЕ батчи.

### /broadcast — Рассылка
```python
@router.message(Command("broadcast"), admin_only)
async def cmd_broadcast(message: Message, pool, redis_conn):
    text = message.text.replace("/broadcast ", "", 1)
    if not text or text == "/broadcast":
        return await message.answer("Использование: /broadcast <текст>")
    
    result = await broadcast(bot=message.bot, pool=pool, text=text)
    await message.answer(f"✅ Отправлено: {result['sent']}, ошибок: {result['failed']}")
```

### /export_leads — Экспорт CSV
```python
@router.message(Command("export_leads"), admin_only)
async def cmd_export(message: Message, pool):
    rows = await pool.fetch("""
        SELECT user_id, username, first_name, phone, email,
               player_class, weapon, score, quest_completed, workshop_registered,
               created_at
        FROM users WHERE phone IS NOT NULL OR email IS NOT NULL
        ORDER BY created_at DESC
    """)
    
    # Формируем CSV
    csv_content = "user_id,username,first_name,phone,email,class,weapon,score,quest,workshop,created\n"
    for row in rows:
        csv_content += ",".join(str(row[col] or '') for col in row.keys()) + "\n"
    
    # Отправляем файлом
    from aiogram.types import BufferedInputFile
    file = BufferedInputFile(csv_content.encode('utf-8'), filename="leads.csv")
    await message.answer_document(file, caption=f"📊 Экспорт: {len(rows)} лидов")
```

---

## 2. АНАЛИТИКА (ТАБЛИЦА EVENTS)

> **Важно:** Внешняя аналитика (в боте без участия сервера) уже считает шаги воронки и соцдем.
> Таблица `events` и запись событий **остаются** для сравнения внутренней и внешней аналитики.
> В админке /stats показываем только лиды и статусы оплат.

### Схема
```sql
CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Все события
| Событие | Момент | Данные |
|---------|--------|--------|
| bot_start | /start | {utm_source} |
| quest_start | Нажал "Квест" | — |
| class_selected | Выбрал класс | {class: "businessman"} |
| weapon_selected | Выбрал оружие | {weapon: "marketing"} |
| round_completed | Ответил на раунд | {round: 1, correct: true, score: 1} |
| quest_completed | Завершил квест | {score: 2} |
| contact_phone | Ввёл телефон | — |
| workshop_registered | Записался на воркшоп | — |
| upsell_shown | Показали оффер | {remaining_slots: 7} |
| payment_created | Создал платёж | {payment_id: "..."} |
| payment_succeeded | Оплатил | {amount: 5000} |
| payment_canceled | Отменил | — |
| followup_idle_sent | Напоминание "завис" | {state: "round_2"} |
| followup_miniquest_sent | Миниквест | {day: 3} |
| followup_miniquest_answered | Ответ на миниквест | {day: 3, correct: true} |
| arena_start | Нажал "Арена" | — |
| arena_registered | Завершил арену | — |

### SQL-запросы для аналитики

**Воронка:**
```sql
SELECT
    COUNT(*) FILTER (WHERE event_type = 'bot_start') as starts,
    COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'quest_start') as quest_started,
    COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'quest_completed') as quest_completed,
    COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'workshop_registered') as workshop,
    COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'payment_succeeded') as paid
FROM events
WHERE created_at >= NOW() - INTERVAL '7 days';
```

**Конверсия по utm_source:**
```sql
SELECT
    e1.event_data->>'utm_source' as source,
    COUNT(DISTINCT e1.user_id) as starts,
    COUNT(DISTINCT e2.user_id) as completed
FROM events e1
LEFT JOIN events e2 ON e1.user_id = e2.user_id AND e2.event_type = 'quest_completed'
WHERE e1.event_type = 'bot_start'
GROUP BY source;
```

---

## 3. ФИНАЛЬНЫЙ ДЕПЛОЙ

### 3.1 Последовательность
```
1. git push → /opt/hydra_bot (git pull или rsync)
2. source venv/bin/activate && pip install -r requirements.txt
3. psql -U hydra hydra_bot < schema.sql (если первый деплой)
4. cp .env.example .env && nano .env (заполнить секреты)
5. cp deploy/nginx.conf /etc/nginx/sites-available/hydra-bot
6. ln -s /etc/nginx/sites-available/hydra-bot /etc/nginx/sites-enabled/
7. nginx -t && systemctl reload nginx
8. cp deploy/hydra-bot.service /etc/systemd/system/
9. cp deploy/hydra-worker.service /etc/systemd/system/
10. systemctl daemon-reload
11. systemctl enable hydra-bot hydra-worker
12. systemctl start hydra-bot
13. systemctl start hydra-worker
14. Проверка: systemctl status hydra-bot hydra-worker
```

### 3.2 Проверка каждого компонента
```bash
# PostgreSQL
psql -U hydra hydra_bot -c "SELECT COUNT(*) FROM users;"

# Redis
redis-cli ping  # PONG
redis-cli INFO memory  # used_memory < 256MB

# NGINX
curl -I https://bot.neurounit.fun/  # 444
curl -I https://bot.neurounit.fun/webhook/test  # 403 (не с IP Telegram)

# Бот
systemctl status hydra-bot  # active (running)
journalctl -u hydra-bot -n 20  # "Worker started successfully"

# Worker
systemctl status hydra-worker  # active (running)
journalctl -u hydra-worker -n 20  # "Worker started: scheduler running"
```

### 3.3 Тест webhook
```bash
# Проверяем что webhook установлен
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
# Ожидаем: url = "https://bot.neurounit.fun/webhook/bot", pending_update_count = 0
```

---

## 4. НАГРУЗОЧНОЕ ТЕСТИРОВАНИЕ

### locust скрипт
```python
# tests/loadtest.py
from locust import HttpUser, task, between

class TelegramWebhookUser(HttpUser):
    wait_time = between(0.1, 0.5)
    
    @task
    def send_start(self):
        self.client.post("/webhook/bot", json={
            "update_id": random.randint(1, 999999),
            "message": {
                "message_id": random.randint(1, 999999),
                "from": {"id": random.randint(100000, 999999), "first_name": "Test"},
                "chat": {"id": random.randint(100000, 999999), "type": "private"},
                "text": "/start"
            }
        }, headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET})
```

### Запуск
```bash
pip install locust
locust -f tests/loadtest.py --headless -u 1000 -r 100 --run-time 5m -H https://bot.neurounit.fun
```

### Целевые метрики
| Метрика | Цель | Критично |
|---------|------|----------|
| RPS | >500 | <100 |
| Latency p50 | <100ms | >500ms |
| Latency p99 | <500ms | >2s |
| Error rate | <1% | >5% |
| PG connections | <40 | >80 |
| Redis memory | <128MB | >256MB |

---

## 5. МОНИТОРИНГ В PRODUCTION

### Логи
```bash
# Бот (Gunicorn)
journalctl -u hydra-bot -f

# Worker (Scheduler)
journalctl -u hydra-worker -f

# NGINX
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### PostgreSQL
```sql
-- Активные подключения
SELECT count(*) FROM pg_stat_activity WHERE datname = 'hydra_bot';
-- Цель: <40 (4 воркера × 10 + worker 5)

-- Размер таблиц
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC;

-- Медленные запросы
SELECT query, calls, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;
```

### Redis
```bash
redis-cli INFO memory     # used_memory
redis-cli INFO keyspace   # количество ключей
redis-cli DBSIZE          # общее количество
```

### Health-check endpoint (опционально)
```python
# В bot.py
async def health_check(request):
    # Проверяем PG и Redis
    try:
        await app['pool'].fetchval("SELECT 1")
        await app['redis'].ping()
        return web.Response(text="OK", status=200)
    except:
        return web.Response(text="UNHEALTHY", status=503)

app.router.add_get("/health", health_check)
```

---

## 6. БОЕВОЙ ЧЕК-ЛИСТ ЗАПУСКА

### Перед запуском трафика
- [ ] YooKassa переключена на LIVE-ключ (префикс `live_`, не `test_`)
- [ ] Webhook YooKassa настроен: `https://bot.neurounit.fun/yookassa/webhook`
- [ ] FOLLOWUP_IDLE_MINUTES=5 (не 1, как при тестировании)
- [ ] `/reset_all` выполнен (чистый старт)
- [ ] SSL-сертификат валиден (certbot renew --dry-run)
- [ ] Все systemd-сервисы active: hydra-bot, hydra-worker
- [ ] NGINX reload после финальных правок
- [ ] Нагрузочный тест пройден (1000 юзеров, <500ms p99)

### Во время трафика (мониторинг первых 30 минут)
- [ ] `journalctl -u hydra-bot -f` — нет ошибок
- [ ] `journalctl -u hydra-worker -f` — scheduler работает
- [ ] `/stats` в боте — пользователи появляются
- [ ] `/slots` — каунтер мест корректный
- [ ] Пройти квест самому от начала до конца
- [ ] PostgreSQL: connections <40
- [ ] Redis: memory <128MB

### После первой волны (через 24 часа)
- [ ] Проверить: миниквесты отправляются в 11:00 (journalctl)
- [ ] `/export_leads` — лиды экспортируются
- [ ] Конверсии адекватные (/stats)
- [ ] Нет жалоб на "не работает" в чатах

---

## 7. УЛУЧШЕНИЯ ЭТОГО ЭТАПА

### 7.1 Технологические
- **scan_iter** вместо scan(0) — полная очистка FSM при /reset_all
- **BufferedInputFile** для CSV — не создаёт файл на диске
- **Health-check endpoint** — для мониторинга uptime
- **pg_stat_statements** — отслеживание медленных запросов

### 7.2 Функциональные
- **Полная статистика** — конверсии, воронка, когорты, utm-источники
- **CSV экспорт** — менеджеры могут работать с лидами в Excel/Google Sheets
- **/broadcast** — мгновенная рассылка для важных объявлений
- **Events** — все действия записываются, можно анализировать постфактум

### 7.3 Для вовлечённости
- **Когортный анализ** — видим, какой день лучше для запуска трафика
- **UTM tracking** — видим, какой TikTok-ролик приводит лучших лидов
- **Конверсии** — видим bottleneck (например, "70% отваливается на раунде 2" → нужно упростить)
- **Быстрая реакция** — /stats в реальном времени, не ждём отчёта

---

## 8. БУДУЩИЕ МОДУЛИ (POST-MVP)

| Модуль | Описание | Когда |
|--------|----------|-------|
| Google Sheets | Авто-экспорт лидов | Когда команда продаж |
| Graspil / GA4 | Детальная аналитика | При платном трафике |
| Реферальная система | "Приведи друга" | После валидации воронки |
| A/B тестирование | Разные тексты/офферы | При оптимизации |
| Мультиязычность | EN/TR | При выходе из РФ |
| Химера Хаоса | Бонусный квест | Для реактивации |
| Telegram Mini App | Визуальный интерфейс | v2.0 |
| Grafana Dashboard | Визуализация метрик | При масштабировании |

---

## 9. ЧЕК-ЛИСТ ЭТАПА

- [ ] Создан handlers/admin.py (/stats, /slots, /reset_user, /reset_all, /broadcast, /export_leads)
- [ ] notify_new_user и notify_quest_completed УДАЛЕНЫ (уведомления только лиды + оплаты)
- [ ] admin_only фильтр для всех команд
- [ ] /reset_user: контакты и платежи НЕ трогаем
- [ ] /reset_all: scan_iter для FSM (не scan(0))
- [ ] /broadcast: asyncio.sleep(0.05) + TelegramRetryAfter
- [ ] /export_leads: CSV через BufferedInputFile
- [ ] Events записываются во всех handlers (Этапы 3-7)
- [ ] /stats показывает конверсии воронки
- [ ] Финальный деплой на VDS выполнен
- [ ] NGINX настроен (whitelist IP Telegram + YooKassa)
- [ ] systemd сервисы работают (hydra-bot + hydra-worker)
- [ ] SSL валиден
- [ ] Нагрузочный тест пройден (1000 юзеров)
- [ ] YooKassa → LIVE ключ
- [ ] /reset_all перед запуском трафика
- [ ] Полный проход квеста на production
- [ ] Мониторинг: PG connections <40, Redis <128MB, no errors in journalctl

---

## 10. ЗАВИСИМОСТИ

- **Зависит от ВСЕХ предыдущих этапов:** это финальный этап интеграции
- **Блокирует:** запуск трафика из TikTok (только после полной проверки)

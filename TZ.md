# 🐉 НЕЙРО-ЮНИТ: КВЕСТ «ГИДРА СИНГУЛЯРНОСТИ»
## Техническое Задание v7.7 — PRODUCTION MVP (Telegram-First Contacts)

---

# 📌 МЕТА-ИНФОРМАЦИЯ

| Параметр | Значение |
|----------|----------|
| **Версия** | 7.7 (Production MVP — Telegram-First Contacts) |
| **Дата** | 04 марта 2026 |
| **Среда разработки** | Cursor AI |
| **Сервер** | FirstVDS — bot.neurounit.fun (82.146.39.44), Ubuntu 24.04 |
| **Целевая нагрузка** | 1 000–10 000 параллельных пользователей |
| **Режим работы** | Webhook (не polling!) |
| **Цель бота** | Лидогенерация через игровой квест → регистрация на открытый воркшоп → upsell платного разбора бизнеса |
| **Источник трафика** | TikTok (волны 1000+ человек), Telegram-реклама |

---

# 🔺 ИЗМЕНЕНИЯ v7.0 → v7.1 (КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ)

| # | Уязвимость | Было | Стало |
|---|-----------|------|-------|
| 1 | **Race Condition YooKassa** | Место списывалось только по webhook оплаты → овербукинг при наплыве | Жёсткое резервирование (hold) слота в Redis на 15 мин ПЕРЕД генерацией ссылки |
| 2 | **NGINX блокирует Telegram** | `limit_req` по IP на webhook-эндпоинте | Белый список IP Telegram + убран rate limit для webhook |
| 3 | **Single-process + дублирование Scheduler** | Один процесс python, APScheduler внутри | Gunicorn с 4-8 воркерами + APScheduler вынесен в отдельный `worker.py` |
| 4 | **Бан Telegram за рассылку** | Цикл `for user in users: send_message()` без задержки | `asyncio.sleep(0.05)` + обработка `TelegramRetryAfter` |
| 5 | **Бесконечный спам заблокировавшим** | `UPDATE` в `try`, `except: pass` → помечка не происходит | `UPDATE` в `finally` → пользователь помечается ВСЕГДА |
| 6 | **MVCC Bloat PostgreSQL** | `UPDATE last_activity_at = NOW()` на каждый клик | Активность хранится в Redis с TTL, не в PostgreSQL |
| 7 | **Предсказуемый Webhook URL** | `/webhook/bot` без верификации | `secret_token` при установке webhook + проверка заголовка |
| 8 | **Upsell не работал после дожима** | Upsell только в основном потоке квеста | Upsell триггерится при ЛЮБОМ `workshop_registered = TRUE` |
| 9 | **Файл миграции вводил в заблуждение** | `migrations/001_initial.sql` (бота ещё нет) | `schema.sql` — скрипт создания БД с нуля |
| 10 | **Сброс прогресса** | Правило было, но неявно | Явный запрет: пользователь НЕ МОЖЕТ сбросить свой прогресс |

---

# ИЗМЕНЕНИЯ v7.2 -> v7.3 (DOCUMENT INTEGRITY FIX)

| # | Уязвимость | Было | Стало |
|---|-----------|------|-------|
| 1 | **get_config() не существовала** | Вызов функции-призрака → NameError при оплате | `utils/config_db.py` с `get_config(pool, key, default)` |
| 2 | **scan(0) получал один батч** | `redis.scan(0)` в admin.py → неполная очистка FSM | `scan_iter()` с автоитерацией всех батчей |
| 3 | **redis не инжектировался в admin.py** | Голый `redis` без передачи в хендлер | `redis_conn` как параметр хендлера через middleware |
| 4 | **get_remaining_slots(pool) без redis** | Вызов в /stats без redis_conn → TypeError | `get_remaining_slots(pool, redis_conn)` |
| 5 | **delete_webhook в on_shutdown** | Один воркер при reload убивал webhook для всех | Только `bot.session.close()`, без delete_webhook |
| 6 | **Дублированный лог в bot.py** | `"Webhook set"` дважды (строки 1466/1485) | Второй заменён на `"Worker started successfully"` |
| 7 | **Хардкод текстов в .py** | Строки вроде `"✅ Оплата прошла!..."` в коде | `ContentManager` → `content/texts.json` |
| 8 | **FSInputFile в цикле рассылок** | `send_photo(FSInputFile(...))` × 5000 юзеров | `media_service.py`: file_id кэш в Redis |
| 9 | **Промпт без правил контента** | 15 правил, нет про тексты/медиа | +4 правила (16-19): контент, медиа, scan_iter, on_shutdown |

---

# ИЗМЕНЕНИЯ v7.3 -> v7.4 (КОНТАКТЫ: TELEGRAM-FIRST)

| # | Изменение | Было | Стало |
|---|-----------|------|-------|
| 1 | **Сбор контактов** | Телефон + email, кнопки "Пропустить" | Телефон обязателен, @username авто, email не собираем |
| 2 | **FSM контактов** | waiting_phone → waiting_email → confirming | waiting_phone → confirming |
| 3 | **Арена** | ARENA_PHONE → ARENA_EMAIL → ARENA_DONE | ARENA_PHONE → ARENA_DONE |
| 4 | **События аналитики** | contact_phone, contact_email | Только contact_phone |
| 5 | **Кнопки подтверждения** | Подтвердить, Изменить телефон, Изменить email | Подтвердить, Изменить телефон |

---

# ИЗМЕНЕНИЯ v7.4 -> v7.5 (АКТУАЛИЗАЦИЯ КОНТЕНТА КВЕСТА)

| # | Изменение | Было | Стало |
|---|-----------|------|-------|
| 1 | **Тональность шага подготовки** | "кто ты в мире бизнеса" | "кто ты в этом мире" + фокус на универсальность для жизни, творчества и работы |
| 2 | **Инструкция fact-check** | Короткий совет про Perplexity | Пошаговая инструкция: сайт → регистрация → deep research → проверка утверждения |
| 3 | **Ценность 3 раундов** | Только "отличить правду от лжи" | Добавлена цель: пройти раунды для приглашения на открытый воркшоп |
| 4 | **Текст выбора класса** | Узкая формулировка под бизнес | Формулировка "в этом технологичном мире" без сужения аудитории |
| 5 | **Финальные результаты (`result_*`)** | HTML-теги внутри вставляемого блока (`<b>`) | Убраны inline HTML-теги, чтобы избежать отображения `&lt;b&gt;...` в финальном экране |
| 6 | **Блок морали** | Короткий общий текст | Расширенный value-блок: автоматизация проверки фактов, ИИ-педагог, видео/аудио-генерация |
| 7 | **Процесс ведения ТЗ** | Неявная фиксация контент-правок | Любая правка пользовательского текста воронки обязательно вносится в `TZ.md` в раздел изменений версии |

---

# ИЗМЕНЕНИЯ v7.5 -> v7.6 (ОРУЖИЯ И ВИЗУАЛ ШАГОВ)

| # | Изменение | Было | Стало |
|---|-----------|------|-------|
| 1 | **Названия оружий** | Меч/Линза/Кисть/Скрижаль и т.п. | Новые названия под визуальный стиль: Мегафон Маркетолога, Глаз Аналитика, Перо Копирайтера, Планшет Дизайнера, Рука Координатора, Камера Видеомейкера |
| 2 | **Картинка шага 2 (`quest_intro`)** | Использовалась стартовая картинка `img_start` | Добавлена отдельная картинка `img_prepare` (photo_2026-03-06_17-27-59) |
| 3 | **Картинка победы** | Старая `img_win` | Обновлена `img_win` на новую победную картинку (photo_2026-03-06_17-28-02) |
| 4 | **Единый source of truth по оружиям** | Частичное расхождение между `keyboards` и `texts.json` | Синхронизированы названия в `keyboards/inline.py` и `content/texts.json` |

---

# ИЗМЕНЕНИЯ v7.6 -> v7.7 (РЕВИЗИЯ ДОКУМЕНТАЦИИ)

| # | Изменение | Было | Стало |
|---|-----------|------|-------|
| 1 | **Production-реквизиты в docs** | Часть документов указывала старый домен/IP | Синхронизировано на `bot.neurounit.fun` и `82.146.39.44` |
| 2 | **README.md** | Устаревший деплой через Amvera и устаревшая структура | Полностью обновлен под текущий VDS/webhook/systemd стек |
| 3 | **Миниквест-медиа в docs** | Привязка к `content/media/*.jpg` в части описаний | Зафиксирована актуальная схема: `file_id` через `utils/media_ids.py` |
| 4 | **Версионная целостность** | Отдельные секции с устаревшими версиями правил | Унифицировано на актуальную ревизию `v7.7` |
| 5 | **Роль `plan/`** | Неявный статус этапных документов | Явно отмечено как архив этапов; source of truth — `TZ.md` |

---

# PATCH 2 (РАССЫЛКИ, УВЕДОМЛЕНИЯ, АДМИНКА, СТАТИСТИКА)

**Отдельный документ:** `plan/PATCH_2_BROADCASTS_NOTIFICATIONS_ADMIN_STATS.md`

**Единая админка:** `neurounit.fun/admin` — лендинг + бот в одном месте. Спецификация: `plan/UNIFIED_ADMIN_SPEC.md`. **Для лендинга:** `plan/REQUIREMENTS_FOR_LANDING.md`

Включает:

- **Единая админка** neurounit.fun/admin (лендинг рендерит UI, бот отдаёт данные по API)
- Массовые рассылки с сегментацией (запуск из админки)
- Автоуведомления пользователям (курс, урок)
- Уведомления админам (user_stuck, bot_down)
- Объединённые лиды (лендинг + бот), CRM-слой
- Graspil + статистика по шагам воронки
- Интеграция с сайтом (оплата → уведомление в Telegram)
- Бекап перед обновлением (chattr +i), откат
- Миграции: `migrations/patch2_001.sql`
- Скрипты: `deploy/backup.sh`, `deploy/rollback.sh`, `deploy/unlock_backups.sh`

---

# ИЗМЕНЕНИЯ v7.1 -> v7.2 (PRODUCTION-HARDENING)

| # | Уязвимость | Было | Стало |
|---|-----------|------|-------|
| 1 | **KEYS блокирует Redis** | `redis.keys()` O(N) | Lua + Sorted Set |
| 2 | **Синхронный SDK** | `YKPayment.create()` блокирует loop | `asyncio.to_thread()` |
| 3 | **Check-Then-Act Race** | Два шага | Атомарный Lua-скрипт |
| 4 | **SETNX+EXPIRE** | Два вызова | `SET EX NX` внутри Lua |
| 5 | **Зомби-платежи** | Webhook без проверки | auto-refund если 10/10 |
| 6 | **N+1 Redis** | `exists()` в цикле | `MGET` |
| 7 | **set_webhook spam** | 4 воркера | `get_webhook_info()` |
| 8 | **DB_POOL_MAX** | 20x4=80 | 10x4=40 |

---


# ⚠️ КРИТИЧЕСКИЕ АРХИТЕКТУРНЫЕ ОГРАНИЧЕНИЯ

> **Эти правила ОБЯЗАТЕЛЬНЫ для любого разработчика (человека или ИИ-агента).
> Нарушение любого из них приведёт к падению бота под реальной нагрузкой.**

1. **НИКОГДА не писать `last_activity` в PostgreSQL при каждом действии пользователя.** Только Redis с TTL.
2. **НИКОГДА не выдавать ссылку на оплату без предварительного HOLD слота в Redis.**
3. **НИКОГДА не слать рассылки без `asyncio.sleep()` между сообщениями.** Лимит Telegram: 30 msg/sec. Безопасный предел: 20 msg/sec.
4. **НИКОГДА не ставить rate limit NGINX на webhook-эндпоинт.** Telegram шлёт запросы с ограниченного пула IP.
5. **НИКОГДА не запускать APScheduler внутри воркера Gunicorn.** Только отдельный процесс.
6. **НИКОГДА не игнорировать `TelegramForbiddenError` без пометки пользователя как "заблокировал бота".**
7. **НИКОГДА не удалять данные пользователя (контакты, платежи) при сбросе прогресса.**
8. **Рядовой пользователь НЕ МОЖЕТ сбросить свой прогресс.** Сброс — только через админские команды.
9. **НИКОГДА не использовать `redis.keys()`.** O(N), блокирует Redis.
10. **НИКОГДА не вызывать синхронный SDK напрямую.** Только `asyncio.to_thread()`.
11. **НИКОГДА не делать Check-Then-Act двумя командами Redis.** Только Lua.
12. **НИКОГДА не вызывать `redis.exists()`/`get()` в цикле.** Только `MGET`.
13. **DB_POOL_MAX = 10 на воркер** (4x10=40 < PG default 100).
14. **НИКОГДА не хардкодить тексты бота в `.py` файлах.** Только `ContentManager` → `content/texts.json`.
15. **НИКОГДА не использовать `FSInputFile` в циклах рассылок.** Только `media_service.py` → file_id кэш в Redis.
16. **НИКОГДА не использовать `redis.scan(0)` одним вызовом.** Только `scan_iter()` (итерирует все батчи).
17. **НИКОГДА не вызывать `bot.delete_webhook()` в `on_shutdown`.** Graceful reload воркера убьёт webhook для всех.
18. **МЕДИА: все картинки хранятся в Telegram.** Используются только `file_id` из `utils/media_ids.py`. Папка `content/media/` и файлы на диске НЕ нужны для основной воронки. Никакая графика не загружается с сервера.
19. **API админки и webhook сайта:** проверка секрета через `hmac.compare_digest()`, rate limit, секреты только в .env.

---

# 🔒 БЕЗОПАСНОСТЬ API (Patch 2)

## Эндпоинты и защита

| Эндпоинт | Защита | NGINX |
|----------|--------|-------|
| `/webhook/*` (Telegram) | IP whitelist + `secret_token` | `allow` Telegram IP, `deny all` |
| `/yookassa/*` | IP whitelist | `allow` YooKassa IP, `deny all` |
| `/api/admin/*` | `X-Admin-Secret` + rate limit | Отдельный `location`, без IP whitelist (лендинг на другом IP) |
| `/api/webhook/site` | `X-Site-Secret` + rate limit | Отдельный `location` |
| `/api/landing/*` (notify-winner) | `X-Bot-Api-Secret` или аналог | По контракту `BOT_API_CONTRACT.md` |

## Правила реализации

1. **Сравнение секретов:** только `hmac.compare_digest(provided, expected)` — защита от timing attack.
2. **Секреты:** минимум 32 байта, случайная генерация (`openssl rand -hex 32`). Хранить только в .env.
3. **Rate limit:** `/api/admin/*` — 60 req/min с IP; `/api/webhook/site` — 30 req/min.
4. **Вызовы к боту:** только с бэкенда лендинга (Flask), никогда из браузера — секрет не попадает в клиент.
5. **YooKassa webhook:** при возможности — проверка подписи HMAC (см. документацию YooKassa).

---

# 🎯 БИЗНЕС-ЛОГИКА (Source of Truth)

## Воронка бота

```
TikTok / Реклама
       │
       ▼
   /start в боте
       │
       ├─── [🎮 Квест] ──► Класс → Оружие → 3 раунда → Результат → Мораль
       │                                                                │
       │                                                    ┌───────────┤
       │                                                    ▼           ▼
       │                                              РЕГИСТРАЦИЯ   НЕ ЗАПИСАЛСЯ
       │                                              на воркшоп    (дожим 5 дней)
       │                                                    │
       │                                                    ▼
       │                                              UPSELL: Разбор
       │                                              бизнеса 5000₽
       │                                              (10 мест, каунтер)
       │                                                    │
       │                                                    ▼
       │                                              YooKassa оплата
       │
       ├─── [🎬 Генератор] ──► Редирект на другого бота
       │
       └─── [⚔️ Арена] ──► Сбор контактов → Предложить квест
```

## Ключевые бизнес-правила

1. **Квест проходится ОДИН РАЗ.** После завершения — экран "уже играл" с предложением записаться на воркшоп.
2. **Пользователь НЕ МОЖЕТ сбросить свой прогресс.** Нет команды `/reset`, нет кнопки "начать заново". Сброс — ТОЛЬКО через админские команды `/reset_user` и `/reset_all`.
3. **Контакты (телефон обязательно, @username автоматически) собираются ПОСЛЕ квеста,** перед финальным экраном. Email не собирается.
4. **Upsell "Разбор бизнеса"** показывается СРАЗУ после установки `workshop_registered = TRUE`, **НЕЗАВИСИМО от точки входа** (основной квест, дожим-миниквест, арена). Всего 10 мест. Когда места кончились — оффер не показывается.
5. **Дожим активируется** если пользователь: (а) завис на шаге >5 минут, (б) прошёл квест но не оставил контакты в течение 5 дней.
6. **Данные пользователей (контакты, платежи) НИКОГДА не удаляются** при сбросе прогресса.
7. **Место на upsell холдируется (бронируется) в Redis на 15 минут** перед генерацией ссылки на оплату. Ссылка выдаётся только если (оплаченные + забронированные) < 10.

---

# 🏗️ АРХИТЕКТУРА: Production MVP

## Обзор стека

```
┌─────────────────────────────────────────────────────────────────────┐
│                        СЕРВЕР FirstVDS                              │
│                  Ubuntu 24.04 / 82.146.39.44                      │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    NGINX (reverse proxy)                     │   │
│  │       SSL-терминация, whitelist IP Telegram + YooKassa       │   │
│  │       БЕЗ rate limit на webhook (Telegram сам шлёт!)        │   │
│  │       Webhook: /webhook/<secret_token>                      │   │
│  └──────────────┬──────────────────────────────┬────────────────┘   │
│                 │                               │                    │
│  ┌──────────────▼────────────────────────┐     │                    │
│  │  GUNICORN (4-8 воркеров)              │     │                    │
│  │  gunicorn bot:app --workers 4         │     │                    │
│  │  --worker-class aiohttp.GunicornWebWorker   │                    │
│  │                                       │     │                    │
│  │  PYTHON APP (bot.py) — ТОЛЬКО HANDLERS│     │                    │
│  │  aiogram 3.x (webhook mode)           │     │                    │
│  │  ├── handlers/     — Роутеры          │     │                    │
│  │  ├── middlewares/   — Throttle, logging│     │                    │
│  │  ├── services/      — Бизнес-логика   │     │                    │
│  │  ├── models/        — Pydantic        │     │                    │
│  │  └── utils/         — Валидация и т.д.│     │                    │
│  │                                       │     │                    │
│  │  ⚠️ БЕЗ APScheduler внутри!          │     │                    │
│  └──────┬───────────────────────┬────────┘     │                    │
│         │                       │               │                    │
│  ┌──────▼──────┐  ┌─────────────▼──────────┐   │                    │
│  │ PostgreSQL  │  │     Redis 7.x          │   │                    │
│  │   16.x      │  │                        │   │                    │
│  │             │  │  • FSM Storage          │   │                    │
│  │  • users    │  │  • Throttle counters    │   │                    │
│  │  • payments │  │  • Slot holds (TTL 15m) │   │                    │
│  │  • events   │  │  • User activity (TTL)  │   │                    │
│  │  • config   │  │  • Кэш утверждений     │   │                    │
│  │             │  │  • Distributed Locks    │   │                    │
│  │ asyncpg     │  │                        │   │                    │
│  │ pool: 20    │  │  redis[hiredis]        │   │                    │
│  └─────────────┘  └────────────────────────┘   │                    │
│                                                 │                    │
│  ┌──────────────────────────────────────────┐   │                    │
│  │  WORKER.PY (ОТДЕЛЬНЫЙ ПРОЦЕСС!)         │   │                    │
│  │  systemd: hydra-worker.service           │   │                    │
│  │  Запускается СТРОГО в 1 экземпляре       │   │                    │
│  │                                          │   │                    │
│  │  APScheduler (AsyncIOScheduler):         │   │                    │
│  │  • Дожим: idle-проверка через Redis      │   │                    │
│  │  • Миниквесты: 1 раз/день в 11:00 МСК   │   │                    │
│  │  • Очистка expired holds                 │   │                    │
│  │                                          │   │                    │
│  │  Рассылки:                               │   │                    │
│  │  • asyncio.sleep(0.05) между msg         │   │                    │
│  │  • Обработка TelegramRetryAfter          │   │                    │
│  │  • finally: пометка user в БД            │   │                    │
│  └──────────────────────────────────────────┘   │                    │
│                                                 │                    │
│  ┌──────────────────────────────────────────┐   │                    │
│  │  YooKassa Webhook Handler                │◄──┘                    │
│  │  POST /yookassa/webhook                  │                        │
│  │  (внутри Gunicorn app)                   │                        │
│  └──────────────────────────────────────────┘                        │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  SYSTEMD SERVICES                                            │    │
│  │  • hydra-bot.service    → Gunicorn (webhook handlers)        │    │
│  │  • hydra-worker.service → worker.py (scheduler, рассылки)    │    │
│  │  Оба с Restart=always + WatchdogSec=30                       │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

## Почему именно этот стек

| Компонент | Почему | Альтернатива (отклонена) |
|-----------|--------|--------------------------|
| **PostgreSQL** | ACID, connection pooling, JSON-поля, масштабирование, поддержка 10K+ одновременных пользователей | SQLite — single-writer, не для конкурентных нагрузок |
| **asyncpg** | Самая быстрая async-библиотека для PostgreSQL, connection pool из коробки | aiosqlite — привязка к SQLite |
| **Redis** | FSM-хранилище, rate limiting, distributed locks, кэширование утверждений, **slot holds для YooKassa**, **трекинг user activity (вместо PostgreSQL!)** | APScheduler jobstore в SQLite — одна точка отказа |
| **Webhook** | Мгновенная доставка, нет polling-задержки, экономия ресурсов при высоких нагрузках | Polling — задержки, лишние запросы к API Telegram |
| **NGINX** | SSL, **whitelist IP Telegram** (НЕ rate limit!), буферизация | `limit_req` на webhook — заблокирует серверы Telegram |
| **Gunicorn** | Запуск 4-8 воркеров (процессов), утилизация всех ядер CPU, graceful reload | Один процесс Python — упирается в одно ядро при 10K CCU |
| **Отдельный worker.py** | APScheduler запускается СТРОГО в 1 экземпляре. Если запустить внутри Gunicorn — каждый воркер создаст свой Scheduler → рассылки уйдут 4-8 раз | APScheduler внутри бота — дублирование задач |
| **YooKassa SDK** | Нативная интеграция, webhook-подтверждение платежей, возвраты | Ручные HTTP-запросы — ненадёжно |
| **Systemd** | 2 сервиса: бот (Gunicorn) + воркер (scheduler). Автоперезапуск, watchdog, journald | Docker — избыточен для MVP |

---

# 📁 СТРУКТУРА ПРОЕКТА

```
hydra_bot/
├── bot.py                          # Точка входа WEBHOOK-СЕРВЕРА (запускается через Gunicorn)
├── worker.py                       # Точка входа SCHEDULER (запускается ОТДЕЛЬНО через systemd)
├── config.py                       # Все настройки из .env
├── db.py                           # PostgreSQL: пул, init
├── redis_client.py                 # Redis: подключение, хелперы
│
├── handlers/                       # Роутеры aiogram
│   ├── __init__.py                 # Регистрация всех роутеров
│   ├── start.py                    # /start, выбор пути
│   ├── quest.py                    # Класс → оружие → раунды
│   ├── contacts.py                 # Сбор телефона (обязат.), @username авто
│   ├── arena.py                    # Ветка Арены
│   ├── payment.py                  # Upsell + YooKassa создание платежа
│   ├── payment_webhook.py          # Обработка webhook от YooKassa (aiohttp endpoint)
│   ├── upsell.py                   # Универсальная функция показа upsell (вызывается из любой точки)
│   └── admin.py                    # /reset_all, /reset_user, /stats, /slots
│
├── middlewares/
│   ├── __init__.py
│   ├── throttle.py                 # Rate limiting через Redis (антиспам)
│   ├── activity.py                 # Трекинг активности → Redis (НЕ PostgreSQL!)
│   ├── db_middleware.py            # Инжектирование db-pool в handler
│   └── logging_mw.py              # Структурированное логирование
│
├── services/                       # Бизнес-логика (без привязки к aiogram)
│   ├── __init__.py
│   ├── quest_service.py            # Логика прохождения квеста
│   ├── payment_service.py          # Создание платежа, HOLD слота, проверка, каунтер мест
│   ├── followup_service.py         # Дожим: idle-проверка (Redis), миниквесты
│   ├── media_service.py            # Кэширование file_id в Redis (отправка медиа без FSInputFile)
│   ├── broadcast_service.py        # Безопасная рассылка (rate limit 20 msg/sec)
│   └── notification_service.py     # Уведомления админам
│
├── models/
│   ├── __init__.py
│   ├── user.py                     # Pydantic: UserCreate, UserUpdate, UserDB
│   └── payment.py                  # Pydantic: PaymentCreate, PaymentStatus
│
├── keyboards/
│   ├── __init__.py
│   └── inline.py                   # Все InlineKeyboard-кнопки
│
├── utils/
│   ├── __init__.py
│   ├── config_db.py                # get_config() — чтение config из PostgreSQL
│   ├── content_manager.py          # ContentManager — загрузка текстов из content/texts.json
│   ├── statements.py               # Загрузка утверждений (с кэшем в Redis)
│   ├── media_ids.py                # file_id всех картинок воронки (Telegram хранит медиа)
│   └── validation.py               # Валидация телефона (email — опционально, не в contacts)
│
├── content/                        # Контент бота (НЕ хардкодить в .py!)
│   └── texts.json                  # Все тексты бота (загружается ContentManager при старте)
│   # Картинки НЕ лежат на сервере — только file_id в utils/media_ids.py
│
├── statements/                     # Файлы с утверждениями
│   ├── marketing.txt
│   ├── analytics.txt
│   ├── copywriting.txt
│   ├── design.txt
│   ├── management.txt
│   ├── video.txt
│   └── other.txt
│
├── schema.sql                      # SQL: создание всех таблиц с нуля (НЕ миграция!)
│
├── deploy/
│   ├── nginx.conf                  # Конфигурация NGINX (whitelist IP Telegram!)
│   ├── hydra-bot.service           # Systemd unit для Gunicorn (webhook)
│   ├── hydra-worker.service        # Systemd unit для worker.py (scheduler)
│   └── setup.sh                    # Скрипт первоначальной настройки сервера
│
├── requirements.txt
├── .env.example
└── README.md
```

---

# 🗄️ БАЗА ДАННЫХ (PostgreSQL)

## Создание таблиц: `schema.sql`

> **Это НЕ миграция.** Бот создаётся с нуля. Этот файл запускается один раз при первичной настройке сервера.

```sql
-- ============================================
-- ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,                     -- Telegram ID
    username VARCHAR(255),                           -- @username
    first_name VARCHAR(255),                         -- Имя в Telegram
    
    -- Состояние квеста (FSM хранится в Redis, здесь — персистентный бэкап)
    quest_state VARCHAR(50) DEFAULT 'start',         -- Последнее состояние
    quest_completed BOOLEAN DEFAULT FALSE,
    
    -- Выборы игрока
    player_class VARCHAR(20),                        -- businessman / freelancer
    weapon VARCHAR(20),                              -- marketing / analytics / ...
    
    -- Результаты
    score INTEGER DEFAULT 0,                         -- Артефакты (0-3)
    round_number INTEGER DEFAULT 0,                  -- Текущий раунд (1-3)
    current_statement_hash VARCHAR(64),              -- SHA256 утверждения (не сам текст!)
    current_is_truth BOOLEAN,
    
    -- Контакты (НИКОГДА НЕ УДАЛЯЮТСЯ при сбросе)
    phone VARCHAR(20),
    email VARCHAR(255),
    workshop_registered BOOLEAN DEFAULT FALSE,
    
    -- Арена
    arena_registered BOOLEAN DEFAULT FALSE,
    
    -- Дожим
    -- ⚠️ last_activity НЕ хранится здесь! Только в Redis (SETEX activity:{user_id} 300 1)
    followup_stage INTEGER DEFAULT 0,                -- 0=нет, -1=idle-напоминание отправлено, 1-5=дни миниквестов
    followup_completed BOOLEAN DEFAULT FALSE,        -- Прошёл миниквест дня
    
    -- Блокировка бота
    is_blocked BOOLEAN DEFAULT FALSE,                -- TRUE если пользователь заблокировал бота (TelegramForbiddenError)
    
    -- Upsell
    upsell_shown BOOLEAN DEFAULT FALSE,              -- Показывали ли оффер разбора
    
    -- Метаданные
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Источник трафика
    utm_source VARCHAR(100),                         -- Из deep link: /start utm_tiktok
    referrer VARCHAR(255)
);

-- Индексы для частых запросов
CREATE INDEX IF NOT EXISTS idx_users_quest_state ON users(quest_state);
CREATE INDEX IF NOT EXISTS idx_users_workshop ON users(workshop_registered);
CREATE INDEX IF NOT EXISTS idx_users_followup ON users(quest_completed, workshop_registered, followup_stage, is_blocked);
CREATE INDEX IF NOT EXISTS idx_users_blocked ON users(is_blocked) WHERE is_blocked = TRUE;
CREATE INDEX IF NOT EXISTS idx_users_created ON users(created_at);

-- ============================================
-- ТАБЛИЦА ПЛАТЕЖЕЙ
-- ============================================
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    
    yookassa_payment_id VARCHAR(100) UNIQUE,         -- ID платежа в YooKassa
    amount DECIMAL(10,2) NOT NULL,                   -- Сумма
    currency VARCHAR(3) DEFAULT 'RUB',
    
    status VARCHAR(20) DEFAULT 'pending',            -- pending / succeeded / canceled / refunded
    description TEXT,                                 -- Описание платежа
    
    -- Оффер
    offer_type VARCHAR(50) DEFAULT 'business_review', -- Тип оффера
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    paid_at TIMESTAMPTZ,                             -- Время успешной оплаты
    
    -- Метаданные от YooKassa
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_payments_yookassa ON payments(yookassa_payment_id);

-- ============================================
-- ТАБЛИЦА СОБЫТИЙ (АНАЛИТИКА)
-- ============================================
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    event_type VARCHAR(50) NOT NULL,                 -- quest_start, round_1, payment_created, etc.
    event_data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);

-- ============================================
-- ТАБЛИЦА КОНФИГУРАЦИИ (для горячей смены параметров)
-- ============================================
CREATE TABLE IF NOT EXISTS config (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Начальные значения
INSERT INTO config (key, value) VALUES
    ('upsell_total_slots', '10'),
    ('upsell_price', '5000'),
    ('upsell_enabled', 'true'),
    ('followup_enabled', 'true'),
    ('bot_active', 'true')
ON CONFLICT (key) DO NOTHING;

-- ============================================
-- ФУНКЦИЯ auto-update updated_at
-- ============================================
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();
```

### Принцип разделения данных при сбросе

```
┌─────────────────────────────────────────────────────┐
│              ДАННЫЕ ПОЛЬЗОВАТЕЛЯ                     │
│                                                      │
│  🔴 СБРАСЫВАЮТСЯ при /reset_user:                    │
│     quest_state, quest_completed,                    │
│     player_class, weapon, score,                     │
│     round_number, current_statement_hash,            │
│     current_is_truth, followup_stage,                │
│     followup_completed, upsell_shown                 │
│                                                      │
│  🟢 НИКОГДА НЕ СБРАСЫВАЮТСЯ:                        │
│     user_id, username, first_name,                   │
│     phone, email, workshop_registered,               │
│     arena_registered, is_blocked,                    │
│     created_at, utm_source, referrer                 │
│                                                      │
│  🟢 ТАБЛИЦА payments — НИКОГДА не трогается          │
│                                                      │
│  🔵 В REDIS (не в PostgreSQL!):                      │
│     activity:{user_id} — последняя активность (TTL)  │
│     hold:{user_id} — бронь слота upsell (TTL 15m)   │
│     fsm:{user_id}:* — состояние FSM                  │
│                                                      │
│  ⛔ ПОЛЬЗОВАТЕЛЬ НЕ МОЖЕТ сбросить себя сам.         │
│     Команды /reset нет. Кнопки "заново" нет.         │
└─────────────────────────────────────────────────────┘
```

---

# 🔧 УТИЛИТЫ: get_config, ContentManager, MediaService

## `utils/config_db.py` — Чтение конфигурации из PostgreSQL

> **⚠️ КРИТИЧНО:** Функция `get_config()` используется в `payment_service.py` и `payment_webhook.py`.
> Без неё бот упадёт с `NameError` при попытке оплаты.

```python
# utils/config_db.py

async def get_config(pool, key: str, default: str = "10") -> str:
    """
    Читает значение из таблицы config в PostgreSQL.
    Позволяет менять параметры (количество слотов, цену, флаги)
    без перезапуска бота — через UPDATE config SET value = '...' WHERE key = '...'.
    """
    result = await pool.fetchval(
        "SELECT value FROM config WHERE key = $1", key
    )
    return result if result else default
```

## `utils/content_manager.py` — Загрузка текстов из JSON

> **⚠️ СТРОГО ЗАПРЕЩЕНО** хардкодить тексты бота в `.py` файлах.
> Все тексты хранятся в `content/texts.json` и загружаются в ОЗУ при старте.
> Динамические переменные оборачиваются в `html.quote()` для защиты от XSS.

```python
# utils/content_manager.py

import json
from pathlib import Path
from html import escape as html_quote
from typing import Optional


class ContentManager:
    """
    Загружает content/texts.json один раз при старте бота.
    Хранит все тексты в ОЗУ — никаких повторных чтений с диска.
    """
    
    _instance: Optional['ContentManager'] = None
    _texts: dict = {}
    
    @classmethod
    def load(cls, path: str = "content/texts.json") -> 'ContentManager':
        if cls._instance is None:
            cls._instance = cls()
            with open(Path(path), "r", encoding="utf-8") as f:
                cls._texts = json.load(f)
        return cls._instance
    
    @classmethod
    def get(cls, key: str, **kwargs) -> str:
        """
        Возвращает текст по ключу. Динамические переменные подставляются
        через .format(**kwargs), все значения экранируются html.quote().
        
        Пример: ContentManager.get("upsell_offer", remaining=7, price="5000")
        """
        template = cls._texts.get(key, f"[MISSING TEXT: {key}]")
        safe_kwargs = {k: html_quote(str(v)) for k, v in kwargs.items()}
        return template.format(**safe_kwargs)
    
    @classmethod
    def get_raw(cls, key: str) -> str:
        """Возвращает текст без подстановок (для статических сообщений)."""
        return cls._texts.get(key, f"[MISSING TEXT: {key}]")
```

### Пример `content/texts.json`

```json
{
    "quest_start": "⚔️ Добро пожаловать в квест <b>«Гидра Сингулярности»</b>!\n\nВыбери свой путь:",
    "class_businessman": "💼 <b>Предприниматель</b>\nТы управляешь бизнесом и хочешь усилить его с помощью ИИ.",
    "class_freelancer": "🎨 <b>Фрилансер</b>\nТы работаешь на себя и хочешь автоматизировать рутину.",
    "round_statement": "🐉 <b>Голова Гидры шепчет:</b>\n\n<i>«{statement}»</i>\n\nЭто ПРАВДА или ЛОЖЬ?",
    "round_correct": "🎉 Отлично! Ты отрубил голову Гидре! Артефакт получен. ({score}/3)",
    "round_wrong": "💀 Гидра обманула тебя! Голова регенерирует... ({score}/3)",
    "quest_results": "🏆 <b>Квест завершён!</b>\n\nТвой счёт: {score}/3 артефактов\nКласс: {player_class}\nОружие: {weapon}",
    "upsell_offer": "🔥 <b>ЭКСКЛЮЗИВНОЕ ПРЕДЛОЖЕНИЕ</b>\n\nВы можете получить разбор вашего бизнеса с помощью ИИ в прямом эфире.\n\n💰 Стоимость: {price} ₽\n🪑 Осталось мест: {remaining}/10\n⏰ Бронь действует 15 минут",
    "upsell_no_slots": "К сожалению, все места на разбор уже заняты.",
    "payment_success": "✅ Оплата прошла! Вы забронировали место на разборе бизнеса.\nМы свяжемся с вами для уточнения деталей.",
    "payment_refund": "К сожалению, пока вы оформляли оплату, все места были заняты.\nДеньги автоматически возвращены на вашу карту.",
    "idle_reminder": "⚔️ Герой, ты остановился в бою! Гидра наступает!\n\nПродолжи квест — игра скоро закончится! 🐉",
    "miniquest_day1": "Пока ты бездействовал, Гидра начала восстанавливаться. Одна из голов снова шепчет ложь...",
    "miniquest_day2": "Ещё одна голова поднялась из тьмы. Чем дольше ты ждёшь, тем сильнее она становится...",
    "miniquest_day3": "Гидра подобралась к стенам Data Sanctuary! Без твоей помощи защита падёт...",
    "miniquest_day4": "Защитники устали. Они ждут тебя. Один удар правдой — и Гидра отступит...",
    "miniquest_day5": "Это последний день. Завтра ворота закроются. Гидра или ты — кто победит?",
    "miniquest_correct": "🎉 Отлично! Ты снова отрубил голову Гидре!",
    "miniquest_wrong": "💪 Не сдавайся! Гидра хитра, но ты сильнее!",
    "workshop_cta_day1": "Кстати, мы проводим бесплатный воркшоп, где ты научишься создавать своего ИИ-педагога за 30 минут. Хочешь присоединиться?",
    "workshop_cta_day2": "Знаешь, что поможет окончательно победить Гидру? Практика! На нашем бесплатном воркшопе ты соберёшь первый НЕЙРОСКЕЛЕТ. Записаться?",
    "workshop_cta_day3": "Ты доказал, что умеешь отличать правду от лжи. Пора перейти на новый уровень! Бесплатный воркшоп — твой следующий шаг к статусу НЕЙРО-ЮНИТ.",
    "workshop_cta_day4": "Ты сражаешься как настоящий герой! На бесплатном воркшопе ты получишь полный арсенал ИИ-инструментов. Железный Человек начинал так же.",
    "workshop_cta_day5": "Последний день. Последний шанс. Бесплатный воркшоп стартует скоро — и места заканчиваются. Запишись сейчас и заверши трансформацию.",
    "reset_user_usage": "Использование: /reset_user &lt;ID&gt;\nПример: /reset_user 123456789"
}
```

## `services/media_service.py` — Кэширование file_id в Redis

> **⚠️ СТРОГО ЗАПРЕЩЁН `FSInputFile` в циклах рассылок!**
> При отправке картинки 5000 пользователям через `FSInputFile` — каждый раз файл загружается
> на серверы Telegram заново (5000 загрузок по 200KB = 1GB трафика + 5000× задержка).
> Решение: один раз отправить файл админу → получить `file_id` → кэшировать в Redis →
> в рассылке слать только хэш (мгновенно, без загрузки).

```python
# services/media_service.py

from aiogram.types import FSInputFile
from pathlib import Path
import hashlib
import logging

logger = logging.getLogger(__name__)

MEDIA_CACHE_PREFIX = "media:file_id:"


async def get_file_id(
    bot,
    redis_conn,
    file_path: str,
    admin_chat_id: int
) -> str:
    """
    Возвращает Telegram file_id для файла. Алгоритм:
    1. Проверяет кэш в Redis (ключ = hash пути файла)
    2. Если нет — отправляет файл скрытым сообщением админу
    3. Получает file_id из ответа Telegram
    4. Кэширует в Redis (без TTL — file_id не протухает)
    5. Удаляет скрытое сообщение у админа
    """
    path_hash = hashlib.md5(file_path.encode()).hexdigest()
    cache_key = f"{MEDIA_CACHE_PREFIX}{path_hash}"
    
    cached = await redis_conn.get(cache_key)
    if cached:
        return cached
    
    # Файл ещё не кэширован — загружаем через скрытую отправку админу
    msg = await bot.send_photo(
        chat_id=admin_chat_id,
        photo=FSInputFile(Path(file_path)),
        caption="[система] кэширование медиа — это сообщение будет удалено"
    )
    
    file_id = msg.photo[-1].file_id
    await redis_conn.set(cache_key, file_id)
    
    try:
        await bot.delete_message(admin_chat_id, msg.message_id)
    except Exception:
        pass
    
    logger.info(f"Cached file_id for {file_path}: {file_id[:20]}...")
    return file_id
```

---

# ⚙️ КОНФИГУРАЦИЯ

## `.env.example`

```env
# ======== TELEGRAM ========
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_IDS=123456789,987654321
ADMIN_USERNAME=fimadima13
WEBHOOK_HOST=https://bot.neurounit.fun
WEBHOOK_PATH=/webhook/bot
WEBHOOK_PORT=8443
WEBHOOK_SECRET=<generate_random_64_char_string>

# ======== POSTGRESQL ========
DB_HOST=localhost
DB_PORT=5432
DB_NAME=hydra_bot
DB_USER=hydra
DB_PASSWORD=<strong_password>
DB_POOL_MIN=2
DB_POOL_MAX=10

# ======== REDIS ========
REDIS_URL=redis://localhost:6379/0

# ======== YOOKASSA ========
YOOKASSA_SHOP_ID=390540012
YOOKASSA_SECRET_KEY=live_89296_XXXXXXXXXXXXXXXX
YOOKASSA_RETURN_URL=https://t.me/neurounit_bot

# ======== ВНЕШНИЕ ССЫЛКИ ========
GENERATOR_BOT_URL=https://t.me/video_generator_bot
WORKSHOP_URL=https://example.com/workshop

# ======== ПРИЗЫ ========
PROMO_CODE=HYDRA50

# ======== НАСТРОЙКИ ДОЖИМА ========
FOLLOWUP_IDLE_MINUTES=5
FOLLOWUP_DAYS=5
```

## `config.py`

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "fimadima13")

# Webhook
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook/bot")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8443"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")  # secret_token для верификации запросов от Telegram

# PostgreSQL
DB_DSN = (
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}"
    f"/{os.getenv('DB_NAME', 'hydra_bot')}"
)
DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "2"))
DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))  # ⚠️ 4 воркера × 10 = 40 < PG default 100

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# YooKassa
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")
YOOKASSA_RETURN_URL = os.getenv("YOOKASSA_RETURN_URL")

# Внешние ссылки
GENERATOR_BOT_URL = os.getenv("GENERATOR_BOT_URL", "https://t.me/video_generator_bot")
WORKSHOP_URL = os.getenv("WORKSHOP_URL", "https://example.com/workshop")

# Призы
PRIZE_CONTACT = f"@{ADMIN_USERNAME}"
PROMO_CODE = os.getenv("PROMO_CODE", "HYDRA50")

# Дожим
FOLLOWUP_IDLE_MINUTES = int(os.getenv("FOLLOWUP_IDLE_MINUTES", "5"))
FOLLOWUP_DAYS = int(os.getenv("FOLLOWUP_DAYS", "5"))
```

---

# 🔄 МАШИНА СОСТОЯНИЙ (FSM)

FSM хранится в **Redis** (быстро, персистентно при перезапуске бота). В PostgreSQL пишется `quest_state` как бэкап для аналитики.

## Список состояний

```python
from aiogram.fsm.state import State, StatesGroup


class QuestStates(StatesGroup):
    # Стартовый экран
    START = State()

    # Квест
    CLASS_SELECTION = State()
    WEAPON_SELECTION = State()

    ROUND_1 = State()        # Показ утверждения раунда 1
    ROUND_1_ANSWER = State() # Ожидание ответа
    ROUND_2 = State()
    ROUND_2_ANSWER = State()
    ROUND_3 = State()
    ROUND_3_ANSWER = State()

    QUEST_RESULTS = State()  # Итоги
    MORAL = State()          # Мораль (мост к воркшопу)

    # Сбор контактов (@username — авто, телефон обязателен, email не собираем)
    CONTACT_PHONE = State()
    CONTACT_CONFIRM = State()

    # Upsell
    UPSELL_OFFER = State()   # Показ оффера разбора бизнеса

    # Финал
    FINAL = State()
    COMPLETED = State()

    # Арена (отдельная ветка; телефон обязателен, email не собираем)
    ARENA_PHONE = State()
    ARENA_DONE = State()


class FollowupStates(StatesGroup):
    """Состояния миниквестов дожима"""
    MINIQUEST_ACTIVE = State()
    MINIQUEST_ANSWER = State()
```

## Схема переходов

```
/start
  │
  ├─[🎮 Квест]────────────────────────────────────────────┐
  │                                                         │
  │  CLASS_SELECTION ──► WEAPON_SELECTION                    │
  │                           │                              │
  │                    ROUND_1 → ROUND_1_ANSWER              │
  │                           │                              │
  │                    ROUND_2 → ROUND_2_ANSWER              │
  │                           │                              │
  │                    ROUND_3 → ROUND_3_ANSWER              │
  │                           │                              │
  │                    QUEST_RESULTS ──► MORAL                │
  │                                       │                  │
  │                              CONTACT_PHONE ──► CONFIRM    │
  │                                       │                  │
  │                              ┌────────┤                  │
  │                              ▼        │                  │
  │                        UPSELL_OFFER   │ (если мест нет)  │
  │                         (10 мест)     │                  │
  │                              │        │                  │
  │                              ▼        ▼                  │
  │                            FINAL → COMPLETED             │
  │                                                          │
  ├─[🎬 Генератор]──► Редирект (внешняя ссылка)             │
  │                                                          │
  └─[⚔️ Арена]──► ARENA_PHONE → ARENA_DONE                  │
                                                    │        │
                                        [🎮 Пройти квест?]───┘

═══ ДОЖИМ (параллельный процесс) ═══

  Пользователь завис >5 минут на шаге
       │
       ▼
  Одноразовое сообщение: "Продолжите квест..."
  
  Пользователь прошёл квест, НЕ оставил контакты
       │
       ▼
  День 1: Миниквест + картинка → похвала → предложение воркшопа (текст 1)
  День 2: Миниквест + картинка → похвала → предложение воркшопа (текст 2)
  День 3: Миниквест + картинка → похвала → предложение воркшопа (текст 3)
  День 4: Миниквест + картинка → похвала → предложение воркшопа (текст 4)
  День 5: Миниквест + картинка → похвала → предложение воркшопа (текст 5)
       │
       ▼
  Если не записался — прекращаем. Не спамим.
```

---

# 💳 ИНТЕГРАЦИЯ YOOKASSA

## Логика upsell-оффера

> **⚠️ КРИТИЧЕСКИ ВАЖНО:** Upsell триггерится при ЛЮБОМ переключении `workshop_registered = TRUE`.
> Не только в основном квесте, но и после миниквеста дожима, и после арены.
> Используй единую функцию `show_upsell_if_available(bot, user_id, pool, redis)`.

```
Пользователь записался на воркшоп (workshop_registered = true)
  ↓ (вызывается из handlers/contacts.py, handlers/upsell.py, services/followup_service.py)
  ↓
  ▼
Вызов show_upsell_if_available():
  │
  ├── Шаг 1: Подсчитать занятые слоты
  │           paid = SELECT COUNT(*) FROM payments WHERE status='succeeded'
  │           held = КОЛИЧЕСТВО ключей hold:* в Redis
  │           available = 10 - paid - held
  │
  ├── available > 0 ?
  │     │
  │     ├── ДА:
  │     │     Шаг 2: HOLD слота в Redis (АТОМАРНАЯ ОПЕРАЦИЯ!)
  │     │            SETNX hold:{user_id} 1 → если OK:
  │     │            EXPIRE hold:{user_id} 900  (15 минут)
  │     │     Шаг 3: Показать сообщение с каунтером:
  │     │            ┌─────────────────────────────────────────────┐
  │     │            │ 🔥 ЭКСКЛЮЗИВНОЕ ПРЕДЛОЖЕНИЕ                │
  │     │            │                                             │
  │     │            │ Вы можете получить разбор вашего бизнеса    │
  │     │            │ с помощью ИИ в прямом эфире от совета       │
  │     │            │ экспертов.                                   │
  │     │            │                                             │
  │     │            │ 💰 Стоимость: 5 000 ₽                      │
  │     │            │ 🪑 Осталось мест: {available}/10            │
  │     │            │ ⏰ Бронь действует 15 минут                 │
  │     │            │                                             │
  │     │            │ [💳 Оплатить] [❌ Пропустить]              │
  │     │            └─────────────────────────────────────────────┘
  │     │     Шаг 4: Создать платёж в YooKassa
  │     │
  │     └── НЕТ (мест нет):
  │           Пропустить, показать FINAL напрямую
  │
  └── При нажатии "Пропустить":
        Удалить hold:{user_id} из Redis → слот возвращается в пул
```

### Почему HOLD, а не просто SELECT COUNT?

Без холда при наплыве 500 человек из TikTok:
- Все 500 делают SELECT, видят "10 мест"
- Все 500 получают ссылку на оплату
- 50 человек оплачивают → 40 ручных возвратов, потеря комиссии, негатив

С холдом:
- Первые 10 получают ссылку + бронь на 15 минут
- Остальные 490 видят "мест нет" → переходят к FINAL
- Если кто-то из 10 не оплатил за 15 минут → бронь сгорает → слот снова доступен

## Создание платежа

```python
# services/payment_service.py — ПСЕВДОКОД

from yookassa import Configuration, Payment as YKPayment
import uuid
import asyncio
import time

Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY

# ============================================================
# АТОМАРНОЕ РЕЗЕРВИРОВАНИЕ СЛОТОВ (Lua-скрипты для Redis)
# ============================================================
# Почему Lua: Check-Then-Act двумя командами = race condition на 4 воркерах.
# Lua = одна атомарная операция внутри Redis.
# Почему Sorted Set: redis.keys("hold:*") = O(N), блокирует Redis.
# ZCARD = O(1), ZREMRANGEBYSCORE = O(log N).

HOLD_TTL = 900  # 15 минут
HOLDS_ZSET_KEY = "upsell:holds"

# Lua: проверка лимита + установка холда (АТОМАРНО)
HOLD_SLOT_LUA = """
local holds_key = KEYS[1]
local user_id = ARGV[1]
local max_slots = tonumber(ARGV[2])
local paid_count = tonumber(ARGV[3])
local now = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])
redis.call('ZREMRANGEBYSCORE', holds_key, '-inf', now)
local active_holds = redis.call('ZCARD', holds_key)
if (paid_count + active_holds) >= max_slots then return 0 end
redis.call('ZADD', holds_key, now + ttl, user_id)
return 1
"""

# Lua: подсчёт активных холдов
CHECK_LIMIT_LUA = """
local holds_key = KEYS[1]
local now = tonumber(ARGV[1])
redis.call('ZREMRANGEBYSCORE', holds_key, '-inf', now)
return redis.call('ZCARD', holds_key)
"""


async def get_remaining_slots(pool, redis_conn) -> int:
    """Сколько мест РЕАЛЬНО осталось (с учётом холдов)"""
    total = await get_config(pool, 'upsell_total_slots')  # 10
    
    paid = await pool.fetchval(
        "SELECT COUNT(*) FROM payments WHERE status = 'succeeded' AND offer_type = 'business_review'"
    )
    
    # Считаем активные холды в Redis
    # ЗАПРЕЩЕНО redis.keys()! Используем Lua + Sorted Set.
    import time as _t
    active_holds = await redis_conn.eval(CHECK_LIMIT_LUA, 1, HOLDS_ZSET_KEY, int(_t.time()))
    held = active_holds
    
    return max(0, int(total) - paid - held)


async def try_hold_slot(pool, redis_conn, user_id: int) -> bool:
    """
    АТОМАРНО проверяет лимит и устанавливает холд через Lua-скрипт.
    Lua гарантирует: между проверкой и установкой никто не вклинится.
    500 юзеров из TikTok не смогут получить 500 ссылок на 10 мест.
    """
    total = int(await get_config(pool, 'upsell_total_slots'))
    paid = await pool.fetchval(
        "SELECT COUNT(*) FROM payments WHERE status = 'succeeded' AND offer_type = 'business_review'"
    )
    result = await redis_conn.eval(
        HOLD_SLOT_LUA, 1, HOLDS_ZSET_KEY,
        str(user_id), str(total), str(paid), str(int(time.time())), str(HOLD_TTL)
    )
    return result == 1


async def release_hold(redis_conn, user_id: int):
    """Отпускает бронь (при нажатии 'Пропустить' или при успешной оплате)"""
    await redis_conn.zrem(HOLDS_ZSET_KEY, str(user_id))


async def create_payment(pool, redis_conn, user_id: int) -> dict:
    """Создаёт платёж в YooKassa. Вызывается ТОЛЬКО если hold уже установлен."""
    
    remaining = await get_remaining_slots(pool, redis_conn)
    if remaining <= 0:
        await release_hold(redis_conn, user_id)
        return {"error": "no_slots"}

    idempotence_key = str(uuid.uuid4())

    # ⚠️ yookassa SDK синхронный (requests) — блокирует event loop!
    # Оборачиваем в asyncio.to_thread() для выполнения в thread pool.
    payment = await asyncio.to_thread(
        YKPayment.create,
        {
            "amount": {"value": "5000.00", "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": YOOKASSA_RETURN_URL
            },
            "capture": True,
            "description": f"Разбор бизнеса с ИИ — Пользователь {user_id}",
            "metadata": {"user_id": str(user_id), "offer_type": "business_review"}
        },
        idempotence_key
    )

    # Сохраняем в БД
    await pool.execute(
        """INSERT INTO payments (user_id, yookassa_payment_id, amount, status, offer_type)
           VALUES ($1, $2, $3, $4, $5)""",
        user_id, payment.id, 5000.00, 'pending', 'business_review'
    )

    return {"url": payment.confirmation.confirmation_url, "payment_id": payment.id}
```

## Webhook от YooKassa

YooKassa отправляет POST на `/yookassa/webhook` при изменении статуса платежа.

```python
# handlers/payment_webhook.py — ПСЕВДОКОД

from aiohttp import web
from yookassa.domain.notification import WebhookNotificationEventType, WebhookNotification


async def yookassa_webhook_handler(request: web.Request):
    """Обработка webhook от YooKassa"""
    body = await request.json()
    
    notification = WebhookNotification(body)
    payment = notification.object

    pool = request.app['pool']
    redis_conn = request.app['redis']
    bot = request.app['bot']

    if notification.event == WebhookNotificationEventType.PAYMENT_SUCCEEDED:
        user_id = int(payment.metadata.get("user_id"))
        
        # Обновляем статус в БД (ИДЕМПОТЕНТНО — YooKassa может прислать webhook дважды)
        result = await pool.fetchval(
            """UPDATE payments SET status = 'succeeded', paid_at = NOW()
               WHERE yookassa_payment_id = $1 AND status != 'succeeded'
               RETURNING id""",
            payment.id
        )
        
        if result is None:
            return web.Response(status=200)  # Повторный webhook
        
        # Снимаем hold
        await redis_conn.zrem("upsell:holds", str(user_id))
        
        # ЗАЩИТА ОТ ЗОМБИ-ПЛАТЕЖЕЙ:
        # Юзер получил ссылку -> hold истёк -> места заняли -> юзер оплатил.
        import asyncio
        from yookassa import Refund
        
        paid_count = await pool.fetchval(
            "SELECT COUNT(*) FROM payments WHERE status = 'succeeded' AND offer_type = 'business_review'"
        )
        total_slots = int(await get_config(pool, 'upsell_total_slots'))
        
        if paid_count > total_slots:
            try:
                await asyncio.to_thread(Refund.create, {
                    "payment_id": payment.id,
                    "amount": {"value": payment.amount.value, "currency": "RUB"},
                    "description": "Автовозврат: все места заняты"
                })
                await pool.execute(
                    "UPDATE payments SET status = 'refunded' WHERE yookassa_payment_id = $1",
                    payment.id
                )
                try:
                    from utils.content_manager import ContentManager
                    await bot.send_message(user_id, ContentManager.get_raw("payment_refund"))
                except Exception: pass
                await notify_admins(bot, "auto_refund", {"user_id": user_id})
            except Exception as e:
                await notify_admins(bot, "CRITICAL_refund_failed", {
                    "user_id": user_id, "payment_id": payment.id, "error": str(e)
                })
            return web.Response(status=200)
        
        # Уведомляем пользователя
        try:
            from utils.content_manager import ContentManager
            await bot.send_message(user_id, ContentManager.get_raw("payment_success"))
        except Exception:
            pass  # Пользователь мог заблокировать бота
        
        # Уведомляем админов
        await notify_admins(bot, "payment_success", {
            "user_id": user_id,
            "amount": payment.amount.value
        })

        # Логируем событие
        await log_event(pool, user_id, "payment_succeeded", {"amount": 5000})

    elif notification.event == WebhookNotificationEventType.PAYMENT_CANCELED:
        user_id = int(payment.metadata.get("user_id"))
        
        await pool.execute(
            """UPDATE payments SET status = 'canceled'
               WHERE yookassa_payment_id = $1 AND status = 'pending'""",
            payment.id
        )
        
        # Снимаем hold
        await redis_conn.zrem("upsell:holds", str(user_id))

    return web.Response(status=200)
```

### Каунтер мест (обратный отсчёт) — ФОРМУЛА

```
Мест доступно = 10 - COUNT(payments WHERE status='succeeded') - COUNT(Redis keys "hold:*")
```

Место считается "занятым" если:
- Оплачено (`payments.status = 'succeeded'`) — навсегда
- Забронировано (`hold:{user_id}` в Redis) — на 15 минут

Если бронь истекает (TTL) — слот автоматически возвращается в пул. Никакого ручного cleanup не нужно.

---

# 🔥 МЕХАНИКА ДОЖИМА (Follow-up)

## Триггер 1: Завис на шаге (>5 минут)

### Трекинг активности — ЧЕРЕЗ REDIS, НЕ POSTGRESQL!

> **⚠️ КРИТИЧНО:** НЕ ПИСАТЬ `UPDATE last_activity_at = NOW()` в PostgreSQL при каждом клике!
> При 10 000 пользователей это убьёт диск (MVCC bloat). Используем Redis с TTL.

```python
# middlewares/activity.py

class ActivityMiddleware(BaseMiddleware):
    """
    При каждом действии пользователя обновляет ключ в Redis с TTL.
    Если ключ существует — пользователь активен.
    Если ключа нет — пользователь "завис" (не действовал > TTL секунд).
    """
    
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user:
            # SETEX: устанавливает ключ с TTL. Лёгкая операция, Redis выдерживает 100K+ RPS
            await redis.setex(f"activity:{user.id}", FOLLOWUP_IDLE_MINUTES * 60, "1")
        
        return await handler(event, data)
```

### Проверка зависших — в worker.py

```python
# services/followup_service.py (запускается ТОЛЬКО из worker.py!)

from utils.content_manager import ContentManager

async def check_idle_users(bot, pool, redis_conn):
    """
    Вызывается scheduler-ом каждые 60 секунд.
    Находит пользователей, у которых НЕТ ключа activity:{user_id} в Redis
    (значит они не действовали > FOLLOWUP_IDLE_MINUTES минут).
    """
    
    # Берём пользователей в активном квесте, которым ещё не отправляли напоминание
    active_users = await pool.fetch("""
        SELECT user_id, quest_state FROM users
        WHERE quest_completed = FALSE
          AND quest_state NOT IN ('start', 'completed', 'final')
          AND followup_stage = 0
          AND is_blocked = FALSE
    """)
    
    if not active_users:
        return
    
    # ⚠️ ЗАПРЕЩЕНО вызывать redis.exists() в цикле (N+1 problem)!
    # Один пакетный запрос MGET вместо 5000 отдельных exists():
    activity_keys = [f"activity:{u['user_id']}" for u in active_users]
    activity_statuses = await redis_conn.mget(activity_keys)
    
    # Собираем только зависших (у кого ключ = None)
    idle_users = [
        user for user, status in zip(active_users, activity_statuses)
        if status is None
    ]
    
    for user in idle_users:
            # Пользователь завис — отправляем напоминание
            # ВАЖНО: Помечаем ПЕРЕД отправкой, чтобы при ошибке не слать повторно!
            await pool.execute(
                "UPDATE users SET followup_stage = -1 WHERE user_id = $1",
                user['user_id']
            )
            
            try:
                await bot.send_message(
                    user['user_id'],
                    ContentManager.get_raw("idle_reminder")
                )
            except TelegramForbiddenError:
                # Пользователь заблокировал бота — помечаем
                await pool.execute(
                    "UPDATE users SET is_blocked = TRUE WHERE user_id = $1",
                    user['user_id']
                )
            except Exception as e:
                logger.warning(f"Ошибка отправки idle-напоминания {user['user_id']}: {e}")
```

## Триггер 2: Миниквесты (5 дней после квеста без контактов)

Если пользователь **прошёл квест** (`quest_completed = TRUE`) но **не записался на воркшоп** (`workshop_registered = FALSE`), каждый день в течение 5 дней ему приходит миниквест.

### Структура миниквестов

Каждый миниквест = **сообщение + картинка + одно задание (ПРАВДА/ЛОЖЬ)**

| День | Тема миниквеста | Нарратив |
|------|-----------------|----------|
| 1 | Гидра восстанавливает первую голову | "Пока ты бездействовал, Гидра начала восстанавливаться. Одна из голов снова шепчет ложь..." |
| 2 | Вторая голова оживает | "Ещё одна голова поднялась из тьмы. Чем дольше ты ждёшь, тем сильнее она становится..." |
| 3 | Гидра атакует Data Sanctuary | "Гидра подобралась к стенам Data Sanctuary! Без твоей помощи защита падёт..." |
| 4 | Последний рубеж обороны | "Защитники устали. Они ждут тебя. Один удар правдой — и Гидра отступит..." |
| 5 | Финальный шанс | "Это последний день. Завтра ворота закроются. Гидра или ты — кто победит?" |

### Логика отправки

> **⚠️ КРИТИЧНО: RATE LIMITING!** Telegram разрешает не более 30 msg/sec.
> Безопасный предел: 20 msg/sec → `asyncio.sleep(0.05)` между сообщениями.
> Обязательна обработка `TelegramRetryAfter`!

```python
# services/followup_service.py (запускается ТОЛЬКО из worker.py!)

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from utils.media_ids import get_miniquest_file_id
from utils.content_manager import ContentManager
from config import ADMIN_IDS

# file_id для миниквестов задаются в utils/media_ids.py (MINIQUEST_FILE_IDS)

async def send_daily_miniquest(bot, pool, redis_conn):
    """
    Вызывается scheduler-ом 1 раз в день (например, в 11:00 MSK).
    ЗАПУСКАЕТСЯ СТРОГО в 1 экземпляре (worker.py, не Gunicorn!)
    
    ⚠️ Медиа отправляется через file_id (кэшированный в Redis),
    а НЕ через FSInputFile. Иначе 5000 пользователей = 5000 загрузок файла.
    """
    
    users = await pool.fetch("""
        SELECT user_id, followup_stage, created_at FROM users
        WHERE quest_completed = TRUE
          AND workshop_registered = FALSE
          AND followup_stage BETWEEN 0 AND 4
          AND followup_completed = FALSE
          AND is_blocked = FALSE
          AND created_at <= NOW() - INTERVAL '1 day' * (followup_stage + 1)
    """)
    
    # Берем готовые file_id из utils/media_ids.py (без файловой системы)
    needed_days = set(u['followup_stage'] + 1 for u in users)
    file_ids = {day: get_miniquest_file_id(day) for day in needed_days}
    
    for user in users:
        day = user['followup_stage'] + 1  # 1-5
        miniquest = get_miniquest_for_day(day)
        
        try:
            # Отправляем картинку через кэшированный file_id (НЕ FSInputFile!)
            photo_id = file_ids.get(day)
            if photo_id:
                await bot.send_photo(
                    user['user_id'],
                    photo=photo_id,  # ← file_id хэш, мгновенная отправка
                    caption=ContentManager.get(f"miniquest_day{day}")
                )
            
            await asyncio.sleep(0.05)  # Rate limit: 20 msg/sec
            
            # Отправляем задание
            await bot.send_message(
                user['user_id'],
                miniquest['statement'],
                reply_markup=get_miniquest_keyboard()  # ПРАВДА / ЛОЖЬ
            )
            
            await asyncio.sleep(0.05)
            
        except TelegramRetryAfter as e:
            logger.warning(f"Telegram rate limit, sleeping {e.retry_after}s")
            await asyncio.sleep(e.retry_after)
            
        except TelegramForbiddenError:
            await pool.execute(
                "UPDATE users SET is_blocked = TRUE WHERE user_id = $1",
                user['user_id']
            )
            
        except Exception as e:
            logger.error(f"Ошибка отправки миниквеста {user['user_id']}: {e}")
            
        finally:
            # ВСЕГДА обновляем stage, даже при ошибке!
            await pool.execute(
                "UPDATE users SET followup_stage = $1 WHERE user_id = $2",
                day, user['user_id']
            )
```

### После прохождения миниквеста

```python
async def handle_miniquest_answer(user_id, answer, pool, redis_conn, bot):
    """Обработка ответа на миниквест"""
    user = await get_user(pool, user_id)
    
    is_correct = check_answer(answer, user)
    
    # Тексты из ContentManager (НЕ хардкод!)
    praise = ContentManager.get_raw("miniquest_correct" if is_correct else "miniquest_wrong")
    await bot.send_message(user_id, praise)
    
    # Предложение воркшопа — текст зависит от дня, берётся из texts.json
    day = user['followup_stage']
    workshop_text = ContentManager.get_raw(f"workshop_cta_day{day}")
    
    await bot.send_message(
        user_id,
        workshop_text,
        reply_markup=get_workshop_signup_keyboard()  # [📝 Записаться] [⏭ Позже]
    )
    
    await pool.execute(
        "UPDATE users SET followup_completed = TRUE WHERE user_id = $1",
        user_id
    )


# ⚠️ ВАЖНО: Когда пользователь нажимает "Записаться" из миниквеста:
# 1. Запросить телефон (если ещё нет). @username — захватывается автоматически
# 2. Установить workshop_registered = TRUE
# 3. Вызвать show_upsell_if_available(bot, user_id, pool, redis_conn)
# Это ЕДИНАЯ точка входа для upsell — та же функция, что и в основном квесте!
```

---

# 🔧 АДМИНСКИЕ КОМАНДЫ

## Список команд

| Команда | Описание | Доступ |
|---------|----------|--------|
| `/reset_all` | Сброс прогресса ВСЕХ игроков (контакты и платежи сохраняются) | ADMIN_IDS |
| `/reset_user <user_id>` | Сброс прогресса конкретного игрока | ADMIN_IDS |
| `/stats` | Лиды и статусы оплат (полная воронка — во внешней аналитике) | ADMIN_IDS |
| `/slots` | Оставшиеся места на upsell | ADMIN_IDS |
| `/broadcast <текст>` | Рассылка всем пользователям | ADMIN_IDS |
| `/export_leads` | Выгрузка лидов в CSV | ADMIN_IDS |

## Политика уведомлений админам (антиспам)

- **НЕ** уведомлять о каждом новом пользователе — при нагрузке админ утонет в сообщениях.
- Уведомлять **только**: лиды (notify_new_contact, notify_arena_lead) и оплаты (payment_success, auto_refund).
- Остальное (квест пройден и т.д.) — только в статистику.

## Политика аналитики в админке

- Внешняя аналитика (без сервера) считает шаги воронки + соцдем.
- В админке показываем **только лиды и статусы оплат**.
- Таблица `events` остаётся для сравнения внутренней и внешней аналитики.

## Реализация сброса

```python
# handlers/admin.py

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from config import ADMIN_IDS

router = Router()


def admin_only(message: Message) -> bool:
    return message.from_user.id in ADMIN_IDS


@router.message(Command("reset_all"), admin_only)
async def cmd_reset_all(message: Message, pool, redis_conn):
    """Сброс прогресса ВСЕХ игроков (контакты и платежи сохраняются!)"""
    
    result = await pool.execute("""
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
        WHERE quest_completed = TRUE OR quest_state != 'start'
    """)
    
    # Очищаем FSM в Redis
    # ⚠️ ЗАПРЕЩЕНО redis.keys()! scan(0) возвращает только первый батч!
    # Используем scan_iter — автоматически итерирует ВСЕ батчи курсора.
    deleted = 0
    async for key in redis_conn.scan_iter(match="fsm:*", count=500):
        await redis_conn.delete(key)
        deleted += 1
    
    affected = result.split()[-1]  # "UPDATE N"
    
    await message.answer(
        f"✅ Прогресс сброшен для {affected} пользователей.\n"
        f"🗑 Удалено FSM-ключей в Redis: {deleted}\n"
        f"📱 Контакты, платежи и регистрации — НЕ ТРОНУТЫ."
    )


@router.message(Command("reset_user"), admin_only)
async def cmd_reset_user(message: Message, pool, redis_conn):
    """Сброс прогресса конкретного игрока"""
    args = message.text.split()
    
    if len(args) < 2 or not args[1].isdigit():
        return await message.answer("Использование: /reset_user <ID>\nПример: /reset_user 123456789")
    
    target_user_id = int(args[1])
    
    user = await pool.fetchrow(
        "SELECT user_id, first_name, username FROM users WHERE user_id = $1",
        target_user_id
    )
    
    if not user:
        await message.answer(f"❌ Пользователь {target_user_id} не найден")
        return
    
    await pool.execute("""
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
    """, target_user_id)
    
    # Очищаем FSM в Redis для конкретного пользователя
    async for key in redis_conn.scan_iter(match=f"fsm:{target_user_id}:*", count=50):
        await redis_conn.delete(key)
    
    await message.answer(
        f"✅ Прогресс сброшен для {user['first_name']} (@{user['username']}).\n"
        f"📱 Контакты и платежи — НЕ ТРОНУТЫ.\n"
        f"Пользователь может пройти квест заново."
    )


@router.message(Command("stats"), admin_only)
async def cmd_stats(message: Message, pool, redis_conn):
    """Статистика воронки"""
    stats = await pool.fetchrow("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE quest_completed) as completed,
            COUNT(*) FILTER (WHERE workshop_registered) as workshop,
            COUNT(*) FILTER (WHERE phone IS NOT NULL) as with_phone,
            COUNT(*) FILTER (WHERE arena_registered) as arena
        FROM users
    """)
    
    payments = await pool.fetchrow("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'succeeded') as paid,
            COALESCE(SUM(amount) FILTER (WHERE status = 'succeeded'), 0) as revenue
        FROM payments
    """)
    
    remaining = await get_remaining_slots(pool, redis_conn)
    
    text = (
        f"📊 СТАТИСТИКА БОТА\n\n"
        f"👥 Всего пользователей: {stats['total']}\n"
        f"🎮 Прошли квест: {stats['completed']}\n"
        f"📝 Записались на воркшоп: {stats['workshop']}\n"
        f"📱 Оставили телефон: {stats['with_phone']}\n"
        f"⚔️ Арена: {stats['arena']}\n\n"
        f"💳 Оплаченных разборов: {payments['paid']}\n"
        f"💰 Выручка: {payments['revenue']}₽\n"
        f"🪑 Мест на разбор осталось: {remaining}/10\n\n"
        f"📈 Конверсии:\n"
        f"  /start → квест: {stats['completed']}/{stats['total']} "
        f"({round(stats['completed']/max(stats['total'],1)*100)}%)\n"
        f"  квест → воркшоп: {stats['workshop']}/{max(stats['completed'],1)} "
        f"({round(stats['workshop']/max(stats['completed'],1)*100)}%)"
    )
    
    await message.answer(text)
```

---

# 🛡️ MIDDLEWARE: АНТИСПАМ И RATE LIMITING

```python
# middlewares/throttle.py

from aiogram import BaseMiddleware
from aiogram.types import Update
import time


class ThrottleMiddleware(BaseMiddleware):
    """
    Rate limiting через Redis.
    Не более 3 сообщений в секунду от одного пользователя.
    """
    
    def __init__(self, redis, rate_limit: float = 0.3):
        self.redis = redis
        self.rate_limit = rate_limit  # Минимальный интервал между сообщениями
    
    async def __call__(self, handler, event: Update, data: dict):
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)
        
        key = f"throttle:{user.id}"
        now = time.time()
        
        last_time = await self.redis.get(key)
        if last_time and (now - float(last_time)) < self.rate_limit:
            return  # Игнорируем спам
        
        await self.redis.set(key, str(now), ex=60)
        return await handler(event, data)
```

---

# 🚀 ТОЧКА ВХОДА: bot.py (Gunicorn-совместимый)

> **⚠️ В bot.py НЕТ APScheduler!** Scheduler живёт в worker.py.
> bot.py запускается через Gunicorn с 4-8 воркерами.

```python
# bot.py — ПСЕВДОКОД СТРУКТУРЫ
# Запуск: gunicorn bot:app --worker-class aiohttp.GunicornWebWorker --workers 4

import logging
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

import asyncpg
import redis.asyncio as aioredis

from config import *
from handlers import start, quest, contacts, arena, payment, admin
from handlers.payment_webhook import yookassa_webhook_handler
from middlewares.throttle import ThrottleMiddleware
from middlewares.activity import ActivityMiddleware
from middlewares.db_middleware import DatabaseMiddleware
from utils.content_manager import ContentManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Загружаем тексты в ОЗУ при импорте модуля (один раз на воркер)
ContentManager.load("content/texts.json")


async def on_startup(app: web.Application):
    """Действия при запуске каждого воркера"""
    # Подключения (каждый воркер создаёт свой пул)
    pool = await asyncpg.create_pool(
        DB_DSN,
        min_size=DB_POOL_MIN,
        max_size=DB_POOL_MAX,
        command_timeout=10
    )
    redis_conn = aioredis.from_url(REDIS_URL, decode_responses=True)
    storage = RedisStorage(redis=aioredis.from_url(REDIS_URL))
    
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=storage)
    
    # Middleware
    dp.update.middleware(DatabaseMiddleware(pool))
    dp.update.middleware(ThrottleMiddleware(redis_conn))
    dp.update.middleware(ActivityMiddleware(redis_conn))
    
    # Роутеры
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(quest.router)
    dp.include_router(contacts.router)
    dp.include_router(arena.router)
    dp.include_router(payment.router)
    
    # ⚠️ Безопасный старт: проверяем текущий webhook ПЕРЕД установкой.
    # 4 воркера Gunicorn стартуют одновременно. Без этой проверки все 4 отправят
    # setWebhook → Telegram может ответить 429 и временно забанить токен.
    webhook_url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
    current_wh = await bot.get_webhook_info()
    if current_wh.url != webhook_url:
        await bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET,   # ← БЕЗОПАСНОСТЬ: Telegram будет слать этот токен в заголовке
            drop_pending_updates=True,
            max_connections=100
        )
        logger.info(f"Webhook set: {webhook_url}")
    else:
        logger.info("Webhook already configured, skipping set_webhook")
    
    # Webhook handler от Telegram (с проверкой secret_token)
    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET    # ← Проверяет X-Telegram-Bot-Api-Secret-Token
    )
    webhook_handler.register(app, path=WEBHOOK_PATH)
    
    # Сохраняем в app для доступа из других handlers
    app['pool'] = pool
    app['bot'] = bot
    app['redis'] = redis_conn
    app['dp'] = dp
    
    setup_application(app, dp, bot=bot)
    logger.info("Worker started successfully")


async def on_shutdown(app: web.Application):
    """Действия при остановке воркера"""
    bot = app.get('bot')
    pool = app.get('pool')
    redis_conn = app.get('redis')
    
    # ⚠️ НЕ вызываем bot.delete_webhook()!
    # Gunicorn может перезапустить один воркер (graceful reload).
    # Если воркер при остановке удалит webhook — бот сломается для ВСЕХ воркеров.
    # Webhook удаляется только явно через админскую команду.
    
    if bot:
        await bot.session.close()
    if redis_conn:
        await redis_conn.close()
    if pool:
        await pool.close()
    logger.info("Worker stopped")


# Создаём aiohttp Application (Gunicorn подхватывает это)
app = web.Application()
app.router.add_post("/yookassa/webhook", yookassa_webhook_handler)
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)
```

---

# 🔄 WORKER.PY (Scheduler + Рассылки)

> **⚠️ ЗАПУСКАЕТСЯ СТРОГО В 1 ЭКЗЕМПЛЯРЕ через hydra-worker.service!**
> Если запустить несколько — рассылки уйдут по N раз.

```python
# worker.py — ПСЕВДОКОД СТРУКТУРЫ
# Запуск: python worker.py (через systemd, НЕ через Gunicorn!)

import asyncio
import logging

from aiogram import Bot
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import asyncpg
import redis.asyncio as aioredis

from config import *
from services.followup_service import check_idle_users, send_daily_miniquest
from utils.content_manager import ContentManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

ContentManager.load("content/texts.json")


async def main():
    # Подключения
    pool = await asyncpg.create_pool(DB_DSN, min_size=2, max_size=5)
    redis_conn = aioredis.from_url(REDIS_URL, decode_responses=True)
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    
    # Scheduler
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    
    # Проверка зависших пользователей — каждые 60 сек
    scheduler.add_job(
        check_idle_users, 'interval', seconds=60,
        args=[bot, pool, redis_conn],
        id='check_idle', replace_existing=True
    )
    
    # Миниквесты — каждый день в 11:00 МСК
    scheduler.add_job(
        send_daily_miniquest, 'cron', hour=11, minute=0,
        args=[bot, pool, redis_conn],  # ⚠️ redis_conn нужен для media_service (file_id кэш)
        id='daily_miniquest', replace_existing=True
    )
    
    scheduler.start()
    logger.info("Worker started: scheduler running")
    
    try:
        await asyncio.Event().wait()  # Бесконечный цикл
    finally:
        scheduler.shutdown()
        await pool.close()
        await bot.session.close()
        logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
```

---

# 🌐 ДЕПЛОЙ НА FIRSTFVDS

## 1. Скрипт первоначальной настройки (`deploy/setup.sh`)

```bash
#!/bin/bash
# Запуск: sudo bash deploy/setup.sh

set -e

echo "=== HYDRA BOT: Настройка сервера ==="

# Обновление системы
apt update && apt upgrade -y

# Установка зависимостей
apt install -y python3.12 python3.12-venv python3-pip \
    postgresql-16 postgresql-contrib \
    redis-server \
    nginx \
    certbot python3-certbot-nginx \
    git htop

# PostgreSQL
sudo -u postgres psql -c "CREATE USER hydra WITH PASSWORD 'CHANGE_ME_STRONG_PASSWORD';"
sudo -u postgres psql -c "CREATE DATABASE hydra_bot OWNER hydra;"

# Redis — включаем persistence
sed -i 's/# save 3600 1/save 300 10/' /etc/redis/redis.conf
# Redis — увеличиваем max memory для production
echo "maxmemory 256mb" >> /etc/redis/redis.conf
echo "maxmemory-policy allkeys-lru" >> /etc/redis/redis.conf
systemctl restart redis

# Создаём директорию проекта
mkdir -p /opt/hydra_bot
cd /opt/hydra_bot

# Python venv
python3.12 -m venv venv
source venv/bin/activate

# Зависимости
pip install -r requirements.txt

# Генерируем WEBHOOK_SECRET
echo "WEBHOOK_SECRET=$(openssl rand -hex 32)" >> .env.example

echo "=== Готово! Далее: ==="
echo "1. Скопируй .env.example в .env и заполни"
echo "2. Примени схему: psql -U hydra hydra_bot < schema.sql"
echo "3. Настрой NGINX, systemd"
echo "4. Запусти: systemctl start hydra-bot hydra-worker"
```

## 2. NGINX конфигурация (`deploy/nginx.conf`)

```nginx
# /etc/nginx/sites-available/hydra-bot

# ⚠️ НЕТ limit_req_zone! Telegram шлёт запросы с ограниченного пула IP.
# Rate limit NGINX заблокирует серверы Telegram при наплыве трафика.
# Антиспам пользователей реализован внутри кода (ThrottleMiddleware).

server {
    listen 443 ssl http2;
    server_name bot.neurounit.fun;

    ssl_certificate /etc/letsencrypt/live/bot.neurounit.fun/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bot.neurounit.fun/privkey.pem;

    # Webhook от Telegram — ТОЛЬКО с IP-адресов Telegram!
    location /webhook/ {
        # Белый список IP Telegram (актуальные подсети)
        allow 149.154.160.0/20;
        allow 91.108.4.0/22;
        allow 91.108.8.0/22;
        allow 91.108.12.0/22;
        allow 91.108.16.0/22;
        allow 91.108.20.0/22;
        allow 91.108.56.0/22;
        deny all;
        
        proxy_pass http://127.0.0.1:8443;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_read_timeout 30s;
        proxy_connect_timeout 5s;
    }

    # Webhook от YooKassa — ТОЛЬКО с IP YooKassa
    location /yookassa/ {
        # IP-адреса YooKassa (проверить актуальные в документации)
        allow 185.71.76.0/27;
        allow 185.71.77.0/27;
        allow 77.75.153.0/25;
        allow 77.75.156.11;
        allow 77.75.156.35;
        allow 77.75.154.128/25;
        deny all;
        
        proxy_pass http://127.0.0.1:8443;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Запрет доступа ко всему остальному
    location / {
        return 444;
    }
}

# Редирект HTTP → HTTPS
server {
    listen 80;
    server_name bot.neurounit.fun;
    return 301 https://$host$request_uri;
}
```

## 3. Systemd units

### `deploy/hydra-bot.service` — Webhook-сервер (Gunicorn)

```ini
# /etc/systemd/system/hydra-bot.service

[Unit]
Description=HYDRA Quest Telegram Bot (Webhook Server)
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/hydra_bot
ExecStart=/opt/hydra_bot/venv/bin/gunicorn bot:app \
    --worker-class aiohttp.GunicornWebWorker \
    --workers 4 \
    --bind 127.0.0.1:8443 \
    --timeout 30 \
    --graceful-timeout 10 \
    --access-logfile - \
    --error-logfile -
Restart=always
RestartSec=5
StartLimitIntervalSec=60
StartLimitBurst=5

EnvironmentFile=/opt/hydra_bot/.env

# Безопасность
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=/opt/hydra_bot

[Install]
WantedBy=multi-user.target
```

### `deploy/hydra-worker.service` — Scheduler + Рассылки (ОДИН экземпляр!)

```ini
# /etc/systemd/system/hydra-worker.service
#
# ⚠️ КРИТИЧНО: Этот процесс запускается СТРОГО В ОДНОМ ЭКЗЕМПЛЯРЕ.
# Если запустить несколько — пользователи получат рассылки по N раз!

[Unit]
Description=HYDRA Quest Worker (Scheduler + Broadcasts)
After=network.target postgresql.service redis.service hydra-bot.service
Requires=postgresql.service redis.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/hydra_bot
ExecStart=/opt/hydra_bot/venv/bin/python worker.py
Restart=always
RestartSec=10

EnvironmentFile=/opt/hydra_bot/.env

NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=/opt/hydra_bot

WatchdogSec=60

[Install]
WantedBy=multi-user.target
```

## 4. Запуск

```bash
# SSL-сертификат
certbot --nginx -d bot.neurounit.fun

# Включаем NGINX
ln -s /etc/nginx/sites-available/hydra-bot /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Создаём БД
sudo -u postgres psql hydra_bot < /opt/hydra_bot/schema.sql

# Запускаем ДВА сервиса
systemctl daemon-reload
systemctl enable hydra-bot hydra-worker
systemctl start hydra-bot
systemctl start hydra-worker

# Проверка
systemctl status hydra-bot
systemctl status hydra-worker
journalctl -u hydra-bot -f      # Логи webhook-сервера
journalctl -u hydra-worker -f   # Логи scheduler/рассылок
```

---

# 📦 ЗАВИСИМОСТИ

## `requirements.txt`

```
# Core
aiogram==3.14.0
aiohttp==3.10.0
gunicorn==22.0.0

# Database
asyncpg==0.30.0

# Redis
redis[hiredis]==5.2.0

# FSM Storage
# (встроен в aiogram, используется redis)

# Scheduler
APScheduler==3.10.4

# Payments
yookassa==3.4.0

# Utils
python-dotenv==1.0.1
pydantic==2.10.0

# Logging
structlog==24.4.0
```

---

# 📊 СОБЫТИЯ ДЛЯ АНАЛИТИКИ

Каждое значимое действие пользователя записывается в таблицу `events`:

| Событие | Когда | Данные |
|---------|-------|--------|
| `bot_start` | /start | `{utm_source}` |
| `quest_start` | Нажал "Квест" | — |
| `class_selected` | Выбрал класс | `{class: "businessman"}` |
| `weapon_selected` | Выбрал оружие | `{weapon: "marketing"}` |
| `round_completed` | Ответил на раунд | `{round: 1, correct: true, score: 1}` |
| `quest_completed` | Завершил все 3 раунда | `{score: 2}` |
| `contact_phone` | Ввёл телефон | `{phone: "+7..."}` |
| `workshop_registered` | Записался на воркшоп | — |
| `upsell_shown` | Показали оффер разбора | `{remaining_slots: 7}` |
| `payment_created` | Создал платёж | `{payment_id: "..."}` |
| `payment_succeeded` | Оплатил | `{amount: 5000}` |
| `payment_canceled` | Отменил платёж | — |
| `followup_idle_sent` | Отправлен "завис на шаге" | `{state: "round_2"}` |
| `followup_miniquest_sent` | Отправлен миниквест | `{day: 3}` |
| `followup_miniquest_answered` | Ответил на миниквест | `{day: 3, correct: true}` |
| `arena_start` | Нажал "Арена" | — |
| `arena_registered` | Записался на арену | — |

---

# 🧪 ТЕСТИРОВАНИЕ

## Ручное тестирование через админ-команды

```
1. /reset_user <свой_id>      — сбросить себя, пройти квест заново
2. /reset_all                  — сбросить всех (перед запуском трафика)
3. /stats                      — проверить что статистика считается
4. /slots                      — проверить каунтер мест
```

## Тестирование YooKassa

YooKassa предоставляет тестовый режим. Для тестов использовать:
- Тестовый `YOOKASSA_SECRET_KEY` (префикс `test_`)
- Тестовые карты: `4111 1111 1111 1111` (успех), `4100 0000 0000 0015` (отклонение)

## Нагрузочное тестирование

```bash
# Установить locust
pip install locust

# Базовый тест: 1000 параллельных пользователей шлют /start
locust -f tests/loadtest.py --headless -u 1000 -r 100 --run-time 5m
```

---

# ✅ ЧЕК-ЛИСТ ЗАПУСКА

## Этап 1: Подготовка сервера (1-2 часа)

- [ ] Подключиться к FirstVDS (SSH)
- [ ] Запустить `deploy/setup.sh`
- [ ] Настроить PostgreSQL (пароль, доступ)
- [ ] Проверить Redis (`redis-cli ping`)
- [ ] Получить SSL-сертификат (certbot)

## Этап 2: Настройка бота (30 мин)

- [ ] Создать бота через @BotFather
- [ ] Получить токен
- [ ] Сгенерировать WEBHOOK_SECRET: `openssl rand -hex 32`
- [ ] Создать `.env` из `.env.example`
- [ ] Настроить YooKassa (shop_id, secret_key, webhook URL: `https://bot.neurounit.fun/yookassa/webhook`)

## Этап 3: Разработка ядра (в Cursor)

- [ ] `config.py` + `db.py` + `redis_client.py`
- [ ] `models/user.py` + `models/payment.py`
- [ ] `schema.sql` (создание таблиц с нуля)
- [ ] `utils/config_db.py` (get_config для чтения таблицы config!)
- [ ] `utils/content_manager.py` (ContentManager → content/texts.json)
- [ ] `utils/statements.py` + `utils/validation.py`
- [ ] `content/texts.json` (ВСЕ тексты бота — НЕ хардкод!)
- [ ] `utils/media_ids.py` (MINIQUEST_FILE_IDS для миниквестов, если нужны картинки)
- [ ] `keyboards/inline.py`
- [ ] `handlers/start.py`
- [ ] `handlers/quest.py`
- [ ] `handlers/contacts.py`
- [ ] `handlers/arena.py`
- [ ] `handlers/upsell.py` (единая функция show_upsell_if_available)
- [ ] `handlers/payment.py` + `handlers/payment_webhook.py`
- [ ] `handlers/admin.py` (redis_conn инжектируется через middleware!)
- [ ] `middlewares/throttle.py` + `middlewares/activity.py` + `middlewares/db_middleware.py`
- [ ] `services/quest_service.py`
- [ ] `services/payment_service.py` (с Redis HOLD + get_config!)
- [ ] `services/media_service.py` (file_id кэш в Redis, НЕ FSInputFile в рассылках!)
- [ ] `services/followup_service.py` (media_service + ContentManager + rate limit + finally!)
- [ ] `services/broadcast_service.py`
- [ ] `services/notification_service.py`
- [ ] `bot.py` (Gunicorn-совместимый, БЕЗ scheduler, БЕЗ delete_webhook в shutdown!)
- [ ] `worker.py` (scheduler, ОТДЕЛЬНЫЙ процесс!)

## Этап 4: Деплой (30 мин)

- [ ] Загрузить код на сервер (git clone или scp)
- [ ] Запустить `schema.sql` для создания таблиц
- [ ] Настроить NGINX (whitelist IP Telegram + YooKassa!)
- [ ] Запустить `hydra-bot.service` (Gunicorn, 4 воркера)
- [ ] Запустить `hydra-worker.service` (scheduler, 1 экземпляр!)
- [ ] Проверить nginx → webhook → бот
- [ ] Настроить webhook YooKassa в личном кабинете

## Этап 5: Тестирование (1-2 часа)

- [ ] Пройти квест от начала до конца
- [ ] Проверить upsell и оплату (тестовый режим YooKassa)
- [ ] Проверить что hold слота работает (выдача ссылки → 15 мин → слот возвращается)
- [ ] `/reset_user` — пройти заново
- [ ] Проверить что рядовой пользователь НЕ может сбросить себе прогресс
- [ ] Проверить дожим idle (поставить FOLLOWUP_IDLE_MINUTES=1 для теста)
- [ ] Проверить миниквесты (вручную вызвать send_daily_miniquest)
- [ ] Проверить upsell после миниквеста (записаться на воркшоп из followup → увидеть оффер)
- [ ] `/stats` — проверить аналитику
- [ ] Проверить что `hydra-worker.service` запущен в 1 экземпляре
- [ ] Нагрузочный тест (locust, 1000 пользователей)

## Этап 6: Боевой запуск

- [ ] Переключить YooKassa на LIVE-ключ
- [ ] Вернуть FOLLOWUP_IDLE_MINUTES=5
- [ ] `/reset_all` — чистый старт
- [ ] Запустить трафик из TikTok
- [ ] Мониторинг: `journalctl -u hydra-bot -f` + `journalctl -u hydra-worker -f`

---

# 🔮 БУДУЩИЕ МОДУЛИ (не в MVP)

| Модуль | Описание | Когда добавлять |
|--------|----------|-----------------|
| **Google Sheets** | Экспорт лидов в таблицу для менеджеров | Когда будет команда продаж |
| **Graspil / GA4** | Детальная аналитика воронки | Когда пойдёт платный трафик |
| **Реферальная система** | "Приведи друга" для вирального роста | После валидации воронки |
| **Мультиязычность** | EN/TR для международного трафика | При выходе за пределы РФ |
| **A/B тестирование** | Разные тексты/офферы для сегментов | При оптимизации конверсий |
| **Химера Хаоса** | Бонусный квест (расширение лора) | Для реактивации старых лидов |

---

# 📝 ЗАМЕТКИ ДЛЯ РАЗРАБОТКИ В CURSOR

## Порядок генерации файлов

```
1. config.py                    — Настройки из .env (включая WEBHOOK_SECRET!)
2. db.py                        — Подключение к PostgreSQL + pool
3. redis_client.py              — Подключение к Redis
4. schema.sql                   — Создание таблиц (НЕ миграция!)
5. models/user.py               — Pydantic-модели
6. utils/config_db.py           — get_config() для чтения таблицы config (⚠️ КРИТИЧНО для платежей!)
7. utils/content_manager.py     — ContentManager (загружает content/texts.json)
8. content/texts.json           — ВСЕ тексты бота (НЕ хардкод в .py!)
9. utils/statements.py          — Загрузка утверждений
10. utils/validation.py         — Валидация телефона
11. keyboards/inline.py         — Все кнопки
12. services/media_service.py   — Кэширование file_id в Redis (⚠️ ЗАПРЕЩЁН FSInputFile в рассылках!)
13. services/*                  — Бизнес-логика (payment с HOLD + get_config!)
14. middlewares/*               — Throttle, Activity (Redis!), DB + Redis injection
15. handlers/start.py           — Стартовый хендлер
16. handlers/quest.py           — Логика квеста
17. handlers/contacts.py        — Сбор контактов
18. handlers/upsell.py          — Единая функция upsell
19. handlers/payment.py         — YooKassa создание платежа
20. handlers/payment_webhook.py — Обработка webhook YooKassa
21. handlers/admin.py           — Админ-команды (redis_conn через middleware!)
22. bot.py                      — Gunicorn app (БЕЗ scheduler! БЕЗ delete_webhook в shutdown!)
23. worker.py                   — Scheduler (ОТДЕЛЬНЫЙ процесс!)
```

## Промпт для Cursor (стартовый)

```
Ты — senior Python developer. Создай Telegram-бота по следующему ТЗ.

Стек: aiogram 3.14 (webhook mode), asyncpg (PostgreSQL), redis, Gunicorn, APScheduler, YooKassa SDK.
Сервер: Ubuntu 24.04, NGINX как reverse proxy.
Нагрузка: до 10 000 параллельных пользователей.

Архитектура: handlers/ → services/ → db.py (asyncpg pool).
FSM хранится в Redis через aiogram RedisStorage.
Антиспам через Redis rate limiting.

КРИТИЧЕСКИЕ АРХИТЕКТУРНЫЕ ПРАВИЛА (v7.6):
1. YooKassa HOLD: Резервирование слота через атомарный Lua-скрипт в Redis ПЕРЕД генерацией ссылки. Ссылка только если (Оплаченные + В холде) < 10.
2. Рассылки: asyncio.sleep(0.05) между msg, TelegramRetryAfter, UPDATE в finally.
3. NGINX: НЕТ limit_req для webhook! Только whitelist IP Telegram.
4. Gunicorn 4 воркера + ОТДЕЛЬНЫЙ worker.py для APScheduler (1 экземпляр!).
5. Активность в Redis (SETEX с TTL), НЕ в PostgreSQL.
6. secret_token при установке Telegram Webhook.
7. Сброс прогресса: ТОЛЬКО админ. Юзер НЕ МОЖЕТ.
8. Upsell при ЛЮБОМ workshop_registered = TRUE.
9. ЗАПРЕЩЕНО: redis.keys(), redis.exists() в цикле. Используй Lua + Sorted Set, MGET.
10. ЗАПРЕЩЕНО: Check-Then-Act двумя командами Redis. Только атомарный Lua.
11. yookassa SDK синхронный! ВСЕ вызовы Payment.create/Refund.create — через asyncio.to_thread().
12. Зомби-платежи: в webhook PAYMENT_SUCCEEDED проверяй COUNT(succeeded). Если 10/10 — auto Refund.create + уведомление.
13. Идемпотентность webhook: UPDATE ... WHERE status != 'succeeded' RETURNING id.
14. on_startup: сначала get_webhook_info(), set_webhook ТОЛЬКО если URL не совпадает.
15. DB_POOL_MAX = 10 (4 воркера × 10 = 40 < PG default 100).
16. КОНТЕНТ: Никакого хардкода текстов в .py файлах. Использовать ContentManager (читает content/texts.json в ОЗУ при старте). Все динамические переменные оборачивать в html.quote(). Тексты обновляются без перезапуска кода — достаточно перезапустить воркер.
17. МЕДИА: СТРОГО ЗАПРЕЩЁН FSInputFile в циклах рассылок. Используй media_service.py для кэширования file_id в Redis через скрытую отправку админу. В рассылке слать только file_id хэш!
18. REDIS SCAN: ЗАПРЕЩЕНО redis.scan(0) одним вызовом. Только scan_iter() (автоматическая итерация всех батчей курсора).
19. ON_SHUTDOWN: НЕ вызывать bot.delete_webhook() в on_shutdown. При graceful reload Gunicorn один воркер убьёт webhook для всех остальных.

[Вставь конкретный файл из чек-листа]

Требования:
- Весь I/O — асинхронный (синхронные SDK → asyncio.to_thread!)
- Все операции с БД через connection pool (DB_POOL_MAX=10)
- Обработка ошибок на каждом шаге
- Logging через structlog
- Type hints везде
- Redis: никаких KEYS, никаких exists() в цикле, никаких scan(0) без итерации
- Тексты: через ContentManager (content/texts.json), НЕ хардкод
- Медиа в рассылках: через media_service (file_id из Redis), НЕ FSInputFile
```

---

**🚀 ДОКУМЕНТ ГОТОВ К PRODUCTION-РАЗРАБОТКЕ**

Версия: 7.4 (Production MVP — Telegram-First Contacts)  
Дата: 04 марта 2026  
Сервер: FirstVDS (bot.neurounit.fun / 82.146.39.44)  
Среда разработки: Cursor AI  
Архитектура: Gunicorn (4 воркера) + worker.py (scheduler) + NGINX (IP whitelist) + Redis (HOLD, activity, FSM, file_id cache)
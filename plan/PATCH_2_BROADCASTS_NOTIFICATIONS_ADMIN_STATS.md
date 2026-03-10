# 🐉 PATCH 2: Рассылки, уведомления, админка и статистика

## Техническое Задание — Patch 2 (отдельный документ)

---

# ✅ ТЕКУЩИЙ СТАТУС РЕАЛИЗАЦИИ (бот)

- Реализован HTTP API на стороне бота: `/api/admin/*`, `/api/webhook/site`
- Реализована auth-модель `X-Admin-Secret` / `X-Site-Secret` + rate limit
- Реализованы сегменты и рассылка через API + scheduled queue (worker job)
- Реализованы лиды: список, заметки, статусы
- Реализован сбор `button_click` метрик (middleware)
- Реализован executor правил уведомлений для триггеров: `scheduled_once`, `scheduled_recurring`
- Реализован sandbox/prod anti-mixup контур деплоя

Осталось на стороне сайта:
- UI neurounit.fun/admin (формы, таблицы, страницы)
- Интеграция API вызовов к боту (backend-to-backend)

Осталось на стороне бота (следующая итерация):
- trigger executor для `event`, `days_before_date`, `relative_days`

---

# 📌 МЕТА-ИНФОРМАЦИЯ

| Параметр | Значение |
|----------|----------|
| **Базовый документ** | TZ.md v7.7 |
| **Дата** | 04 марта 2026 |
| **Цель Patch** | Массовые рассылки, автоуведомления, админ-уведомления, единая админка со статистикой и Graspil |
| **Единая админка** | **neurounit.fun/admin** — все функции (лендинг + бот) в одном месте |
| **Спецификация админки** | `plan/UNIFIED_ADMIN_SPEC.md` |
| **Ограничения** | Архитектура под нагрузку, без конфликтов с текущей системой, безопасный деплой с откатом и защищённым бекапом |

---

# 🔺 СВЯЗЬ С ТЕКУЩЕЙ СИСТЕМОЙ

## Что уже есть (не трогаем)

| Компонент | Описание |
|-----------|----------|
| `followup_service.py` | Idle-напоминание (1 раз), 5-дневные миниквесты |
| `broadcast_service.py` | Рассылка всем `is_blocked=FALSE`, `asyncio.sleep(0.05)`, `TelegramRetryAfter`/`TelegramForbiddenError` |
| `worker.py` | APScheduler: `check_idle_users` (60 сек), `send_daily_miniquest` (11:00 МСК) |
| `utils/notifications.py` | `notify_admins`, `notify_new_contact`, `notify_arena_lead`, `notify_error` |
| `events` | Таблица для логирования: `user_id`, `event_type`, `event_data` (JSONB) |
| `handlers/admin.py` | `/stats`, `/slots`, `/reset_user`, `/reset_all`, `/broadcast`, `/export_leads` |

## Что добавляем (без конфликтов)

| Компонент | Описание |
|-----------|----------|
| **Единая админка** | **neurounit.fun/admin** — лендинг + бот. Рассылки, автоуведомления, лиды, статистика. См. `UNIFIED_ADMIN_SPEC.md` |
| **API бота для админки** | Эндпоинты `/api/admin/*` с авторизацией `X-Admin-Secret` — лендинг дергает бота |
| **Массовые рассылки** | Запуск из neurounit.fun/admin: текст, сегмент, дата/время, превью |
| **Автоуведомления** | Настройка в админке: текст, сегмент, триггер, расписание |
| **Хранение лидов** | CRM-слой: статусы, заметки, фильтры. Объединённый вид (лендинг + бот) |
| **Интеграция с сайтом** | Webhook: оплата на сайте → уведомление в Telegram |
| **Уведомления админам** | user_stuck, bot_down, critical_error |
| **Статистика** | Воронка, Graspil, клики по кнопкам |
| **Бекап/откат** | Защищённый бекап, процедура отката |

---

# 🏗️ АРХИТЕКТУРА PATCH 2

## Обзор изменений

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ЕДИНАЯ АДМИНКА: neurounit.fun/admin                                         │
│  Лендинг (Flask) + данные бота по API. Рассылки, автоуведомления, лиды.       │
└─────────────────────────────────────────────────────────────────────────────┘
         │                                    │
         │ /admin/api/leads                    │ GET/POST {BOT_API_URL}/api/admin/*
         │ (локально)                          │ X-Admin-Secret
         ▼                                    ▼
┌──────────────────────────────┐    ┌──────────────────────────────────────────┐
│  ЛЕНДИНГ (neurounit.fun)     │    │  TELEGRAM-БОТ (bot.neurounit.fun)         │
│  Flask + SQLite (leads.db)   │    │  followup │ broadcast │ worker │ events  │
└──────────────────────────────┘    └──────────────────────────────────────────┘
                                                    │
                                                    ▼
                                    ┌──────────────────────────────────────────┐
                                    │  API бота для админки                     │
                                    │  /api/admin/stats, /funnel, /leads,        │
                                    │  /broadcast, /notification-rules          │
                                    │  lead_notes, lead_statuses                 │
                                    │  POST /api/webhook/site (оплата → TG)     │
                                    └──────────────────────────────────────────┘
```

---

# 1. ЕДИНАЯ АДМИНКА (neurounit.fun/admin)

## 1.1 Принцип

Вся админка — на **neurounit.fun/admin**. Лендинг (Flask) рендерит UI, данные бота получает по API. Один логин/пароль для всего.

**Спецификация:** `plan/UNIFIED_ADMIN_SPEC.md`

### Роль бота

Бот **не** рендерит админку. Бот предоставляет **HTTP API** для чтения/записи данных. Лендинг при загрузке страниц админки вызывает `GET {BOT_API_URL}/api/admin/*` с заголовком `X-Admin-Secret`.

### Структура админки (на лендинге)

```
neurounit.fun/admin
    │
    ├── Дашборд (счётчики лендинга + счётчики бота)
    │
    ├── 📤 Рассылки (данные из бота)
    │   ├── Новая рассылка (форма → POST к боту)
    │   ├── Запланированные
    │   └── История
    │
    ├── ⏰ Автоуведомления (данные из бота)
    │   ├── Список правил (GET от бота)
    │   └── Форма: создать/редактировать (POST/PUT к боту)
    │
    ├── 👥 Лиды (объединённые: лендинг + бот)
    │   ├── Таблица с источником: «Лендинг · Оферта», «Бот · Квест» и т.д.
    │   ├── Фильтры, поиск, статусы, заметки (для лидов бота)
    │   └── Карточка лида
    │
    ├── 📊 Статистика
    │   ├── Воронка бота (GET от бота)
    │   └── Ссылка на Graspil
    │
    └── Блоки лендинга (уже есть): квиз, кнопки, индекс вовлечённости
```

### Команды в боте (/stats, /broadcast и т.д.)

Остаются для быстрого доступа из Telegram (например, в поездке). Но **основной** интерфейс — neurounit.fun/admin.

---

# 2. МАССОВЫЕ РАССЫЛКИ (запуск из админки)

## 2.1 Механизм no-code

1. Админ нажимает «Новая рассылка» в админке.
2. Заполняет форму:
   - **Текст** — многострочное поле (поддержка HTML)
   - **Сегмент** — выпадающий список (см. ниже)
   - **Когда отправить** — «Сейчас» или «В указанное время» (дата + время)
3. Нажимает «Запустить» или «Запланировать».
4. Система показывает превью: «Будет отправлено ~N пользователям».
5. При «Сейчас» — лендинг шлёт POST к боту, бот запускает рассылку в фоне. Результат можно показать в админке (polling или webhook) или дублировать админу в Telegram.

### API бота (вызывается neurounit.fun/admin)

Админка на лендинге дергает бота. Все запросы: `X-Admin-Secret: {ADMIN_API_SECRET}`.

```
POST {BOT_API_URL}/api/admin/broadcast
  - text: string
  - segment_id: string
  - scheduled_at: datetime | null (null = сейчас)
  - preview: boolean (только посчитать, не слать)

Response: { total_recipients, status: "queued"|"scheduled", scheduled_at? }
```

Полный контракт API бота — в `UNIFIED_ADMIN_SPEC.md`.

### Сегменты пользователей

На основе данных `users`, `payments`, `events`:

| ID | Название | Описание | Источник данных |
|----|---------|----------|-----------------|
| `all` | Все активные | Не заблокировали бота | `is_blocked = FALSE` |
| `visitors` | Зашли в бота | Хотя бы /start | `event_type = 'bot_start'` |
| `quest_started` | Начали квест | Нажали «Начать квест» | `event_type = 'quest_start'` |
| `quest_in_progress` | В процессе квеста | Не завершили, не на start | `quest_completed = FALSE AND quest_state NOT IN ('start', 'completed')` |
| `quest_completed` | Завершили квест | Прошли 3 раунда | `quest_completed = TRUE` |
| `workshop_registered` | Записались на воркшоп | Оставили контакты после квеста | `workshop_registered = TRUE` |
| `not_workshop` | Прошли квест, не записались | Кандидаты на дожим | `quest_completed = TRUE AND workshop_registered = FALSE` |
| `arena_only` | Только арена | Записались на арену, квест не проходили | `arena_registered = TRUE AND quest_completed = FALSE` |
| `has_phone` | Оставили телефон | Лиды (квест или арена) | `phone IS NOT NULL` |
| `paid` | Оплатили | Успешная оплата | `EXISTS (SELECT 1 FROM payments WHERE user_id = users.user_id AND status = 'succeeded')` |
| `followup_day1` | День 1 дожима | Первый день миниквестов | `followup_stage = 0 AND quest_completed AND NOT workshop_registered` |
| `followup_day2_5` | Дни 2–5 дожима | Активный дожим | `followup_stage BETWEEN 1 AND 4` |
| `by_class_*` | По классу | businessman / creator / analyst / manager | `player_class = ?` |
| `by_weapon_*` | По оружию | marketing / analytics / copywriting / design / management / video | `weapon = ?` |
| `by_utm_*` | По источнику | utm_tiktok, utm_telegram и т.д. | `utm_source = ?` |
| `registered_after` | Зарегистрировались после | Когорта по дате | `created_at >= ?` |

Сегменты `by_class_*`, `by_weapon_*`, `by_utm_*` — динамические: список значений берётся из БД (DISTINCT).

### Критические правила (из TZ v7.7)

- `asyncio.sleep(0.05)` между сообщениями
- `TelegramRetryAfter` → `await asyncio.sleep(e.retry_after)`
- `TelegramForbiddenError` → `UPDATE is_blocked = TRUE` в `finally`
- Никаких `redis.keys()` / `redis.exists()` в циклах

---

# 3. АВТОУВЕДОМЛЕНИЯ (настройка в админке)

## 3.1 Настройка через админку (no-code)

Каждое автоуведомление — **правило**, которое админ создаёт и редактирует в интерфейсе.

### Форма создания/редактирования правила

| Поле | Тип | Описание |
|------|-----|----------|
| **Название** | Текст | Например: «Урок начался», «Курс скоро» |
| **Текст сообщения** | Многострочный | Поддержка HTML, плейсхолдеры: `{first_name}`, `{phone}` |
| **Сегмент** | Выпадающий | Те же сегменты, что и для рассылок |
| **Триггер** | Выпадающий | См. раздел 3.2 |
| **Расписание** | — | Зависит от триггера (дата, время, регулярность) |
| **Включено** | Чекбокс | Вкл/выкл без удаления |

### Триггеры (что можно заложить уже сейчас)

| Триггер | Описание | Параметры настройки | Когда срабатывает |
|---------|----------|---------------------|-------------------|
| **event** | Событие в боте | `event_type`: workshop_registered, payment_succeeded, quest_completed, arena_registered | Сразу после события |
| **scheduled_once** | Один раз в указанное время | Дата + время (МСК) | В указанный момент |
| **scheduled_recurring** | Регулярно по расписанию | День недели (0–6) или «ежедневно» + время HH:MM | Каждый день/неделю в это время |
| **relative_days** | N дней после события | Событие + число дней (1, 3, 7…) | N дней после того, как пользователь попал в сегмент |
| **days_before_date** | За N дней до даты | Дата события (старт курса) + число дней | За N дней до даты всем из сегмента |

### Примеры правил

| Название | Триггер | Сегмент | Расписание |
|----------|---------|---------|-----------|
| Вы записаны на курс | event: workshop_registered | — (определяется событием) | — |
| Оплата прошла | event: payment_succeeded | — | — |
| Урок начался | scheduled_recurring | workshop_registered | Ежедневно 19:00 |
| Курс через 3 дня | days_before_date | workshop_registered | Дата курса: 2026-03-15, за 3 дня |
| Напоминание через 2 дня | relative_days | quest_completed, not workshop | 2 дня после quest_completed |

### Регулярность (для scheduled_recurring)

- **Каждые N часов** — опционально (для напоминаний): «каждые 6 часов» — редко нужно, но можно заложить.
- **Каждый день в HH:MM** — основной кейс: «каждый день в 11:00», «каждый день в 19:00».
- **Каждый понедельник в HH:MM** — по дням недели.

Формат в БД: `cron_expr` (например `0 19 * * *` = ежедневно 19:00) или `{ "hour": 19, "minute": 0, "days": [0,1,2,3,4,5,6] }`.

### Таблица правил (БД)

```sql
CREATE TABLE IF NOT EXISTS notification_rules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    text_template TEXT NOT NULL,
    segment_id VARCHAR(50) NOT NULL,
    trigger_type VARCHAR(50) NOT NULL,  -- event, scheduled_once, scheduled_recurring, relative_days, days_before_date
    trigger_config JSONB DEFAULT '{}',  -- event_type, cron, date, days, etc.
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Дедупликация

- Для `event` — один раз на пользователя (событие уникально).
- Для `scheduled_recurring` — логировать `notification_sent:{rule_id}:{user_id}:{date}` в Redis или events, не слать повторно в тот же день.
- Для `days_before_date` — `course_soon_sent` в users или event `notify_course_soon_sent`.

---

# 4. УДОБНОЕ ХРАНЕНИЕ ЛИДОВ

## 4.1 Проблема

Сейчас: `/export_leads` → CSV. Нет структуры для работы с лидами (статусы, заметки, история).

## 4.2 Решение: CRM-слой над лидами

### Таблица leads (расширение)

Лиды = пользователи с `phone IS NOT NULL OR arena_registered = TRUE`. Можно хранить как представление или отдельную таблицу с денормализацией для быстрого доступа.

```sql
-- Вариант A: представление + таблица lead_notes
CREATE TABLE IF NOT EXISTS lead_notes (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    admin_id BIGINT NOT NULL,
    note TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lead_statuses (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
    status VARCHAR(30) DEFAULT 'new',  -- new, contacted, qualified, converted, lost
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by BIGINT
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_lead_notes_user ON lead_notes(user_id);
CREATE INDEX IF NOT EXISTS idx_lead_statuses_status ON lead_statuses(status);
```

### Статусы лида

| Статус | Описание |
|--------|----------|
| `new` | Новый, не обработан |
| `contacted` | Связались |
| `qualified` | Квалифицирован (интерес есть) |
| `converted` | Оплатил / конвертировался |
| `lost` | Отказ, не отвечает |

### Функциональность в neurounit.fun/admin

| Функция | Описание |
|---------|----------|
| **Объединённый список лидов** | Лендинг + бот. Колонка «Источник»: «Лендинг · Оферта», «Бот · Квест», «Бот · Арена» |
| **Список лидов бота** | Таблица: имя, телефон, источник (квест/арена), статус, дата. API: `GET /api/admin/leads` |
| **Фильтры** | По статусу, источнику, дате, классу, оружию |
| **Поиск** | По имени, телефону, username |
| **Карточка лида** | Контакты, путь в боте, статус, заметки, история |
| **Заметки** | `POST /api/admin/leads/{user_id}/notes` |
| **Смена статуса** | `PUT /api/admin/leads/{user_id}/status` |
| **Экспорт** | CSV по текущему фильтру (лендинг + бот или только бот) |

### Связь с users

Лиды — подмножество `users`. Не дублируем данные: `lead_statuses` и `lead_notes` — дополнения. Основные поля (phone, username, player_class, workshop_registered, arena_registered) — в `users`.

---

# 5. ИНТЕГРАЦИЯ БОТ ↔ САЙТ

## 5.1 Сценарий

Пользователь оплачивает на **сайте** (не в боте). Сайт отправляет событие на бэкенд бота → бот находит пользователя и шлёт ему в Telegram: «Оплата прошла успешно, менеджер свяжется с вами в ближайшее время».

## 5.2 Связь пользователя сайта и Telegram

| Способ | Описание | Когда использовать |
|--------|----------|-------------------|
| **По телефону** | На сайте при оплате вводится телефон. Ищем в `users` по `phone`. | Пользователь уже был в боте, оставил телефон |
| **По email** | Аналогично по `email` | Если собираем email |
| **Привязка при первом заходе** | Пользователь на сайте вводит Telegram @username или переходит по ссылке t.me/bot?start=pay_XXX | Явная привязка перед оплатой |
| **Deep link после оплаты** | «Введите код из письма» → код = user_id (зашифрованный) | Менее удобно |

**Рекомендация:** приоритет — **телефон**. При оплате на сайте запрашиваем телефон. Ищем `users.phone` или `users.user_id` (если на сайте сохранён после привязки).

## 5.3 API для сайта

```
POST /api/webhook/site
Headers: X-Site-Secret: <secret>  (проверка, что запрос с нашего сайта)
Body: {
  "event": "payment_succeeded",
  "user_phone": "+79001234567",   // или user_telegram_id, если привязан
  "amount": 5000,
  "order_id": "...",
  "metadata": {}
}
```

### Обработка

1. Проверить `X-Site-Secret` (конфиг `SITE_WEBHOOK_SECRET`).
2. Найти пользователя: `SELECT user_id FROM users WHERE phone = $1` (нормализовать телефон).
3. Если не найден — логировать, не падать (пользователь мог оплатить без бота).
4. Отправить сообщение в Telegram (текст из `content/texts.json` или из правила автоуведомления).
5. Записать событие в `events`: `event_type = 'site_payment_succeeded'`.

### Текст уведомления

Вариант в `content/texts.json`:

```json
"site_payment_success": "✅ Оплата прошла успешно! Менеджер свяжется с вами в ближайшее время."
```

Или настраиваемый в админке (правило с триггером `site_event`).

## 5.4 Другие события с сайта (расширяемо)

| Событие | Описание |
|---------|----------|
| `payment_succeeded` | Оплата на сайте |
| `order_shipped` | Заказ отправлен |
| `appointment_confirmed` | Запись подтверждена |
| `course_started` | Курс начался |

Формат единый: `event` + `user_phone`/`user_telegram_id` + доп. поля.

## 5.5 Безопасность (обязательно)

- **Секрет:** `SITE_WEBHOOK_SECRET` в .env, проверка `X-Site-Secret` через `hmac.compare_digest()`.
- **Rate limit:** 30 req/min с IP (Redis: `site_webhook:rate:{ip}`).
- **Идемпотентность:** проверять `order_id` в events, не слать дубль.
- **NGINX:** отдельный `location /api/webhook/site` (без IP whitelist — сайт на другом IP).

---

# 5.6 Безопасность API админки (обязательно)

| Мера | Реализация |
|------|------------|
| **Секрет** | `ADMIN_API_SECRET` в .env, проверка `X-Admin-Secret` через `hmac.compare_digest()` |
| **Rate limit** | 60 req/min с IP для `/api/admin/*` (Redis) |
| **Вызовы** | Только с бэкенда лендинга (Flask), никогда из браузера |
| **NGINX** | `location /api/admin/` — проксирование на Gunicorn, без IP whitelist (лендинг на другом IP) |
| **Логирование** | При 401 — логировать факт отказа без раскрытия секрета |

См. также раздел «БЕЗОПАСНОСТЬ API» в TZ.md.

---

# 6. УВЕДОМЛЕНИЯ АДМИНАМ

## 6.1 Типы уведомлений

| Тип | Триггер | Приоритет | Текст |
|-----|---------|-----------|-------|
| **user_stuck** | 3 напоминания отправлены, пользователь не прошёл шаг | Высокий | user_id, quest_state, кол-во напоминаний |
| **bot_down** | Бот не отвечает / webhook не работает | Критический | Время простоя, последняя ошибка |
| **critical_error** | Необработанное исключение в хендлере | Высокий | error_type, user_id, traceback (обрезанный) |
| **rate_limit_hit** | Частые TelegramRetryAfter | Средний | Количество за последний час |

## 6.2 user_stuck — логика

Текущий дожим:
- `followup_stage = -1` — отправили idle-напоминание (1 раз)
- `followup_stage = 0..4` — дни миниквестов

**Новое:** счётчик напоминаний в рамках одного "зависания".

Вариант A (минимальные изменения):
- Добавить `idle_reminder_count` в users (или Redis `idle:reminders:{user_id}`)
- При `check_idle_users`: если `followup_stage = -1` и прошло >1 часа — считать повторное напоминание
- После 3-го — `notify_admins(bot, "user_stuck", {user_id, quest_state, ...})`

Вариант B (через events):
- Логировать `idle_reminder_sent` в events
- При проверке: `COUNT(*) WHERE event_type = 'idle_reminder_sent' AND user_id = X AND created_at > NOW() - 7 days`
- Если >= 3 → уведомить админа

**Рекомендация:** Вариант A — добавить `idle_reminder_count INTEGER DEFAULT 0` в users. При каждом idle-напоминании инкрементировать. При 3 → уведомление, сбросить при активности (touch_activity).

## 6.3 bot_down

- **Health-check:** endpoint `/health` возвращает 200 если PG + Redis доступны
- **Внешний мониторинг:** UptimeRobot / cron на другом сервере: `curl https://bot.neurounit.fun/health`
- **При 5xx или timeout:** скрипт шлёт в Telegram админам (через бота или BotFather-бот для алертов)
- **Альтернатива:** worker раз в 5 мин проверяет `get_webhook_info()` и при ошибке — `notify_admins`

## 6.4 critical_error

- **Глобальный error handler** в aiogram: `@router.errors()` или `dp.errors`
- При необработанном исключении: `notify_error(bot, type, message, user_id)` (уже есть в utils/notifications)
- Ограничение: не более 1 уведомления в 5 мин на один тип (Redis: `admin_alert:critical_error` TTL 300)

## 6.5 Антиспам для админов

- Не более N уведомлений в час по каждому типу (config: `admin_notify_max_per_hour`)
- Redis: `admin_notify:{type}:{hour}` INCR, EXPIRE 3600
- При превышении — только логировать, не слать в Telegram

---

# 7. АДМИНКА И СТАТИСТИКА

## 7.1 Интеграция Graspil

### Подключение

- **Метод:** Auto Setup (передача токена бота) — самый простой
- **Альтернатива:** API для отправки событий (targets) — `POST https://api.graspil.com/v1/send-target`
- **Конфиг:** `GRASPIL_API_KEY` в .env (если используем API)

### Что даёт Graspil

- DAU/WAU/MAU
- Конверсии (если настроены goals)
- UTM-источники
- Действия пользователей (commands, кнопки — при настройке)
- Готовые дашборды

### Встраивание в neurounit.fun/admin

- Блок «Graspil»: ссылка «Открыть дашборд» → `https://app.graspil.com/...`
- Опционально: iframe, если Graspil поддерживает embed

## 7.2 Собственная статистика по шагам

### Воронка (из events + users)

| Шаг | Метрика | SQL/Источник |
|-----|---------|--------------|
| 1 | Посетители всего | `COUNT(DISTINCT user_id) FROM events WHERE event_type = 'bot_start'` |
| 2 | Начали квест | `event_type = 'quest_start'` |
| 3 | Выбрали класс | `event_type = 'class_selected'` |
| 4 | Выбрали оружие | `event_type = 'weapon_selected'` |
| 5 | Раунд 1 | `event_type` содержит round или `quest_state` |
| 6 | Раунд 2 | — |
| 7 | Раунд 3 | — |
| 8 | Квест завершён | `event_type = 'quest_completed'` |
| 9 | Записались на воркшоп | `event_type = 'workshop_registered'` |
| 10 | Оплатили | `event_type = 'payment_succeeded'` |

### Текущие event_type (из кода)

- `bot_start`, `quest_start`, `class_selected`, `weapon_selected`
- `quest_completed`, `contact_phone`, `workshop_registered`
- `arena_start`, `arena_participate`, `arena_q1_answered`, `arena_q2_answered`, `arena_q3_answered`, `arena_registered`, `arena_to_quest`, `arena_declined_quest`
- `upsell_shown`, `payment_created`, `payment_succeeded`, `payment_canceled`

### Дополнительные события для воронки

- `round_1_start`, `round_2_start`, `round_3_start` — или использовать `quest_state` в users
- Текущая схема: `quest_state` = `round_1`, `round_2`, `round_3` и т.д.

**Рекомендация:** добавить `log_event(pool, user_id, "round_start", {"round": N})` в quest.py при переходе на раунд. Тогда воронка будет полной.

### Статистика кликов по кнопкам

Новый event_type: `button_click`

```json
{"callback": "quest:class:businessman", "step": "class_selection"}
```

**Реализация:** middleware или обёртка над `CallbackQuery` — при каждом callback логировать `button_click` с `event_data = {"callback": callback_data}`.

### Статистика в neurounit.fun/admin

| Блок | API бота | Описание |
|------|----------|----------|
| Воронка | `GET /api/admin/funnel?days=7` | Шаги, числа, конверсии % |
| Кнопки | `GET /api/admin/button-stats` | Топ кнопок по кликам |
| Graspil | Ссылка | `url_button` на дашборд Graspil |

Команды в боте (`/stats`, `/stats_funnel`, `/export_leads`) остаются для быстрого доступа из Telegram.

### Пример вывода /stats_funnel

```
📊 ВОРОНКА (7 дней)

Шаг                    │ Всего   │ Конверсия
────────────────────────┼─────────┼──────────
1. Посетители           │ 1 234   │ 100%
2. Начали квест          │   987   │ 80.0%
3. Выбрали класс         │   876   │ 88.8%
4. Выбрали оружие        │   765   │ 87.3%
5. Завершили квест       │   543   │ 71.0%
6. Записались на воркшоп │   234   │ 43.1%
7. Оплатили              │    12   │  5.1%

📱 Лиды: 234 (квест) + 45 (арена) = 279
```

---

# 8. БЕКАП И ОТКАТ

## 8.1 Требования

- Бекап **перед каждым** обновлением
- Бекап **физически невозможно стереть** без участия владельца
- Быстрый откат на предыдущую версию

## 8.2 Схема бекапа

### Что бэкапить

| Объект | Метод |
|--------|-------|
| PostgreSQL | `pg_dump -U hydra hydra_bot -Fc -f backup_YYYYMMDD_HHMM.dump` |
| Redis | `redis-cli BGSAVE` + копия `dump.rdb` |
| Код | `git archive` или `tar` текущего состояния |
| .env | Копия (без коммита в git) |

### Расположение

```
/var/backups/hydra_bot/
├── db/
│   ├── hydra_20260304_120000.dump
│   └── ...
├── redis/
│   ├── dump_20260304_120000.rdb
│   └── ...
├── code/
│   ├── hydra_20260304_120000.tar.gz
│   └── ...
└── .env.backup_20260304
```

### Защита от удаления

1. **Директория:** `chown root:root /var/backups/hydra_bot`, `chmod 750`
2. **Скрипт бекапа:** запускается от root (cron или systemd timer)
3. **После создания:** `chattr +i` на каждый файл бекапа (immutable — даже root не удалит без `chattr -i`)
4. **Разблокировка:** отдельный скрипт `deploy/unlock_backups.sh`, который требует явного подтверждения и логирует действие

```bash
#!/bin/bash
# deploy/unlock_backups.sh — ТОЛЬКО для владельца сервера
# Убирает immutable с файлов старше N дней (или по дате)
echo "ВНИМАНИЕ: Вы разблокируете бекапы для удаления."
echo "Введите дату бекапа для разблокировки (YYYYMMDD) или 'all' для всех:"
read -r input
# ... chattr -i на выбранные файлы
```

### Скрипт deploy/backup.sh

```bash
#!/usr/bin/env bash
# Запуск: sudo deploy/backup.sh
# Вызывается ПЕРЕД каждым деплоем
set -euo pipefail
BACKUP_ROOT="/var/backups/hydra_bot"
TS=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_ROOT"/{db,redis,code}

# PostgreSQL
pg_dump -U hydra hydra_bot -Fc -f "$BACKUP_ROOT/db/hydra_${TS}.dump"

# Redis
redis-cli BGSAVE
sleep 2
cp /var/lib/redis/dump.rdb "$BACKUP_ROOT/redis/dump_${TS}.rdb"

# Код
cd /opt/hydra_bot
tar czf "$BACKUP_ROOT/code/hydra_${TS}.tar.gz" --exclude=venv --exclude=__pycache__ .

# .env
cp .env "$BACKUP_ROOT/.env.backup_${TS}"

# Immutable
chattr +i "$BACKUP_ROOT/db/hydra_${TS}.dump"
chattr +i "$BACKUP_ROOT/redis/dump_${TS}.rdb"
chattr +i "$BACKUP_ROOT/code/hydra_${TS}.tar.gz"
chattr +i "$BACKUP_ROOT/.env.backup_${TS}"

echo "Backup done: $TS"
```

## 8.3 Процедура обновления

```
1. sudo deploy/backup.sh
2. cd /opt/hydra_bot && git fetch && git diff HEAD origin/main  # проверить изменения
3. git pull origin main  # или конкретный тег/коммит
4. source venv/bin/activate && pip install -r requirements.txt
5. [Если есть миграции] psql -U hydra hydra_bot -f migrations/xxx.sql
6. systemctl restart hydra-bot hydra-worker
7. Проверка: curl https://bot.neurounit.fun/health
8. journalctl -u hydra-bot -n 50
```

## 8.4 Процедура отката

```
1. Определить последний рабочий бекап: ls -la /var/backups/hydra_bot/db/
2. sudo deploy/unlock_backups.sh  # разблокировать нужный бекап (если нужно восстановить)
3. systemctl stop hydra-bot hydra-worker
4. pg_restore -U hydra -d hydra_bot -c -Fc /var/backups/hydra_bot/db/hydra_YYYYMMDD_HHMMSS.dump
5. cp /var/backups/hydra_bot/redis/dump_YYYYMMDD.rdb /var/lib/redis/dump.rdb
6. redis-cli SHUTDOWN NOSAVE && systemctl start redis
7. cd /opt/hydra_bot && tar xzf /var/backups/hydra_bot/code/hydra_YYYYMMDD.tar.gz
8. systemctl start hydra-bot hydra-worker
9. Проверка
```

**Важно:** откат кода через `git checkout <commit>` проще, но откат БД обязателен если миграции меняли схему.

---

# 9. МИГРАЦИИ БД

## 9.1 Новые объекты (Patch 2)

```sql
-- migrations/patch2_001.sql

-- Счётчик idle-напоминаний (для user_stuck)
ALTER TABLE users ADD COLUMN IF NOT EXISTS idle_reminder_count INTEGER DEFAULT 0;

-- Дедупликация course_soon
ALTER TABLE users ADD COLUMN IF NOT EXISTS course_soon_sent BOOLEAN DEFAULT FALSE;

-- Индекс для воронки
CREATE INDEX IF NOT EXISTS idx_events_type_created ON events(event_type, created_at);

-- Рассылки из админки
CREATE TABLE IF NOT EXISTS scheduled_broadcasts (
    id SERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    segment_id VARCHAR(50) NOT NULL,
    scheduled_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'pending',
    created_by BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    result_sent INT,
    result_failed INT
);

-- Правила автоуведомлений
CREATE TABLE IF NOT EXISTS notification_rules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    text_template TEXT NOT NULL,
    segment_id VARCHAR(50) NOT NULL,
    trigger_type VARCHAR(50) NOT NULL,
    trigger_config JSONB DEFAULT '{}',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Лиды: заметки и статусы
CREATE TABLE IF NOT EXISTS lead_notes (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    admin_id BIGINT NOT NULL,
    note TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_lead_notes_user ON lead_notes(user_id);

CREATE TABLE IF NOT EXISTS lead_statuses (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
    status VARCHAR(30) DEFAULT 'new',
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by BIGINT
);
CREATE INDEX IF NOT EXISTS idx_lead_statuses_status ON lead_statuses(status);
```

## 9.2 Обратная совместимость

- Все `ADD COLUMN IF NOT EXISTS` — безопасно при повторном запуске
- Существующие запросы не ломаются (новые колонки имеют DEFAULT)

---

# 10. КРИТИЧЕСКИЕ ПРАВИЛА (ПОВТОР ИЗ TZ)

1. **НИКОГДА** `redis.keys()`, `redis.exists()` в циклах — только `MGET`, `scan_iter`
2. **НИКОГДА** рассылки без `asyncio.sleep(0.05)` между сообщениями
3. **НИКОГДА** APScheduler внутри Gunicorn — только в worker.py
4. **НИКОГДА** игнорировать `TelegramForbiddenError` без `UPDATE is_blocked = TRUE`
5. **НИКОГДА** не удалять контакты/платежи при сбросе прогресса
6. **Worker** — строго 1 экземпляр (systemd)

---

# 11. ЧЕК-ЛИСТ PATCH 2

## Phase 1 (обязательный минимум)

- [ ] API бота для админки: `/api/admin/stats`, `/funnel`, `/leads`, `/broadcast`, `/segments` (X-Admin-Secret)
- [ ] Безопасность API: `hmac.compare_digest()` для секретов, rate limit (Redis)
- [ ] Лендинг: расширение neurounit.fun/admin — блоки бота (см. UNIFIED_ADMIN_SPEC.md)
- [ ] Рассылки: форма на лендинге → POST к боту, превью по сегменту
- [ ] Сегменты: реализация всех сегментов из раздела 2
- [ ] Автоуведомления: таблица `notification_rules`, worker обрабатывает правила
- [ ] Триггеры: event, scheduled_once, scheduled_recurring, days_before_date
- [ ] Лиды: таблицы `lead_notes`, `lead_statuses`, UI в админке
- [ ] Webhook сайта: `POST /api/webhook/site`, поиск по phone, отправка в Telegram
- [ ] Уведомление админу `user_stuck` после 3 idle-напоминаний
- [ ] `/stats_funnel` — воронка по шагам
- [ ] Миграции БД
- [ ] `deploy/backup.sh`, `deploy/rollback.sh`
- [ ] NGINX: `location /api/admin/`, `location /api/webhook/site`, `location /health` (deploy/nginx.conf)

## Phase 2 (по желанию)

- [ ] Триггер `relative_days` (N дней после события)
- [ ] Graspil embed / ссылка в админке
- [ ] `bot_down` — health-check + внешний мониторинг

---

# 12. ЧТО МОЖЕТ ПОЙТИ НЕ ТАК

1. **Перегрузка админов уведомлениями** — при массовом "зависании" сотен пользователей. Решение: rate limit уведомлений, батчинг (1 сообщение "10 пользователей застряли на round_2").
2. **Бекап заполняет диск** — при ежедневных бекапах. Решение: ротация (хранить последние 7 дней), `unlock_backups.sh` для удаления старых после разблокировки.
3. **Graspil rate limit** — при 10K пользователей и частой отправке событий. Решение: батчинг, отправка раз в N минут, или только ключевые цели (payment_succeeded, workshop_registered).
4. **Конфликт с followup_service** — изменение логики idle. Решение: `idle_reminder_count` инкрементировать только в `check_idle_users`, сбрасывать при `touch_activity`.
5. **Сайт: пользователь не найден по телефону** — оплатил на сайте, но в боте нет (новый клиент). Решение: логировать в events `site_payment_user_not_found`, не падать; опционально — уведомлять админа о «сиротской» оплате.

# ТЗ: Единая админка для лендинга и Telegram-бота

## 1. Обзор проекта

**НЕЙРО-ЮНИТ** — образовательный проект с двумя точками входа:
- **Лендинг** (neurounit.fun) — захват лидов, квиз, игра «Угадай ИИ-клона»
- **Telegram-бот** — взаимодействие с пользователями в мессенджере

**Цель:** единая админ-панель **neurounit.fun/admin**, где менеджер видит данные и с лендинга, и с бота в одном месте.

---

## 2. Архитектура единой админки

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ЕДИНАЯ АДМИНКА: neurounit.fun/admin                                          │
│  • Один логин/пароль (ADMIN_USER, ADMIN_PASS_HASH)                           │
│  • Данные лендинга (leads.db) + данные бота (PostgreSQL)                      │
│  • Рассылки, автоуведомления, лиды, статистика — всё здесь                   │
└─────────────────────────────────────────────────────────────────────────────┘
         │                                    │
         │ GET /admin/api/leads                │ GET {BOT_API_URL}/api/admin/*
         │ (локально, leads.db)                │ (X-Admin-Secret)
         ▼                                    ▼
┌──────────────────────────────┐    ┌──────────────────────────────────────────┐
│  ЛЕНДИНГ (neurounit.fun)     │    │  TELEGRAM-БОТ (bot.neurounit.fun)         │
│  • Flask + SQLite (leads.db) │    │  • aiogram + PostgreSQL + Redis          │
│  • Формы, квиз, игра        │    │  • POST /api/landing/notify-winner        │
│  • Хостинг: тот же или иной  │    │  • API для админки (см. ниже)             │
└──────────────────────────────┘    └──────────────────────────────────────────┘
```

**Вариант интеграции:** A — админка на лендинге, бот отдаёт данные по API.

**Существующая связь:** `POST /api/landing/notify-winner` — лендинг при выигрыше в игре шлёт уведомление в Telegram (приз). Контракт: `BOT_API_CONTRACT.md`.

---

## 3. Маршруты админки (neurounit.fun/admin)

### 3.1 Базовые (уже есть на лендинге)

| Маршрут | Метод | Описание |
|---------|-------|----------|
| `/admin/login` | GET/POST | Форма входа |
| `/admin` | GET | Дашборд |
| `/admin/logout` | GET | Выход |
| `/admin/leads/csv` | GET | Экспорт лидов в CSV |
| `/admin/api/leads` | GET | JSON API лидов (лендинг) |

### 3.2 Новые блоки (данные бота + функционал Patch 2)

| Маршрут | Описание |
|---------|----------|
| `/admin` | Дашборд: счётчики лендинга + счётчики бота (объединённые) |
| `/admin/leads` | **Объединённые лиды**: лендинг + бот, фильтры, поиск, статусы, заметки |
| `/admin/broadcasts` | Рассылки: форма, сегмент, дата/время, история |
| `/admin/notifications` | Правила автоуведомлений: создать, редактировать, вкл/выкл |
| `/admin/stats` | Статистика: воронка бота, Graspil, кнопки |
| `/admin/bot` | Специфичные данные бота (пользователи, события) |

---

## 4. Дашборд — блоки

### 4.1 Счётчики (лендинг, уже есть)

- Всего лидов, лидов сегодня
- Квиз пройден, источников
- Посетители (7 дней), уникальные
- Формы начали / отправили
- Оплаты (кол-во, сумма ₽)
- Индекс вовлечённости

### 4.2 Счётчики бота (новые, из API бота)

| Блок | Источник | Описание |
|------|----------|----------|
| Пользователи бота | `GET /api/admin/stats` | users_total, users_today |
| Воронка | `GET /api/admin/funnel` | bot_start → quest → workshop → paid |
| Призы с лендинга | `GET /api/admin/stats` | winners_notified, winners_pending |
| Рассылки | локально или API | Очередь, запланировано |

### 4.3 Лиды — объединённый вид

- **Источник** в одной таблице: «Лендинг · Оферта», «Лендинг · Игра», «Бот · Квест», «Бот · Арена»
- Поиск по имени, телефону, Telegram
- Статусы (new, contacted, qualified, converted, lost) — для лидов бота
- Заметки — для лидов бота (lead_notes)
- Tooltip при наведении на имя — статистика (лендинг: просмотры, клики; бот: путь в воронке)

---

## 5. API бота для админки

Все запросы к API бота требуют заголовок:
```
X-Admin-Secret: {ADMIN_API_SECRET}
```

Секрет хранится в .env бота и лендинга. Лендинг при рендере админки дергает бота с этим секретом.

### 5.1 Статистика

```
GET {BOT_API_URL}/api/admin/stats
```

**Ответ:**
```json
{
  "users_total": 150,
  "users_today": 5,
  "users_blocked": 3,
  "winners_notified": 12,
  "winners_pending": 2,
  "leads_quest": 45,
  "leads_arena": 8,
  "payments_succeeded": 7,
  "revenue": 35000
}
```

### 5.2 Воронка

```
GET {BOT_API_URL}/api/admin/funnel?days=7
```

**Ответ:**
```json
{
  "steps": [
    { "name": "Посетители", "count": 1234, "conversion": 100 },
    { "name": "Начали квест", "count": 987, "conversion": 80.0 },
    { "name": "Завершили квест", "count": 543, "conversion": 55.0 },
    { "name": "Записались на воркшоп", "count": 234, "conversion": 43.1 },
    { "name": "Оплатили", "count": 12, "conversion": 5.1 }
  ]
}
```

### 5.3 Лиды бота

```
GET {BOT_API_URL}/api/admin/leads?limit=50&offset=0&status=new&search=
```

**Ответ:**
```json
{
  "leads": [
    {
      "user_id": 123456789,
      "username": "ivan",
      "first_name": "Иван",
      "phone": "+79001234567",
      "source": "quest",
      "status": "new",
      "player_class": "businessman",
      "workshop_registered": true,
      "arena_registered": false,
      "created_at": "2026-03-07T12:00:00",
      "notes": [],
      "got_prize": false
    }
  ],
  "total": 53
}
```

### 5.4 Сегменты (для превью рассылки)

```
GET {BOT_API_URL}/api/admin/segments
```

**Ответ:**
```json
{
  "segments": [
    { "id": "all", "name": "Все активные", "count": 150 },
    { "id": "workshop_registered", "name": "Записались на воркшоп", "count": 45 }
  ]
}
```

### 5.5 Рассылка (POST)

```
POST {BOT_API_URL}/api/admin/broadcast
Content-Type: application/json
X-Admin-Secret: {ADMIN_API_SECRET}

{
  "text": "Текст рассылки",
  "segment_id": "workshop_registered",
  "scheduled_at": "2026-03-10T19:00:00",
  "preview": false
}
```

**Ответ:**
```json
{
  "total_recipients": 45,
  "status": "scheduled",
  "scheduled_at": "2026-03-10T19:00:00"
}
```

Если `scheduled_at` = null и `preview` = false — рассылка запускается сразу.

### 5.6 Правила автоуведомлений (CRUD)

```
GET  {BOT_API_URL}/api/admin/notification-rules
POST {BOT_API_URL}/api/admin/notification-rules
PUT  {BOT_API_URL}/api/admin/notification-rules/{id}
DELETE {BOT_API_URL}/api/admin/notification-rules/{id}
```

### 5.7 Заметки и статусы лидов

```
POST {BOT_API_URL}/api/admin/leads/{user_id}/notes
PUT  {BOT_API_URL}/api/admin/leads/{user_id}/status
```

---

## 6. Конфигурация

### Лендинг (.env)

```
BOT_API_URL=https://bot.neurounit.fun
ADMIN_API_SECRET=<общий_секрет>
```

### Бот (.env)

```
ADMIN_API_SECRET=<тот_же_секрет>
SITE_WEBHOOK_SECRET=<секрет_для_webhook_сайта>
```

---

## 6.1 Безопасность API

| Требование | Реализация |
|------------|------------|
| **Проверка секрета** | `hmac.compare_digest(provided, expected)` — защита от timing attack |
| **Вызовы к боту** | Только с бэкенда лендинга (Flask), никогда из браузера |
| **Rate limit** | Бот: 60 req/min с IP для `/api/admin/*` |
| **NGINX** | `location /api/admin/` — проксирование на Gunicorn (без IP whitelist) |
| **Секреты** | Минимум 32 байта, `openssl rand -hex 32` |

---

## 7. Текущая админка лендинга — полная спецификация

### 7.1 Авторизация

- Логин: env `ADMIN_USER` (по умолчанию `admin`)
- Пароль: SHA-256 хеш в `ADMIN_PASS_HASH`
- Сессия Flask (cookie)
- Декоратор `@admin_required` на защищённых маршрутах

### 7.2 Дашборд — блоки (лендинг)

**Счётчики (stat-card):**
- Всего лидов, лидов сегодня
- Квиз пройден, источников
- Посетители (7 дней), уникальные
- Формы начали заполнять, формы отправлены
- Оплаты (кол-во), сумма оплат ₽

**Индекс вовлечённости:** 0–100, статус «скучно» / «погранично» / «не скучно»

**Взаимодействия с кнопками:** таблица кнопка | всего | уникальных

**Лиды (лендинг):**
- Поиск по имени, телефону, Telegram
- Колонки: # | Имя | Телефон | Источник | Telegram | Квиз | Дата
- Имя: tooltip — статистика посетителя (просмотры, клики, формы, IP, UTM, referrer, ответы квиза)
- Телефон: иконка копирования
- Источник: «Забронировать место · Оферта», «Забрать приз (игра) · Игра»

**Результаты квиза:** Session ID | Ответы | Результат | Дата

### 7.3 Модель данных leads (лендинг)

| Поле | Тип | Описание |
|------|-----|----------|
| id | int | PK |
| name | text | Имя |
| phone | text | Телефон |
| source | text | landing_page, выигрыш в Игре ИИ клон |
| telegram | text | @username |
| quiz_data | text | JSON: session_id, q1, q2, q3, result |
| form_id | text | lead-form, prize-lead-form |
| block_id | text | offer, game-section |
| visitor_id | text | UUID из localStorage |
| utm_source, utm_medium, utm_campaign | text | UTM |
| referrer | text | document.referrer |
| ip, user_agent | text | Метаданные |
| created_at | timestamp | |

### 7.4 API лендинга для внешнего доступа

**GET /admin/api/leads** (требует сессию admin) — возвращает массив лидов лендинга.

Для интеграции с ботом можно добавить **GET /api/admin/leads?token=...** — отдача по токену (если бот будет агрегировать).

---

## 8. Связанные документы

- `REQUIREMENTS_FOR_LANDING.md` — **для агента лендинга:** что реализовать на neurounit.fun для интеграции
- `PATCH_2_BROADCASTS_NOTIFICATIONS_ADMIN_STATS.md` — функционал рассылок, автоуведомлений, лидов (реализуется в боте)
- `BOT_API_CONTRACT.md` — notify-winner (уже реализован)
- `TZ.md` — основное ТЗ бота

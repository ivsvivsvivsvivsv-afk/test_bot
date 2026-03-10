# План реализации: НЕЙРО-ЮНИТ «Гидра Сингулярности»

> ⚠️ Архив этапов: папка `plan/` хранит историю проектной реализации.
> Для актуальной архитектуры, контента и production-конфигурации source of truth: `TZ.md` (v7.6+).

> **Версия ТЗ:** 7.6 (Production MVP)
> **Сервер:** FirstVDS (bot.neurounit.fun / 82.146.39.44)
> **Целевая нагрузка:** 1 000–10 000 параллельных пользователей
> **Стек:** aiogram 3.14 + asyncpg + Redis + Gunicorn + APScheduler + YooKassa

---

## Обзор этапов

| # | Этап | Файл | Суть | Оценка |
|---|------|------|------|--------|
| 1 | **Инфраструктура** | [STAGE_1](STAGE_1_INFRASTRUCTURE.md) | VDS, PostgreSQL, Redis, NGINX, systemd, SSL | 4-6 часов |
| 2 | **Ядро архитектуры** | [STAGE_2](STAGE_2_CORE_ARCHITECTURE.md) | db.py, ContentManager, texts.json, MediaService, middleware | 6-8 часов |
| 3 | **Квест (основная ветка)** | [STAGE_3](STAGE_3_QUEST_LOGIC.md) | /start → класс → оружие → 3 раунда → результат → мораль | 8-12 часов |
| 4 | **Арена и Генератор** | [STAGE_4](STAGE_4_ARENA_GENERATOR.md) | Арена (хакатон: 3 квалиф. вопроса → лид → квест), Генератор (редирект) | 4-6 часов |
| 5 | **Контакты и Upsell** | [STAGE_5](STAGE_5_CONTACTS_WORKSHOP_UPSELL.md) | Телефон (обязат.) + @username (авто), воркшоп, upsell | 4-6 часов |
| 6 | **YooKassa** | [STAGE_6](STAGE_6_YOOKASSA_PAYMENT.md) | Lua-скрипты, атомарный hold, webhook, zombie-protection | 8-10 часов |
| 7 | **Дожим и Worker** | [STAGE_7](STAGE_7_FOLLOWUP_WORKER.md) | worker.py, idle-напоминания, 5-дневные миниквесты, рассылки | 8-12 часов |
| 8 | **Админ, аналитика, деплой** | [STAGE_8](STAGE_8_ADMIN_ANALYTICS_DEPLOY.md) | /stats, /broadcast, events, нагрузочное тестирование, запуск | 6-8 часов |
| **Patch 2** | **Рассылки, админка, интеграция** | [PATCH_2](PATCH_2_BROADCASTS_NOTIFICATIONS_ADMIN_STATS.md) | Единая админка neurounit.fun/admin, API бота, рассылки, автоуведомления, лиды | — |

**Итого:** ~50-70 часов разработки

---

## Граф зависимостей

```
ЭТАП 1: Инфраструктура ────────────────────────┐
    │                                            │
    ▼                                            │
ЭТАП 2: Ядро архитектуры ─────────────┐         │
    │                                  │         │
    ▼                                  │         │
ЭТАП 3: Квест ──────────┐             │         │
    │                    │             │         │
    ▼                    │             │         │
ЭТАП 4: Арена ─────┐    │             │         │
    │               │    │             │         │
    ▼               ▼    ▼             │         │
ЭТАП 5: Контакты + Upsell            │         │
    │                                  │         │
    ▼                                  │         │
ЭТАП 6: YooKassa ─────────────────────┤         │
    │                                  │         │
    ▼                                  ▼         │
ЭТАП 7: Дожим + Worker ──────────────────────────┤
    │                                             │
    ▼                                             ▼
ЭТАП 8: Админ + Деплой + Запуск ◄─────── ВСЁ СОБИРАЕТСЯ
```

---

## Что НЕЛЬЗЯ потерять при миграции

### Тексты (texts.py → content/texts.json)
- [x] welcome, welcome_back
- [x] quest_intro, select_class
- [x] Результаты: result_perfect, result_good, result_ok, result_bad
- [x] Головы Гидры: 6 вариантов (round1_cut, round1_alive, ...)
- [x] Контакты: phone_request, format_hint, success (email убран)
- [x] Арена: arena_intro
- [x] Промо: PROMO_TEXT, PROMO_SUCCESS_TEXT, PROMO_SLOTS_ENDED_TEXT
- [x] help, about_course, moral
- [x] Названия раундов: ХАОС, СОМНЕНИЕ, ИСТИНА
- [x] Тексты кнопок: BUTTONS dict

### Логика веток
- [x] Квест: класс (4) → оружие (6) → 3 раунда → результат
- [x] Арена: специализация (4) → 2 задания → результат
- [x] Генератор: редирект на внешнего бота
- [x] Контакты: @username (авто) → телефон (обязат.) → подтверждение
- [x] Промо/Upsell: показ оффера → оплата YooKassa

### Данные
- [x] statements/*.txt — 7 файлов с утверждениями (без изменений)
- [x] Классы: businessman, creator, analyst, manager
- [x] Оружия: marketing, analytics, copywriting, design, management, video
- [x] Арена: хакатон-воронка (3 квалификационных вопроса → сбор контактов → предложение квеста)

### Картинки
- [x] Основная воронка использует только Telegram `file_id` (`utils/media_ids.py`)
- [ ] Миниквесты: при необходимости добавить `MINIQUEST_FILE_IDS` в `utils/media_ids.py`

---

## Критические архитектурные правила (актуальная версия в `TZ.md`)

1. ❌ last_activity в PostgreSQL → ✅ Redis SETEX с TTL
2. ❌ Оплата без HOLD → ✅ Lua-скрипт + Redis Sorted Set
3. ❌ Рассылка без задержки → ✅ asyncio.sleep(0.05) + TelegramRetryAfter
4. ❌ rate limit NGINX на webhook → ✅ whitelist IP Telegram
5. ❌ APScheduler в Gunicorn → ✅ worker.py (отдельный процесс)
6. ❌ Игнорирование TelegramForbiddenError → ✅ is_blocked = TRUE в finally
7. ❌ Удаление контактов при сбросе → ✅ phone/payments НЕ трогаем
8. ❌ /restart для пользователей → ✅ Только /reset_user для админов
9. ❌ redis.keys() → ✅ Sorted Set + ZCARD
10. ❌ Синхронный YooKassa SDK → ✅ asyncio.to_thread()
11. ❌ Check-Then-Act двумя командами → ✅ Атомарный Lua
12. ❌ redis.exists() в цикле → ✅ MGET
13. ✅ DB_POOL_MAX = 10 (4×10=40 < PG 100)
14. ❌ Хардкод текстов → ✅ ContentManager → texts.json
15. ❌ FSInputFile и файловое хранилище медиа в воронке → ✅ только Telegram file_id
16. ❌ redis.scan(0) → ✅ scan_iter()
17. ❌ delete_webhook в on_shutdown → ✅ Только bot.session.close()
18. **Patch 2:** Единая админка neurounit.fun/admin. Для лендинга: [REQUIREMENTS_FOR_LANDING](REQUIREMENTS_FOR_LANDING.md)

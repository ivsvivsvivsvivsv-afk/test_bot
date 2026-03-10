# ЭТАП 2: Ядро архитектуры и контент-система

## САММАРИ

**Цель:** Создать фундаментальные модули, на которых строится вся логика бота: подключения к БД и Redis, модели данных, систему управления контентом и медиа.

**Что делаем:**
- `db.py` — asyncpg connection pool с graceful shutdown
- `redis_client.py` — подключение Redis, хелперы
- `models/user.py` + `models/payment.py` — Pydantic-модели для валидации
- `utils/config_db.py` — `get_config()` для чтения таблицы config в PostgreSQL
- `utils/content_manager.py` — ContentManager (загрузка texts.json в ОЗУ при старте)
- `content/texts.json` — **МИГРАЦИЯ ВСЕХ ТЕКСТОВ** из текущего `texts.py` + новые тексты для дожима и upsell
- `services/media_service.py` — кэширование file_id в Redis (для рассылок без FSInputFile)
- `middlewares/db_middleware.py` — инъекция pool и redis_conn в handlers
- `middlewares/logging_mw.py` — структурированное логирование

**Что НЕ теряем:**
- ВСЕ тексты из `texts.py` (TEXTS, MESSAGES, ROUND_NAMES, BUTTONS) → `content/texts.json`
- Ни одно сообщение не пропадает, только формат хранения меняется (Python dict → JSON)

**Ключевые архитектурные правила:**
- НИКАКОГО хардкода текстов в .py файлах — только ContentManager
- НИКАКОГО FSInputFile в рассылках — только media_service (file_id из Redis)
- get_config() обязателен — без него бот упадёт при оплате (NameError)
- DB_POOL_MAX = 10 на воркер (4 воркера × 10 = 40 < PG default 100)

**Риски:**
- При миграции текстов нужно проверить все {placeholder} — в JSON формат .format()
- ContentManager — singleton, при тестировании нужно сбрасывать _instance

---

## 1. МОДУЛЬ db.py — PostgreSQL Connection Pool

### Текущее состояние
В `database.py` есть `PostgreSQLDatabase` с asyncpg pool (min=5, max=20), но:
- Таблицы не соответствуют ТЗ (нет quest_state, score, round_number и т.д.)
- Отсутствуют методы, которые вызываются в handlers (update_user_class, update_user_round...)
- Pool max=20 — при 4 воркерах = 80, что опасно близко к PG default 100

### Что создаём
```python
# db.py — чистый модуль, без ORM

async def create_pool(dsn, min_size, max_size) -> asyncpg.Pool
async def close_pool(pool)

# Все SQL-запросы через pool.fetch/fetchrow/fetchval/execute
# Нет абстрактных интерфейсов — прямой asyncpg
```

### Ключевые отличия от текущего database.py
| Было | Стало |
|------|-------|
| DatabaseInterface (ABC) + 2 реализации | Один модуль, только asyncpg |
| pool min=5, max=20 | pool min=2, max=10 (из .env) |
| Отдельные таблицы users + contacts | Единая таблица users |
| Нет command_timeout | command_timeout=10 |

### Улучшения
- **Retry-логика при старте** — если PostgreSQL ещё не готов (при перезапуске), pool пытается подключиться 3 раза с экспоненциальной задержкой
- **Health-check** — `SELECT 1` при старте для верификации подключения
- **Graceful shutdown** — `pool.close()` с ожиданием завершения активных запросов

---

## 2. МОДУЛЬ redis_client.py

### Текущее состояние
Redis используется в `promo.py` (RedisLock) и потенциально для FSM, но:
- Клиент инициализируется глобально через `set_redis_client()`
- Нет decode_responses=True (бинарные данные)
- Нет hiredis для производительности

### Что создаём
```python
# redis_client.py
async def create_redis(url: str) -> redis.asyncio.Redis
```

### Ключевые параметры
- `decode_responses=True` — все значения как строки, не bytes
- `hiredis` — C-парсер для 3x ускорения
- Отдельный экземпляр для FSM Storage (без decode_responses, как требует aiogram)

---

## 3. МОДЕЛИ ДАННЫХ (Pydantic)

### models/user.py
```python
class UserCreate:
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    utm_source: Optional[str]

class UserUpdate:
    quest_state: Optional[str]
    player_class: Optional[str]
    weapon: Optional[str]
    score: Optional[int]
    round_number: Optional[int]
    # ...

class UserDB:
    # Полная модель из БД (все поля таблицы users)
```

### models/payment.py
```python
class PaymentCreate:
    user_id: int
    amount: Decimal
    offer_type: str = "business_review"

class PaymentStatus:
    # pending / succeeded / canceled / refunded
```

### Зачем Pydantic
- **Валидация** — типы проверяются при создании, не при записи в БД
- **Документация** — модели описывают контракт данных
- **Сериализация** — .model_dump() для JSON, .model_dump(exclude_none=True) для partial updates

---

## 4. МИГРАЦИЯ ТЕКСТОВ: texts.py → content/texts.json

### Критичность
Это **самая важная миграция** — потеря текстов = потеря всей игровой атмосферы.

### Текущие источники текстов
1. `texts.py` → `TEXTS` dict (welcome, quest_intro, select_class, results, contacts, arena, help)
2. `texts.py` → `MESSAGES` dict (legacy тексты: start, class_choice, weapon_choice, rounds, victory, moral, contacts, arena)
3. `texts.py` → `ROUND_NAMES` dict (названия раундов)
4. `texts.py` → `BUTTONS` dict (тексты кнопок)
5. `handlers/quest.py` → хардкод текстов в строках (подтверждения выбора класса/оружия)
6. `handlers/promo.py` → PROMO_TEXT, PROMO_SUCCESS_TEXT, PROMO_SLOTS_ENDED_TEXT
7. `handlers/arena.py` → хардкод текстов (задания, результаты)

### Стратегия миграции
Все тексты объединяются в ОДИН файл `content/texts.json` с ключами по категориям:

```json
{
    "welcome": "...(из TEXTS.welcome)...",
    "welcome_back": "...(из TEXTS.welcome_back)...",
    "quest_intro": "...(из TEXTS.quest_intro)...",
    "select_class": "...(из TEXTS.select_class)...",
    
    "class_businessman_confirm": "⚔️ <b>Отлично! Вы — 💼 Бизнесмен</b>\n\nСтроит империю с помощью ИИ\n\nТеперь выберите своё оружие:",
    "class_creator_confirm": "⚔️ <b>Отлично! Вы — 🎨 Творец</b>\n\n...",
    "class_analyst_confirm": "...",
    "class_manager_confirm": "...",
    
    "weapon_confirm": "🗡️ <b>Ваше оружие: {weapon_name}</b>\n\n{weapon_desc}\n\nПриготовьтесь! Сейчас начнётся испытание.",
    
    "round_intro": "⚔️ <b>{round_name}</b>\n\n📜 <b>Утверждение:</b>\n<i>\"{statement}\"</i>\n\n💡 <b>Подсказка от мудреца:</b>\n{wisdom_prompt}\n\nГотов проверить и дать ответ?",
    
    "round_correct": "✅ <b>ВЕРНО!</b>\n\n🗡️ Ты отрубил голову Гидры!\n\n{head_message}\n\nАртефакты: <b>{score}</b>",
    "round_wrong": "❌ <b>Неверно!</b>\n\n🐍 Голова Гидры уцелела...\n\n{continue_message}\n\nАртефакты: <b>{score}</b>",
    
    "head_round1_cut": "🔥 Первая голова повержена! Но две ещё живы...",
    "head_round1_alive": "😈 Первая голова ухмыляется. Впереди ещё два испытания.",
    "head_round2_cut": "⚡ Вторая голова падает! Осталась последняя...",
    "head_round2_alive": "🐍 Две головы смотрят на тебя голодными глазами.",
    "head_round3_cut": "🏆 ФИНАЛЬНЫЙ УДАР! Гидра повержена!",
    "head_round3_alive": "💀 Гидра выжила... Но ты сражался достойно.",
    
    "round_name_1": "🐉 ГОЛОВА ПЕРВАЯ: ХАОС",
    "round_name_2": "🐉 ГОЛОВА ВТОРАЯ: СОМНЕНИЕ",
    "round_name_3": "🐉 ГОЛОВА ТРЕТЬЯ: ИСТИНА",
    
    "result_perfect": "...(из TEXTS)...",
    "result_good": "...(из TEXTS)...",
    "result_ok": "...(из TEXTS)...",
    "result_bad": "...(из TEXTS)...",
    
    "moral": "...(из MESSAGES.moral)...",
    
    "contact_intro": "...(из TEXTS)...",
    "contact_phone_request": "...(из TEXTS)...",
    "contact_success": "...(из TEXTS)...",
    
    "upsell_offer": "🔥 <b>ЭКСКЛЮЗИВНОЕ ПРЕДЛОЖЕНИЕ</b>\n\n...(из PROMO_TEXT с {remaining}, {price})...",
    "upsell_no_slots": "...(из PROMO_SLOTS_ENDED_TEXT)...",
    "payment_success": "...(из PROMO_SUCCESS_TEXT)...",
    "payment_refund": "К сожалению, все места заняты. Деньги возвращены.",
    
    "arena_intro": "...(из TEXTS)...",
    
    "idle_reminder": "⚔️ Герой, ты остановился в бою! Гидра наступает!\n\nПродолжи квест!",
    "miniquest_day1": "...(из ТЗ)...",
    "miniquest_day2": "...",
    "miniquest_day3": "...",
    "miniquest_day4": "...",
    "miniquest_day5": "...",
    "miniquest_correct": "🎉 Отлично! Ты снова отрубил голову Гидре!",
    "miniquest_wrong": "💪 Не сдавайся! Гидра хитра, но ты сильнее!",
    "workshop_cta_day1": "...(из ТЗ)...",
    "workshop_cta_day2": "...",
    "workshop_cta_day3": "...",
    "workshop_cta_day4": "...",
    "workshop_cta_day5": "...",
    
    "help": "...(из TEXTS)...",
    "about_course": "...(из TEXTS)..."
}
```

### Правила для texts.json
1. Динамические переменные: `{variable}` — подставляются через `.format(**kwargs)`
2. HTML-теги: `<b>`, `<i>`, `<code>` — используются напрямую
3. Все пользовательские значения оборачиваются в `html.quote()` внутри ContentManager

---

## 5. ContentManager — ЗАГРУЗКА ТЕКСТОВ

### Архитектура
- **Singleton** — загружается 1 раз при старте воркера
- **В ОЗУ** — нет повторных чтений с диска
- **Thread-safe** — каждый воркер Gunicorn имеет свой экземпляр
- **XSS-защита** — все динамические переменные экранируются

### API
```python
ContentManager.load("content/texts.json")           # При старте
ContentManager.get("upsell_offer", remaining=7)     # С подстановкой
ContentManager.get_raw("idle_reminder")              # Без подстановки
```

### Обновление текстов без передеплоя
1. Редактируешь `content/texts.json` на сервере
2. `systemctl restart hydra-bot` — Gunicorn перезапускает воркеры
3. Тексты обновлены (worker.py тоже перезапустить)

---

## 6. MediaService — КЭШИРОВАНИЕ file_id

### Проблема
При рассылке миниквестов 5000 пользователям через `FSInputFile`:
- 5000 × загрузка файла на серверы Telegram = 1GB трафика
- Каждая отправка ~500ms = 2500 секунд = 40 минут

### Решение
1. Один раз отправить файл скрытым сообщением админу
2. Получить `file_id` из ответа Telegram
3. Кэшировать в Redis (без TTL — file_id не протухает)
4. В рассылке слать file_id (мгновенно, 0 трафика)

### Когда используется
- Рассылка миниквестов (5 картинок × N пользователей)
- Любая будущая отправка медиа массово

---

## 7. MIDDLEWARE СТЕК

### db_middleware.py
Инжектирует `pool` и `redis_conn` в каждый handler через `data`:
```python
async def __call__(self, handler, event, data):
    data["pool"] = self.pool
    data["redis_conn"] = self.redis_conn
    return await handler(event, data)
```

**Критично:** В текущем коде `db: Database` передаётся как параметр. В новой архитектуре — `pool` и `redis_conn` через middleware.

### logging_mw.py
Структурированное логирование каждого update:
- user_id, update_type, handler_name, duration_ms
- Формат: structlog JSON для последующего анализа

---

## 8. УЛУЧШЕНИЯ ЭТОГО ЭТАПА

### 8.1 Технологические
- **ContentManager** вместо хардкода — тексты можно менять без передеплоя кода
- **MediaService** — 1000x экономия трафика при рассылках
- **Pydantic-модели** — валидация на уровне данных, не в handlers
- **Structlog** — JSON-логи, удобный grep по user_id

### 8.2 Функциональные
- **get_config()** — горячая смена цены, количества слотов, флагов из PostgreSQL
- **Единый формат текстов** — все переводы/правки в одном JSON-файле
- **Кэш утверждений** — statements загружаются в Redis, не читаются с диска каждый раз

### 8.3 Для вовлечённости
- **Персонализация текстов** — ContentManager.get("result_perfect", name=user.first_name) — обращение по имени
- **Динамический контент** — можно менять тексты A/B тестами через таблицу config
- **Готовность к мультиязычности** — texts_ru.json / texts_en.json в будущем

---

## 9. ЧЕК-ЛИСТ ЭТАПА

- [ ] Создан db.py (asyncpg pool, create/close, health-check)
- [ ] Создан redis_client.py (подключение, decode_responses)
- [ ] Создан models/user.py (UserCreate, UserUpdate, UserDB)
- [ ] Создан models/payment.py (PaymentCreate, PaymentStatus)
- [ ] Создан utils/config_db.py (get_config)
- [ ] Создан utils/content_manager.py (ContentManager singleton)
- [ ] Создан content/texts.json (ВСЕ тексты мигрированы из texts.py + promo.py + quest.py)
- [ ] Создан services/media_service.py (get_file_id, кэш в Redis)
- [ ] Создан middlewares/db_middleware.py (инъекция pool + redis)
- [ ] Создан middlewares/logging_mw.py (structlog)
- [ ] Проверено: ни одного хардкода текста в .py файлах
- [ ] Проверено: texts.json содержит ВСЕ тексты из texts.py + MESSAGES + promo
- [ ] Тест: ContentManager.get("round_intro", round_name="test", statement="test", wisdom_prompt="test")

---

## 10. ЗАВИСИМОСТИ

- **Зависит от Этапа 1:** schema.sql, config.py, requirements.txt, PostgreSQL, Redis
- **Блокирует Этапы 3-8:** все handlers используют ContentManager, pool, redis_conn

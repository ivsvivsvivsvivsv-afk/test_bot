# ЭТАП 3: Игровая логика квеста (основная ветка)

## САММАРИ

**Цель:** Перенести и улучшить основную игровую ветку — от /start до морали и воркшопа. Это ядро бота, через которое проходят 100% пользователей.

**Что делаем:**
- `bot.py` — точка входа (Gunicorn-совместимый, webhook mode, БЕЗ scheduler)
- `handlers/start.py` — /start с deep link (utm), повторные визиты, запрет самосброса
- `handlers/quest.py` — выбор класса → оружие → 3 раунда ПРАВДА/ЛОЖЬ → результат → мораль
- `services/quest_service.py` — бизнес-логика квеста (вынесена из handlers)
- `keyboards/inline.py` — все клавиатуры (миграция из текущих + новые)
- FSM-состояния (QuestStates) в Redis через aiogram RedisStorage
- `utils/statements.py` — загрузка утверждений с кэшем в Redis

**Что ОБЯЗАТЕЛЬНО сохраняем (ничего нельзя потерять!):**
- 4 класса: businessman, creator, analyst, manager (с их emoji, названиями, описаниями)
- 6 оружий: marketing, analytics, copywriting, design, management, video (с названиями)
- 3 раунда с утверждениями ПРАВДА/ЛОЖЬ
- Логика получения утверждений из statements/*.txt по оружию и уровню
- Тексты результатов: perfect (3/3), good (2/3), ok (1/3), bad (0/3)
- Тексты голов Гидры: round1_cut, round1_alive, round2_cut, round2_alive, round3_cut, round3_alive
- Последовательность: класс → оружие → 3 раунда → результат → мораль → воркшоп
- Деактивация кнопок после нажатия (edit_reply_markup)
- Подсказки от мудреца (wisdom_prompt из statements)

**Ключевые изменения vs текущий код:**
- Пользователь НЕ МОЖЕТ сбросить прогресс (нет /restart, нет кнопки "Пройти снова")
- Квест проходится ОДИН РАЗ — при повторном /start показывается "уже играл" + предложение воркшопа
- FSM в Redis (вместо MemoryStorage) — состояние переживает перезапуск
- Тексты из ContentManager (вместо хардкода)
- quest_state записывается в PostgreSQL как бэкап (параллельно с Redis FSM)
- current_statement_hash хранится в БД (SHA256, не сам текст)

**Риски:**
- Текущий quest.py содержит кнопку "Пройти снова" — нужно убрать
- start.py содержит /restart — нужно убрать для обычных пользователей
- Нужно проверить, что все statements/*.txt корректно парсятся

---

## 1. ТЕКУЩАЯ ЛОГИКА (ЧТО СОХРАНЯЕМ)

### Поток (из текущего handlers/start.py + quest.py)
```
/start
  │
  ├─ Новый пользователь → приветствие + [🚀 Начать квест] [📚 О курсе]
  │
  └─ Повторный пользователь
       ├─ Квест пройден → "Уже прошёл, воркшоп?"
       └─ Квест не пройден → (В НОВОЙ ВЕРСИИ: продолжить с места, не сбрасывать)

[🚀 Начать квест]
  │
  ▼ quest_intro (3 шага описание)
  │
  ▼ [✅ Понятно, продолжить]
  │
  ▼ Выбор класса:
  │   [💼 Бизнесмен] [🎨 Творец] [📊 Аналитик] [📋 Менеджер]
  │
  ▼ Подтверждение класса + Выбор оружия:
  │   [📈 Маркетинг] [🔍 Аналитика] [✍️ Копирайтинг] [🎨 Дизайн] [📋 Менеджмент] [🎬 Видео]
  │
  ▼ Подтверждение оружия
  │
  ▼ РАУНД 1: утверждение + [✅ Правда] [❌ Ложь]
  │   → результат (верно/неверно + текст головы) + [➡️ Следующий раунд]
  │
  ▼ РАУНД 2: утверждение + [✅ Правда] [❌ Ложь]
  │   → результат + [➡️ Следующий раунд]
  │
  ▼ РАУНД 3: утверждение + [✅ Правда] [❌ Ложь]
  │   → результат + [🏆 Узнать результат]
  │
  ▼ Итоговый экран (класс, оружие, очки, текст результата)
  │   → [🎁 Получить подарок] (→ переход к контактам, Этап 5)
```

### Классы (из текущего quest.py)
```python
HERO_CLASSES = {
    "businessman": {"name": "💼 Бизнесмен", "emoji": "💼", "description": "Строит империю с помощью ИИ"},
    "creator":     {"name": "🎨 Творец",     "emoji": "🎨", "description": "Создает контент с помощью ИИ"},
    "analyst":     {"name": "📊 Аналитик",   "emoji": "📊", "description": "Анализирует данные с помощью ИИ"},
    "manager":     {"name": "📋 Менеджер",   "emoji": "📋", "description": "Управляет проектами с ИИ"}
}
```

### Оружия (из текущего quest.py)
```python
WEAPONS = {
    "marketing":   {"name": "📈 Меч Маркетинга",        "emoji": "📈", "description": "Продвижение и реклама"},
    "analytics":   {"name": "🔍 Линза Аналитики",       "emoji": "🔍", "description": "Данные и аналитика"},
    "copywriting": {"name": "✍️ Перо Копирайтинга",     "emoji": "✍️", "description": "Тексты и контент"},
    "design":      {"name": "🎨 Кисть Дизайна",         "emoji": "🎨", "description": "Визуальный контент"},
    "management":  {"name": "📋 Скрижаль Менеджмента",  "emoji": "📋", "description": "Управление и процессы"},
    "video":       {"name": "🎬 Камера Видео",           "emoji": "🎬", "description": "Видеоконтент"}
}
```

### Утверждения (из statements/*.txt)
Формат: `LEVEL|TYPE|STATEMENT|WISDOM_PROMPT`
Пример: `1|false|Email-маркетинг мёртв|Проверь статистику Mailchimp`

7 файлов: marketing, analytics, copywriting, design, management, video, other (fallback)

---

## 2. АРХИТЕКТУРА НОВОГО quest.py

### Разделение ответственности
```
handlers/quest.py          — роутер (callback handlers, отправка сообщений)
services/quest_service.py  — бизнес-логика (получить утверждение, проверить ответ, записать в БД)
utils/statements.py        — загрузка и парсинг утверждений (сохраняется без изменений!)
```

### FSM-состояния (расширение текущих)
```python
class QuestStates(StatesGroup):
    START = State()              # Стартовый экран
    CLASS_SELECTION = State()    # = selecting_class
    WEAPON_SELECTION = State()   # = selecting_weapon
    ROUND_1 = State()            # Показ утверждения
    ROUND_1_ANSWER = State()     # Ожидание ответа
    ROUND_2 = State()
    ROUND_2_ANSWER = State()
    ROUND_3 = State()
    ROUND_3_ANSWER = State()
    QUEST_RESULTS = State()      # = viewing_result
    MORAL = State()              # НОВОЕ: мораль (мост к воркшопу)
    CONTACT_PHONE = State()      # Переход в contacts handler
    CONTACT_EMAIL = State()
    UPSELL_OFFER = State()
    FINAL = State()
    COMPLETED = State()
```

### Запись в PostgreSQL при каждом шаге
Каждый переход состояния записывается:
```sql
UPDATE users SET quest_state = $1, updated_at = NOW() WHERE user_id = $2
```
Это бэкап на случай потери Redis FSM. При восстановлении можно определить, на каком шаге был пользователь.

---

## 3. BOT.PY — ТОЧКА ВХОДА

### Текущее состояние
`bot.py` — монолит с polling и webhook. Содержит всё: инициализацию, роутеры, middleware.

### Новая архитектура
```python
# bot.py — Gunicorn-совместимый webhook-сервер
# Запуск: gunicorn bot:app --worker-class aiohttp.GunicornWebWorker --workers 4

app = web.Application()

async def on_startup(app):
    pool = await create_pool(...)       # asyncpg
    redis_conn = await create_redis(...)  # redis
    storage = RedisStorage(redis=...)   # FSM
    bot = Bot(token=..., parse_mode=HTML)
    dp = Dispatcher(storage=storage)
    
    # Middleware (порядок важен!)
    dp.update.middleware(DatabaseMiddleware(pool, redis_conn))
    dp.update.middleware(ThrottleMiddleware(redis_conn))
    dp.update.middleware(ActivityMiddleware(redis_conn))
    
    # Роутеры (порядок = приоритет)
    dp.include_router(admin.router)     # Сначала админ (чтобы /stats не перехватился)
    dp.include_router(start.router)
    dp.include_router(quest.router)
    dp.include_router(contacts.router)
    dp.include_router(arena.router)
    dp.include_router(payment.router)
    
    # Webhook (с проверкой secret_token!)
    webhook_url = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
    current_wh = await bot.get_webhook_info()
    if current_wh.url != webhook_url:
        await bot.set_webhook(url=webhook_url, secret_token=WEBHOOK_SECRET)
    
    # SimpleRequestHandler с secret_token
    webhook_handler = SimpleRequestHandler(dp, bot, secret_token=WEBHOOK_SECRET)
    webhook_handler.register(app, path=WEBHOOK_PATH)

async def on_shutdown(app):
    # НЕ вызываем bot.delete_webhook()!
    await bot.session.close()
    await redis_conn.close()
    await pool.close()
```

### Критические правила для bot.py
1. **БЕЗ APScheduler** — scheduler в worker.py
2. **БЕЗ delete_webhook в on_shutdown** — graceful reload убьёт webhook для всех
3. **get_webhook_info() перед set_webhook()** — 4 воркера стартуют одновременно
4. **secret_token** — Telegram проверяет X-Telegram-Bot-Api-Secret-Token
5. **ContentManager.load() при импорте** — один раз на воркер

---

## 4. ИЗМЕНЕНИЯ В ЛОГИКЕ ОТНОСИТЕЛЬНО ТЕКУЩЕГО КОДА

### 4.1 УБИРАЕМ: самосброс прогресса
**Текущий код (handlers/start.py:192-211):**
```python
@router.message(Command("restart"))
async def cmd_restart(message: Message, state: FSMContext, db: Database):
    await state.clear()
    await db.reset_user_progress(user_id)
```
**Новый код:** Команда /restart УДАЛЯЕТСЯ. Пользователь НЕ МОЖЕТ сбросить прогресс.

### 4.2 УБИРАЕМ: кнопку "Пройти снова"
**Текущий код (handlers/quest.py:184-199):**
```python
def get_finish_keyboard():
    builder.row(InlineKeyboardButton(text="🔄 Пройти снова", callback_data="quest:restart"))
```
**Новый код:** Кнопка "Пройти снова" УДАЛЯЕТСЯ. Остаётся только "🎁 Получить подарок".

### 4.3 ИЗМЕНЯЕМ: повторный /start
**Текущий код:** Показывает "С возвращением! Используй /restart"
**Новый код:**
- Квест пройден → "Ты уже прошёл квест!" + [📝 Записаться на воркшоп] (если не записан)
- Квест не пройден → восстанавливаем FSM из PostgreSQL и продолжаем с места остановки

### 4.4 ДОБАВЛЯЕМ: экран морали
После результатов квеста — экран морали (текст из content/texts.json, ключ "moral"), затем переход к сбору контактов.

### 4.5 ДОБАВЛЯЕМ: запись events
Каждое значимое действие пишется в таблицу events:
- `quest_start` — нажал "Начать квест"
- `class_selected` — выбрал класс (data: {class: "businessman"})
- `weapon_selected` — выбрал оружие (data: {weapon: "marketing"})
- `round_completed` — ответил на раунд (data: {round: 1, correct: true, score: 1})
- `quest_completed` — завершил квест (data: {score: 2})

---

## 5. SERVICES/QUEST_SERVICE.PY

Выделяем бизнес-логику из handlers:

```python
async def get_or_create_user(pool, user_id, username, first_name, source) -> dict
async def get_statement_for_round(pool, redis_conn, weapon, round_num) -> Statement
async def process_answer(pool, user_id, round_num, user_answer, correct_answer) -> dict
async def complete_quest(pool, user_id, score) -> None
async def log_event(pool, user_id, event_type, event_data) -> None
```

### Кэш утверждений в Redis
Сейчас утверждения читаются с диска при каждом раунде. Оптимизация:
1. При первом запросе — парсим statements/{weapon}.txt
2. Кэшируем в Redis с TTL 1 час
3. При последующих запросах — из Redis

---

## 6. УЛУЧШЕНИЯ ЭТОГО ЭТАПА

### 6.1 Технологические
- **FSM в Redis** — состояние переживает перезапуск бота, работает с 4 воркерами
- **quest_state бэкап в PostgreSQL** — восстановление при потере Redis
- **Statement hash** — в БД хранится SHA256 утверждения (не текст), чтобы при изменении файла не было конфликтов
- **Webhook с secret_token** — защита от поддельных запросов

### 6.2 Функциональные
- **Продолжение с места остановки** — если пользователь закрыл бот на раунде 2, при /start он продолжает с раунда 2
- **Персонализация результата** — обращение по имени: "Поздравляем, {first_name}!"
- **Event tracking** — каждое действие записывается в events для аналитики воронки

### 6.3 Для вовлечённости
- **Прогресс-бар** — перед каждым раундом показывать "Раунд 2/3 | Артефакты: 1" (визуальная обратная связь)
- **Таймер обдумывания** — после показа утверждения добавить текст "💡 Используй Perplexity для проверки!" (мотивация использовать ИИ-инструменты)
- **Эмоциональные тексты голов** — разные для каждой комбинации класс+оружие (в будущем через A/B тест)
- **Плавная подача** — не сразу все 3 раунда, а с нарастающей драматургией (тексты "ХАОС → СОМНЕНИЕ → ИСТИНА" уже задают это)
- **Невозможность пройти заново** — создаёт ощущение ценности: "Это было уникальное испытание", мотивирует идти на воркшоп

---

## 7. ЧЕК-ЛИСТ ЭТАПА

- [ ] Создан bot.py (Gunicorn, webhook, secret_token, БЕЗ scheduler)
- [ ] Создан handlers/start.py (deep link, повторные визиты, БЕЗ /restart)
- [ ] Создан handlers/quest.py (класс → оружие → 3 раунда → результат → мораль)
- [ ] Создан services/quest_service.py (бизнес-логика, event logging)
- [ ] Обновлён keyboards/inline.py (все клавиатуры квеста)
- [ ] utils/statements.py скопирован без изменений
- [ ] QuestStates определены в FSM (Redis storage)
- [ ] Все 4 класса сохранены (businessman, creator, analyst, manager)
- [ ] Все 6 оружий сохранены (marketing, analytics, copywriting, design, management, video)
- [ ] Все 3 раунда работают (утверждение → ПРАВДА/ЛОЖЬ → результат)
- [ ] Тексты голов Гидры: 6 вариантов сохранены
- [ ] Тексты результатов: 4 варианта (perfect, good, ok, bad) сохранены
- [ ] Кнопка "Пройти снова" УДАЛЕНА
- [ ] Команда /restart УДАЛЕНА для пользователей
- [ ] Деактивация кнопок после нажатия работает
- [ ] Events записываются в БД (quest_start, class_selected, weapon_selected, round_completed, quest_completed)
- [ ] quest_state пишется в PostgreSQL при каждом переходе
- [ ] Тест: полный проход квеста от /start до морали

---

## 8. ЗАВИСИМОСТИ

- **Зависит от Этапа 1:** инфраструктура (PostgreSQL, Redis, NGINX)
- **Зависит от Этапа 2:** ContentManager, db.py, redis_client.py, middleware
- **Блокирует Этапы 5-7:** сбор контактов и upsell начинаются после квеста

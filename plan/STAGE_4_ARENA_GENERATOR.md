# ЭТАП 4: Арена, Генератор и альтернативные ветки

## САММАРИ

**Цель:** Реализовать две альтернативные ветки бота — Арену (сбор лидов опытных пользователей через хакатон) и Генератор видео (редирект на внешнего бота). Арена — это отдельная воронка лидогенерации для продвинутой аудитории, которая уже знакома с нейросетями.

**Что делаем:**
- `handlers/arena.py` — ветка Арены: приглашение на хакатон → 3 квалификационных вопроса → сбор контактов → предложение пройти квест
- Генератор видео — редирект на внешнего бота (просто кнопка-ссылка)
- Стартовое меню из 3 веток: [🎮 Квест] [🎬 Генератор] [⚔️ Арена]
- ArenaStates в FSM (Redis)

**Логика Арены (ИСТОЧНИК ПРАВДЫ):**
1. Пользователь нажимает [⚔️ Арена]
2. Сообщение: "Если ты уже опытный — записывайся на хакатон! Конкурс по созданию проектов с помощью нейросетей с ценными призами"
3. Если согласен → 3 вопроса про уровень подготовки и знание нейросетей (квалификация лида)
4. После ответов → сбор контактов (телефон + email) по стандартной схеме (как после квеста)
5. Контакты сохраняются в БД, arena_registered = TRUE
6. После контактов → "Хочешь пройти квест «Гидра Сингулярности»?"
7. Если да → переход в квест

**Бизнес-смысл:**
- Арена ловит продвинутую аудиторию, которой квест может показаться слишком простым
- 3 квалификационных вопроса = скоринг лида (тёплый/горячий)
- Контакты собираются ДО квеста (в отличие от основной ветки, где ПОСЛЕ)
- Данные о знаниях нейросетей → для менеджера при обработке лида

**Риски:**
- Нужно продумать 3 квалификационных вопроса (конкретное содержание)
- Арена проходится один раз (как и квест)

---

## 1. ПОТОК АРЕНЫ

```
[⚔️ Арена] на стартовом экране
  │
  ▼ ЭКРАН ПРИГЛАШЕНИЯ:
  │  "⚔️ АРЕНА НЕЙРО-ЮНИТ: ХАКАТОН
  │
  │   Ты уже знаком с нейросетями и хочешь большего?
  │
  │   Мы проводим хакатон — конкурс по созданию проектов
  │   с помощью ИИ. Лучшие получат ценные призы!
  │
  │   Чтобы попасть на хакатон, ответь на 3 коротких
  │   вопроса о своём уровне подготовки."
  │
  │   [🏆 Хочу участвовать!] [⬅️ Назад]
  │
  ├── [⬅️ Назад] → возврат в стартовое меню
  │
  └── [🏆 Хочу участвовать!]
        │
        ▼ ВОПРОС 1: Уровень опыта с нейросетями
        │  "Как давно ты используешь нейросети в работе?"
        │  [🟢 Только начинаю]
        │  [🟡 Несколько месяцев]
        │  [🔴 Больше года, использую ежедневно]
        │
        ▼ ВОПРОС 2: Инструменты
        │  "Какие ИИ-инструменты ты используешь?"
        │  [💬 ChatGPT / Claude]
        │  [🎨 Midjourney / DALL-E / Stable Diffusion]
        │  [🛠 API, автоматизации, собственные решения]
        │  [📦 Всё вышеперечисленное]
        │
        ▼ ВОПРОС 3: Цель участия
        │  "Что хочешь создать на хакатоне?"
        │  [🤖 Чат-бота или ассистента]
        │  [📊 Аналитический инструмент]
        │  [🎨 Генератор контента]
        │  [💡 Свой проект (расскажу)]
        │
        ▼ КВАЛИФИКАЦИЯ ЗАВЕРШЕНА:
        │  "🎉 Отлично! Твой профиль:
        │   Опыт: {ответ_1}
        │   Инструменты: {ответ_2}
        │   Цель: {ответ_3}
        │
        │   Ты подходишь для участия в хакатоне!
        │   Оставь контакты, и мы пригласим тебя."
        │
        ▼ СБОР КОНТАКТОВ (стандартная схема):
        │  Телефон → Email → Подтверждение
        │  (FSM: ARENA_PHONE → ARENA_EMAIL → ARENA_CONFIRM)
        │
        ▼ КОНТАКТЫ СОХРАНЕНЫ:
        │  arena_registered = TRUE
        │  arena_q1, arena_q2, arena_q3 → в БД (скоринг лида)
        │
        ▼ ПРЕДЛОЖЕНИЕ КВЕСТА:
           "Пока ждёшь хакатон — проверь свои навыки
            критического мышления в квесте «Гидра Сингулярности»!"
           [🎮 Пройти квест] [❌ Нет, спасибо]
           │
           ├── [🎮 Квест] → переход в handlers/quest.py
           └── [❌ Нет] → ARENA_DONE (финальный экран)
```

---

## 2. FSM-СОСТОЯНИЯ АРЕНЫ

```python
class ArenaStates(StatesGroup):
    INTRO = State()              # Экран приглашения на хакатон
    QUESTION_1 = State()         # Вопрос: уровень опыта
    QUESTION_2 = State()         # Вопрос: инструменты
    QUESTION_3 = State()         # Вопрос: цель участия
    QUALIFICATION_RESULT = State()  # Результат квалификации
    ARENA_PHONE = State()        # Ввод телефона
    ARENA_EMAIL = State()        # Ввод email
    ARENA_CONFIRM = State()      # Подтверждение контактов
    ARENA_DONE = State()         # Финал (предложение квеста)
```

---

## 3. КВАЛИФИКАЦИОННЫЕ ВОПРОСЫ

### Структура (content/texts.json)

Вопросы и варианты ответов хранятся в texts.json, не хардкодятся:

```json
{
    "arena_intro": "⚔️ <b>АРЕНА НЕЙРО-ЮНИТ: ХАКАТОН</b>\n\nТы уже знаком с нейросетями и хочешь большего?\n\nМы проводим хакатон — конкурс по созданию проектов с помощью ИИ. Лучшие участники получат ценные призы!\n\nЧтобы попасть, ответь на 3 коротких вопроса о своём уровне подготовки.",

    "arena_q1": "📊 <b>Вопрос 1/3: Опыт</b>\n\nКак давно ты используешь нейросети в работе или учёбе?",
    "arena_q1_opt_beginner": "🟢 Только начинаю",
    "arena_q1_opt_intermediate": "🟡 Несколько месяцев",
    "arena_q1_opt_advanced": "🔴 Больше года, использую ежедневно",

    "arena_q2": "🛠 <b>Вопрос 2/3: Инструменты</b>\n\nКакие ИИ-инструменты ты используешь?",
    "arena_q2_opt_chat": "💬 ChatGPT / Claude",
    "arena_q2_opt_image": "🎨 Midjourney / DALL-E / Stable Diffusion",
    "arena_q2_opt_dev": "🛠 API, автоматизации, собственные решения",
    "arena_q2_opt_all": "📦 Всё вышеперечисленное",

    "arena_q3": "🎯 <b>Вопрос 3/3: Цель</b>\n\nЧто хочешь создать на хакатоне?",
    "arena_q3_opt_bot": "🤖 Чат-бота или ассистента",
    "arena_q3_opt_analytics": "📊 Аналитический инструмент",
    "arena_q3_opt_content": "🎨 Генератор контента",
    "arena_q3_opt_custom": "💡 Свой проект (расскажу)",

    "arena_qualification_result": "🎉 <b>Отлично! Твой профиль:</b>\n\n📊 Опыт: {experience}\n🛠 Инструменты: {tools}\n🎯 Цель: {goal}\n\n✅ Ты подходишь для участия в хакатоне!\n\nОставь контакты — мы пригласим тебя, когда откроется регистрация.",

    "arena_contacts_saved": "✅ <b>Заявка принята!</b>\n\nТы в списке кандидатов на хакатон.\nМы свяжемся с тобой, когда начнётся регистрация.\n\nА пока — проверь свои навыки критического мышления в квесте «Гидра Сингулярности»!",

    "arena_done": "👋 <b>Спасибо за интерес!</b>\n\nМы свяжемся с тобой по поводу хакатона.\n\nЕсли передумаешь пройти квест — напиши /start"
}
```

### Сохранение ответов в PostgreSQL

Ответы квалификации хранятся в таблице users (новые поля):

```sql
ALTER TABLE users ADD COLUMN arena_q1_experience VARCHAR(50);  -- beginner / intermediate / advanced
ALTER TABLE users ADD COLUMN arena_q2_tools VARCHAR(50);        -- chat / image / dev / all
ALTER TABLE users ADD COLUMN arena_q3_goal VARCHAR(50);         -- bot / analytics / content / custom
```

Или в основном schema.sql при первичном создании:

```sql
CREATE TABLE IF NOT EXISTS users (
    -- ... (существующие поля) ...
    
    -- Арена (хакатон)
    arena_registered BOOLEAN DEFAULT FALSE,
    arena_q1_experience VARCHAR(50),    -- beginner / intermediate / advanced
    arena_q2_tools VARCHAR(50),          -- chat / image / dev / all
    arena_q3_goal VARCHAR(50),           -- bot / analytics / content / custom
    
    -- ...
);
```

### Скоринг лида (для менеджера)

По ответам можно определить «температуру» лида:

| Опыт | Инструменты | Цель | Скоринг |
|------|-------------|------|---------|
| advanced | dev / all | любая | 🔥 Горячий |
| intermediate | любые | bot / analytics | 🟡 Тёплый |
| beginner | chat | любая | 🟢 Холодный |

Скоринг не показывается пользователю — это данные для менеджера при обработке лида.

---

## 4. HANDLERS/ARENA.PY — РЕАЛИЗАЦИЯ

### Обработчики

```python
# Вход на арену
@router.callback_query(F.data == "start:arena")
async def cb_arena_intro(callback, state):
    await state.set_state(ArenaStates.INTRO)
    await callback.message.answer(
        ContentManager.get_raw("arena_intro"),
        reply_markup=arena_intro_keyboard()  # [🏆 Хочу участвовать!] [⬅️ Назад]
    )

# Начало квалификации
@router.callback_query(F.data == "arena:participate")
async def cb_arena_start(callback, state):
    await state.set_state(ArenaStates.QUESTION_1)
    await callback.message.answer(
        ContentManager.get_raw("arena_q1"),
        reply_markup=arena_q1_keyboard()
    )

# Ответ на вопрос 1 → переход к вопросу 2
@router.callback_query(F.data.startswith("arena:q1:"))
async def cb_arena_q1(callback, state, pool):
    answer = callback.data.split(":")[-1]  # beginner / intermediate / advanced
    await state.update_data(arena_q1=answer)
    await state.set_state(ArenaStates.QUESTION_2)
    await callback.message.answer(
        ContentManager.get_raw("arena_q2"),
        reply_markup=arena_q2_keyboard()
    )

# Ответ на вопрос 2 → переход к вопросу 3
@router.callback_query(F.data.startswith("arena:q2:"))
async def cb_arena_q2(callback, state):
    answer = callback.data.split(":")[-1]
    await state.update_data(arena_q2=answer)
    await state.set_state(ArenaStates.QUESTION_3)
    await callback.message.answer(
        ContentManager.get_raw("arena_q3"),
        reply_markup=arena_q3_keyboard()
    )

# Ответ на вопрос 3 → результат квалификации
@router.callback_query(F.data.startswith("arena:q3:"))
async def cb_arena_q3(callback, state, pool):
    answer = callback.data.split(":")[-1]
    await state.update_data(arena_q3=answer)
    data = await state.get_data()
    
    # Показываем результат
    await state.set_state(ArenaStates.QUALIFICATION_RESULT)
    await callback.message.answer(
        ContentManager.get("arena_qualification_result",
            experience=EXPERIENCE_LABELS[data['arena_q1']],
            tools=TOOLS_LABELS[data['arena_q2']],
            goal=GOAL_LABELS[data['arena_q3']]
        ),
        reply_markup=arena_contacts_keyboard()  # [📱 Оставить контакты]
    )

# Далее → сбор контактов (ARENA_PHONE → ARENA_EMAIL → ARENA_CONFIRM)
# Используем ту же логику, что в handlers/contacts.py

# После подтверждения контактов → сохранение + предложение квеста
async def arena_contacts_confirmed(callback, state, pool, user_id):
    data = await state.get_data()
    
    # Сохраняем контакты и ответы квалификации
    await pool.execute("""
        UPDATE users SET
            phone = $2, email = $3,
            arena_registered = TRUE,
            arena_q1_experience = $4,
            arena_q2_tools = $5,
            arena_q3_goal = $6
        WHERE user_id = $1
    """, user_id, data['phone'], data['email'],
         data['arena_q1'], data['arena_q2'], data['arena_q3'])
    
    # Уведомляем админов
    await notify_arena_lead(bot, user_id, data)
    
    # Предлагаем квест
    await callback.message.answer(
        ContentManager.get_raw("arena_contacts_saved"),
        reply_markup=arena_quest_offer_keyboard()
        # [🎮 Пройти квест] [❌ Нет, спасибо]
    )
```

---

## 5. КЛАВИАТУРЫ АРЕНЫ

```python
def arena_intro_keyboard():
    """[🏆 Хочу участвовать!] [⬅️ Назад]"""

def arena_q1_keyboard():
    """3 кнопки: beginner / intermediate / advanced"""

def arena_q2_keyboard():
    """4 кнопки: chat / image / dev / all"""

def arena_q3_keyboard():
    """4 кнопки: bot / analytics / content / custom"""

def arena_contacts_keyboard():
    """[📱 Оставить контакты]"""

def arena_quest_offer_keyboard():
    """[🎮 Пройти квест] [❌ Нет, спасибо]"""
```

Все тексты кнопок — из content/texts.json (не хардкод).

---

## 6. ГЕНЕРАТОР ВИДЕО

### Текущий код
В стартовом меню кнопка "🎬 Генератор видео" → текст + ссылка на бота.

### Новая реализация
Минимальная: inline-кнопка с URL на внешнего бота.

```python
# В handlers/start.py
@router.callback_query(F.data == "start:generator")
async def cb_generator(callback: CallbackQuery):
    await callback.message.answer(
        ContentManager.get_raw("generator_info"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Открыть Генератор", url=GENERATOR_BOT_URL)]
        ])
    )
```

Нет собственной логики — просто редирект.

---

## 7. ОБНОВЛЕНИЕ СТАРТОВОГО МЕНЮ

### Текущее меню
```
[🚀 Начать квест]
[📚 Узнать больше о курсе]
```

### Новое меню (по ТЗ)
```
[🎮 Начать Квест]
[🎬 Генератор видео]
[⚔️ Арена]
```

Кнопка "О курсе" убирается из главного меню (информация о курсе → мораль после квеста).

---

## 8. СОБЫТИЯ ДЛЯ АНАЛИТИКИ

| Событие | Момент | Данные |
|---------|--------|--------|
| `arena_start` | Нажал [⚔️ Арена] | — |
| `arena_participate` | Нажал [🏆 Хочу участвовать!] | — |
| `arena_q1_answered` | Ответил на вопрос 1 | {answer: "advanced"} |
| `arena_q2_answered` | Ответил на вопрос 2 | {answer: "all"} |
| `arena_q3_answered` | Ответил на вопрос 3 | {answer: "bot"} |
| `arena_contacts_saved` | Оставил контакты | — |
| `arena_to_quest` | Перешёл к квесту | — |
| `arena_declined_quest` | Отказался от квеста | — |

---

## 9. УВЕДОМЛЕНИЕ АДМИНАМ О ЛИДЕ АРЕНЫ

Когда пользователь оставляет контакты через арену, админы получают:

```
⚔️ НОВЫЙ ЛИД С АРЕНЫ

User: @username (ID: 123456)
Имя: Иван

📊 Квалификация:
  Опыт: Больше года, использую ежедневно
  Инструменты: Всё вышеперечисленное
  Цель: Чат-бота или ассистента

📱 Телефон: +79161234567
📧 Email: ivan@mail.ru

🔥 Скоринг: ГОРЯЧИЙ
```

Скоринг рассчитывается автоматически по ответам (горячий/тёплый/холодный).

---

## 10. УЛУЧШЕНИЯ ЭТОГО ЭТАПА

### 10.1 Технологические
- **Ответы квалификации в PostgreSQL** — данные для CRM/менеджера, не теряются
- **FSM в Redis** — ArenaStates не конфликтует с QuestStates
- **Event tracking** — полная аналитика воронки арены

### 10.2 Функциональные
- **Скоринг лидов** — автоматическая оценка "температуры" по ответам
- **Арена → Квест** — cross-path: продвинутые пользователи тоже проходят квест
- **arena_registered в PostgreSQL** — отдельный флаг для фильтрации при рассылках и аналитике
- **Уведомления админам** — мгновенное получение горячего лида

### 10.3 Для вовлечённости
- **Хакатон как мотиватор** — "ценные призы" создают ощущение эксклюзивности
- **3 вопроса — не 10** — минимальный барьер, пользователь не устаёт
- **Персонализированный результат** — "Твой профиль: Опыт: X, Инструменты: Y" — пользователь чувствует, что его оценили
- **Мост к квесту** — "Пока ждёшь хакатон — проверь навыки в квесте" — естественный переход без давления
- **Статус "кандидат на хакатон"** — пользователь чувствует, что прошёл отбор (даже если отбора нет)
- **Прогресс-бар** — "Вопрос 1/3", "Вопрос 2/3", "Вопрос 3/3" — видимый прогресс снижает отвал

---

## 11. ЧЕК-ЛИСТ ЭТАПА

- [ ] Создан handlers/arena.py (приглашение → 3 вопроса → контакты → квест)
- [ ] ArenaStates в FSM (9 состояний, Redis)
- [ ] 3 квалификационных вопроса с вариантами ответов
- [ ] Все тексты и варианты ответов в content/texts.json
- [ ] Сбор контактов (телефон + email) по стандартной схеме
- [ ] Ответы квалификации сохраняются в PostgreSQL (arena_q1, arena_q2, arena_q3)
- [ ] arena_registered = TRUE при сохранении контактов
- [ ] Уведомление админам с профилем и скорингом лида
- [ ] Предложение квеста после контактов
- [ ] Арена проходится один раз (повторный вход → "Заявка уже принята")
- [ ] Генератор: inline-кнопка с URL
- [ ] Стартовое меню: 3 кнопки (Квест, Генератор, Арена)
- [ ] Events: arena_start, arena_participate, arena_q1-q3, arena_contacts_saved
- [ ] Деактивация кнопок после нажатия
- [ ] Тест: полный проход арены → контакты → предложение квеста

---

## 12. ЗАВИСИМОСТИ

- **Зависит от Этапов 1-2:** инфраструктура, ContentManager, middleware
- **Зависит от Этапа 3:** стартовое меню (start.py), навигация между ветками
- **Этап 5 зависит от этого этапа:** сбор контактов может быть инициирован из арены (ARENA_PHONE/EMAIL используют ту же логику валидации)

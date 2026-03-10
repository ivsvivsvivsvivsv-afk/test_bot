# ЭТАП 7: Система дожима, Worker и механика удержания

## САММАРИ

**Цель:** Реализовать worker.py (отдельный процесс для scheduler и рассылок) и полную механику дожима: idle-напоминания + 5-дневные миниквесты для пользователей, которые не записались на воркшоп.

**Что делаем:**
- `worker.py` — отдельный процесс с APScheduler (СТРОГО 1 экземпляр!)
- `middlewares/activity.py` — трекинг активности в Redis (SETEX с TTL, НЕ PostgreSQL!)
- `middlewares/throttle.py` — антиспам через Redis (rate limiting)
- `services/followup_service.py` — idle-проверка + ежедневные миниквесты
- `services/broadcast_service.py` — безопасная рассылка (20 msg/sec, TelegramRetryAfter)
- `services/notification_service.py` — уведомления админам
- Механика миниквестов: картинка + утверждение ПРАВДА/ЛОЖЬ + CTA воркшопа
- FollowupStates в FSM для обработки ответов на миниквесты

**Бизнес-логика дожима (из ТЗ):**
1. Пользователь завис на шаге >5 минут → одноразовое напоминание "Продолжи квест!"
2. Пользователь прошёл квест, НЕ записался на воркшоп → 5 дней миниквестов:
   - День 1-5: картинка + утверждение + похвала + предложение воркшопа
   - Если записался — upsell (если есть места)
   - Если не записался за 5 дней — прекращаем, не спамим

**Критические архитектурные правила:**
1. worker.py СТРОГО 1 экземпляр (systemd, НЕ Gunicorn)
2. Активность ТОЛЬКО в Redis (SETEX с TTL), НЕ в PostgreSQL (MVCC bloat при 10K юзеров)
3. Рассылки: asyncio.sleep(0.05) между сообщениями (20 msg/sec)
4. TelegramRetryAfter → await asyncio.sleep(e.retry_after)
5. TelegramForbiddenError → UPDATE users SET is_blocked = TRUE (в finally!)
6. MGET вместо redis.exists() в цикле (N+1 problem)
7. Медиа через file_id (media_service), НЕ FSInputFile в циклах

**Что нового (нет в текущем коде):**
- Полностью новый модуль — в текущем боте нет дожима
- 5 картинок миниквестов (content/media/)
- 5 дней нарративов (Гидра восстанавливается)
- 5 разных CTA для воркшопа (эскалация срочности)

---

## 1. WORKER.PY — ОТДЕЛЬНЫЙ ПРОЦЕСС

### Почему отдельный процесс
Gunicorn запускает 4 воркера. Если APScheduler внутри Gunicorn:
- 4 воркера × 1 scheduler = 4 scheduler-а
- Рассылка дня 1 уйдёт 4 раза каждому пользователю → бан Telegram

### Архитектура worker.py
```python
# worker.py — запускается через systemd
# НЕ через Gunicorn!

async def main():
    pool = await create_pool(...)       # свой пул (min=2, max=5)
    redis_conn = await create_redis(...)
    bot = Bot(token=BOT_TOKEN)
    
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    
    # Задача 1: проверка зависших (каждые 60 сек)
    scheduler.add_job(check_idle_users, 'interval', seconds=60,
                      args=[bot, pool, redis_conn])
    
    # Задача 2: миниквесты (каждый день в 11:00 МСК)
    scheduler.add_job(send_daily_miniquest, 'cron', hour=11, minute=0,
                      args=[bot, pool, redis_conn])
    
    scheduler.start()
    await asyncio.Event().wait()  # Бесконечный цикл
```

---

## 2. ТРЕКИНГ АКТИВНОСТИ — Redis, НЕ PostgreSQL

### Проблема
При 10 000 активных пользователей `UPDATE last_activity_at = NOW()` на каждый клик:
- 10 000 UPDATE/минуту × 60 = 600 000 UPDATE/час
- PostgreSQL MVCC: каждый UPDATE создаёт новую версию строки
- VACUUM не успевает → таблица раздувается → замедление

### Решение: Redis SETEX
```python
# middlewares/activity.py
class ActivityMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user:
            # SETEX: ключ = activity:{user_id}, TTL = 5 мин, значение = "1"
            await redis.setex(f"activity:{user.id}", 300, "1")
        return await handler(event, data)
```

Если ключ `activity:{user_id}` существует → пользователь активен.
Если ключа нет → пользователь завис >5 минут.

### Проверка зависших
```python
# services/followup_service.py
async def check_idle_users(bot, pool, redis_conn):
    # Берём пользователей в активном квесте, которым не слали напоминание
    active_users = await pool.fetch("""
        SELECT user_id FROM users
        WHERE quest_completed = FALSE
          AND quest_state NOT IN ('start', 'completed', 'final')
          AND followup_stage = 0
          AND is_blocked = FALSE
    """)
    
    # MGET — один запрос вместо N отдельных exists()
    keys = [f"activity:{u['user_id']}" for u in active_users]
    statuses = await redis_conn.mget(keys)
    
    # Зависшие = те, у кого ключ = None
    idle_users = [u for u, s in zip(active_users, statuses) if s is None]
    
    for user in idle_users:
        # Помечаем ПЕРЕД отправкой (чтобы не слать повторно при ошибке)
        await pool.execute("UPDATE users SET followup_stage = -1 WHERE user_id = $1",
                          user['user_id'])
        try:
            await bot.send_message(user['user_id'], ContentManager.get_raw("idle_reminder"))
        except TelegramForbiddenError:
            await pool.execute("UPDATE users SET is_blocked = TRUE WHERE user_id = $1",
                              user['user_id'])
```

---

## 3. МИНИКВЕСТЫ — 5 ДНЕЙ НАРРАТИВА

### Структура миниквеста
```
Картинка (content/media/miniquest_dayN.jpg) через file_id
  +
Нарративный текст (content/texts.json → miniquest_dayN)
  +
Утверждение ПРАВДА/ЛОЖЬ (из statements/{weapon}.txt)
  +
Результат: похвала / подбадривание
  +
CTA воркшопа (content/texts.json → workshop_cta_dayN)
  [📝 Записаться] [⏭ Позже]
```

### 5 дней нарратива (из ТЗ)

| День | Тема | Текст | Эскалация |
|------|------|-------|-----------|
| 1 | Гидра восстанавливается | "Пока ты бездействовал, Гидра начала восстанавливаться..." | Мягкая |
| 2 | Вторая голова оживает | "Ещё одна голова поднялась из тьмы..." | Средняя |
| 3 | Атака на Data Sanctuary | "Гидра подобралась к стенам Data Sanctuary!..." | Высокая |
| 4 | Последний рубеж | "Защитники устали. Они ждут тебя..." | Очень высокая |
| 5 | Финальный шанс | "Это последний день. Завтра ворота закроются..." | Максимальная |

### 5 CTA воркшопа (из ТЗ)
| День | CTA |
|------|-----|
| 1 | "Мы проводим бесплатный воркшоп, где ты научишься создавать ИИ-педагога за 30 минут" |
| 2 | "Что поможет победить Гидру? Практика! На воркшопе ты соберёшь первый НЕЙРОСКЕЛЕТ" |
| 3 | "Ты доказал, что умеешь отличать правду от лжи. Бесплатный воркшоп — следующий шаг" |
| 4 | "Ты сражаешься как герой! На воркшопе — полный арсенал ИИ-инструментов" |
| 5 | "Последний день. Последний шанс. Запишись и заверши трансформацию" |

### Логика отправки миниквеста
```python
async def send_daily_miniquest(bot, pool, redis_conn):
    """Вызывается 1 раз в день в 11:00 МСК"""
    
    users = await pool.fetch("""
        SELECT user_id, followup_stage, weapon FROM users
        WHERE quest_completed = TRUE
          AND workshop_registered = FALSE
          AND followup_stage BETWEEN 0 AND 4
          AND followup_completed = FALSE
          AND is_blocked = FALSE
          AND created_at <= NOW() - INTERVAL '1 day' * (followup_stage + 1)
    """)
    
    # Прекэширование file_id (1 раз, не 5000)
    for day in needed_days:
        file_ids[day] = await get_file_id(bot, redis_conn, MINIQUEST_IMAGES[day], admin_id)
    
    for user in users:
        day = user['followup_stage'] + 1
        try:
            # Картинка через file_id (НЕ FSInputFile!)
            await bot.send_photo(user['user_id'], photo=file_ids[day],
                                caption=ContentManager.get(f"miniquest_day{day}"))
            await asyncio.sleep(0.05)  # 20 msg/sec
            
            # Утверждение
            statement = get_statement_for_day(user['weapon'], day)
            await bot.send_message(user['user_id'], statement_text,
                                  reply_markup=miniquest_keyboard())
            await asyncio.sleep(0.05)
            
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except TelegramForbiddenError:
            await pool.execute("UPDATE users SET is_blocked = TRUE WHERE user_id = $1",
                              user['user_id'])
        finally:
            # ВСЕГДА обновляем stage (даже при ошибке!)
            await pool.execute("UPDATE users SET followup_stage = $1 WHERE user_id = $2",
                              day, user['user_id'])
```

### После ответа на миниквест
```
Пользователь отвечает ПРАВДА/ЛОЖЬ:
  → Похвала: "Отлично!" / "Не сдавайся!"
  → CTA воркшопа (текст дня)
  → [📝 Записаться] [⏭ Позже]
  
Если [📝 Записаться]:
  → Запросить контакты (если нет)
  → workshop_registered = TRUE
  → show_upsell_if_available() ← единая точка из Этапа 5!
  
Если [⏭ Позже]:
  → followup_completed = TRUE для этого дня
  → Завтра придёт следующий миниквест (если < 5)
```

---

## 4. MIDDLEWARES/THROTTLE.PY — АНТИСПАМ

### Логика
Не более 3 сообщений в секунду от одного пользователя:
```python
class ThrottleMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if not user: return await handler(event, data)
        
        key = f"throttle:{user.id}"
        now = time.time()
        last = await self.redis.get(key)
        
        if last and (now - float(last)) < 0.3:
            return  # Игнорируем спам
        
        await self.redis.set(key, str(now), ex=60)
        return await handler(event, data)
```

---

## 5. SERVICES/BROADCAST_SERVICE.PY

### Безопасная рассылка
```python
async def broadcast(bot, pool, text, **kwargs):
    """
    Рассылка всем неблокированным пользователям.
    Rate limit: 20 msg/sec (asyncio.sleep(0.05))
    """
    users = await pool.fetch("SELECT user_id FROM users WHERE is_blocked = FALSE")
    
    sent = 0
    failed = 0
    
    for user in users:
        try:
            await bot.send_message(user['user_id'], text, **kwargs)
            sent += 1
            await asyncio.sleep(0.05)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except TelegramForbiddenError:
            await pool.execute("UPDATE users SET is_blocked = TRUE WHERE user_id = $1",
                              user['user_id'])
            failed += 1
        except Exception:
            failed += 1
    
    return {"sent": sent, "failed": failed}
```

### Критическое правило: UPDATE в finally
```python
# НЕПРАВИЛЬНО:
try:
    await bot.send_message(...)
    await pool.execute("UPDATE users SET is_blocked = FALSE ...")
except:
    pass  # ← is_blocked не обновится!

# ПРАВИЛЬНО:
try:
    await bot.send_message(...)
except TelegramForbiddenError:
    blocked = True
except Exception:
    error = True
finally:
    if blocked:
        await pool.execute("UPDATE users SET is_blocked = TRUE ...")
```

---

## 6. SERVICES/NOTIFICATION_SERVICE.PY

### Уведомления админам
```python
async def notify_admins(bot, event_type, data):
    """Отправляет уведомление всем админам."""
    for admin_id in ADMIN_IDS:
        try:
            text = format_admin_notification(event_type, data)
            await bot.send_message(admin_id, text)
        except Exception:
            pass  # Админ мог заблокировать бота
```

### Типы уведомлений
- `new_user` — новый пользователь
- `quest_completed` — прошёл квест (score, class, weapon)
- `new_contact` — оставил контакты
- `workshop_registered` — записался на воркшоп
- `payment_success` — оплатил разбор
- `auto_refund` — автовозврат (zombie-платёж)
- `arena_completed` — прошёл арену

---

## 7. УЛУЧШЕНИЯ ЭТОГО ЭТАПА

### 7.1 Технологические
- **MGET вместо N×exists()** — один Redis-запрос вместо 5000
- **file_id кэш** — 5000 пользователей = 1 загрузка файла (вместо 5000)
- **asyncio.sleep(0.05)** — 20 msg/sec, не блокирует event loop
- **TelegramRetryAfter** — автоматическая адаптация к rate limits Telegram
- **finally блок** — is_blocked обновляется ВСЕГДА

### 7.2 Функциональные
- **5-дневный нарратив** — Гидра восстанавливается (поддержание интереса)
- **Персонализация** — утверждения по оружию пользователя (не случайные)
- **Эскалация CTA** — от мягкого "попробуй" до "последний шанс"
- **Остановка после 5 дней** — не спамим бесконечно

### 7.3 Для вовлечённости
- **Визуальный контент** — каждый день новая картинка (удержание внимания)
- **Мини-геймификация** — ежедневное задание ПРАВДА/ЛОЖЬ (привычка заходить в бот)
- **Нарратив** — Гидра не побеждена, она возвращается (мотивация)
- **Утреннее время** — 11:00 МСК (оптимальное время для Telegram-рассылок)
- **Связь с основным квестом** — утверждения по выбранному оружию (персонализация)
- **Мягкое давление** — "Защитники ждут тебя" → "Последний день" (градация)

---

## 8. КАРТИНКИ ДЛЯ МИНИКВЕСТОВ

### Необходимые файлы
```
content/media/
├── miniquest_day1.jpg   — Гидра восстанавливает голову
├── miniquest_day2.jpg   — Вторая голова оживает
├── miniquest_day3.jpg   — Атака на Data Sanctuary
├── miniquest_day4.jpg   — Последний рубеж обороны
└── miniquest_day5.jpg   — Финальная битва
```

Стиль: фэнтези/киберпанк, Гидра, цифровые эффекты, тёмные тона с яркими акцентами.

### Важно
Эти картинки нужно подготовить ДО деплоя. Без них миниквесты будут отправляться только текстом (fallback).

---

## 9. ЧЕК-ЛИСТ ЭТАПА

- [ ] Создан worker.py (APScheduler, 1 экземпляр, 2 задачи)
- [ ] Создан middlewares/activity.py (SETEX в Redis, TTL=5мин)
- [ ] Создан middlewares/throttle.py (rate limiting 3 msg/sec)
- [ ] Создан services/followup_service.py (check_idle_users, send_daily_miniquest)
- [ ] Создан services/broadcast_service.py (безопасная рассылка)
- [ ] Создан services/notification_service.py (notify_admins)
- [ ] Idle-проверка: MGET (не exists в цикле)
- [ ] Миниквесты: file_id через media_service (не FSInputFile)
- [ ] asyncio.sleep(0.05) между сообщениями
- [ ] TelegramRetryAfter → await sleep(retry_after)
- [ ] TelegramForbiddenError → is_blocked = TRUE (в finally!)
- [ ] FollowupStates в FSM (MINIQUEST_ACTIVE, MINIQUEST_ANSWER)
- [ ] 5 текстов миниквестов в texts.json
- [ ] 5 CTA воркшопа в texts.json
- [ ] 5 картинок в content/media/
- [ ] После миниквеста → [📝 Записаться] → контакты → upsell
- [ ] Остановка после 5 дней (не спамим)
- [ ] deploy/hydra-worker.service работает (1 экземпляр!)
- [ ] Тест: idle-напоминание (поставить FOLLOWUP_IDLE_MINUTES=1)
- [ ] Тест: миниквест дня 1 (вручную вызвать send_daily_miniquest)

---

## 10. ЗАВИСИМОСТИ

- **Зависит от Этапов 1-2:** Redis, PostgreSQL, ContentManager, media_service
- **Зависит от Этапа 3:** квест создаёт пользователей, которых будем дожимать
- **Зависит от Этапа 5:** upsell после воркшопа из дожима
- **Зависит от Этапа 6:** payment_service для upsell
- **Этап 8 зависит:** worker.service в systemd

# Требования к лендингу для интеграции с ботом

**Документ для синхронизации:** агент/разработчик лендинга (neurounit.fun) должен реализовать перечисленное ниже для единой админки и интеграции с Telegram-ботом.

**Связанные документы:**
- `UNIFIED_ADMIN_SPEC.md` — полная спецификация единой админки
- `PATCH_2_BROADCASTS_NOTIFICATIONS_ADMIN_STATS.md` — функционал бота (рассылки, уведомления, лиды)
- `BOT_API_CONTRACT.md` — notify-winner (если уже реализован)

---

## 1. Конфигурация (.env лендинга)

Добавить переменные:

```
BOT_API_URL=https://bot.neurounit.fun
ADMIN_API_SECRET=<общий_секрет_32+_байт>
```

- `ADMIN_API_SECRET` — один и тот же в .env бота и лендинга. Генерация: `openssl rand -hex 32`
- Секрет **никогда** не передавать в браузер (только серверные запросы)

Для sandbox окружения лендинга:
```
BOT_API_URL=https://bot-sandbox.neurounit.fun
ADMIN_API_SECRET=<sandbox_секрет>
```
Production и sandbox секреты должны отличаться.

---

## 2. Вызовы API бота (только с бэкенда)

Все запросы к боту выполняются **с сервера лендинга** (Flask/Python), не из JavaScript в браузере.

Заголовок для каждого запроса:
```
X-Admin-Secret: {ADMIN_API_SECRET}
```

### 2.1 Эндпоинты для реализации

| Эндпоинт | Метод | Когда вызывать |
|----------|-------|----------------|
| `{BOT_API_URL}/api/admin/stats` | GET | При загрузке дашборда `/admin` |
| `{BOT_API_URL}/api/admin/funnel?days=7` | GET | Блок «Воронка бота» на `/admin/stats` |
| `{BOT_API_URL}/api/admin/leads?limit=50&offset=0&status=&search=` | GET | Страница `/admin/leads` (лиды бота) |
| `{BOT_API_URL}/api/admin/segments` | GET | Форма рассылки (выпадающий список сегментов) |
| `{BOT_API_URL}/api/admin/broadcast` | POST | Кнопка «Запустить рассылку» |
| `{BOT_API_URL}/api/admin/notification-rules` | GET | Страница `/admin/notifications` |
| `{BOT_API_URL}/api/admin/notification-rules` | POST | Создание правила |
| `{BOT_API_URL}/api/admin/notification-rules/{id}` | PUT | Редактирование правила |
| `{BOT_API_URL}/api/admin/notification-rules/{id}` | DELETE | Удаление правила |
| `{BOT_API_URL}/api/admin/leads/{user_id}/notes` | POST | Добавление заметки к лиду |
| `{BOT_API_URL}/api/admin/leads/{user_id}/status` | PUT | Смена статуса лида |

### 2.2 Пример запроса (Python/Flask)

```python
import os
import requests

BOT_API_URL = os.environ.get("BOT_API_URL", "https://bot.neurounit.fun")
ADMIN_API_SECRET = os.environ.get("ADMIN_API_SECRET", "")

def fetch_bot_stats():
    resp = requests.get(
        f"{BOT_API_URL}/api/admin/stats",
        headers={"X-Admin-Secret": ADMIN_API_SECRET},
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    return resp.json()
```

---

## 3. UI-блоки для реализации

### 3.1 Дашборд (`/admin`)

Добавить блоки с данными бота (рядом с существующими блоками лендинга):

- **Пользователи бота:** users_total, users_today
- **Лиды бота:** leads_quest, leads_arena
- **Оплаты:** payments_succeeded, revenue
- **Призы с лендинга:** winners_notified, winners_pending (если бот отдаёт)

### 3.2 Страница лидов (`/admin/leads`)

- Объединить лиды лендинга (leads.db) и лиды бота (API)
- Колонка «Источник»: «Лендинг · Оферта», «Лендинг · Игра», «Бот · Квест», «Бот · Арена»
- Для лидов бота: статус, заметки, кнопки «Добавить заметку», «Сменить статус»

### 3.3 Рассылки (`/admin/broadcasts`)

- Форма: текст (textarea), сегмент (select из API `/segments`), «Сейчас» / «В указанное время»
- Превью: «Будет отправлено ~N пользователям» (count из segments)
- Кнопка «Запустить» → POST `/api/admin/broadcast`

### 3.4 Автоуведомления (`/admin/notifications`)

- Список правил (GET `/api/admin/notification-rules`)
- Форма создания/редактирования: название, текст, сегмент, триггер, расписание
- Вкл/выкл без удаления

### 3.5 Статистика (`/admin/stats`)

- Блок «Воронка бота» (GET `/api/admin/funnel`)
- Ссылка на Graspil (если настроен)

---

## 4. Webhook: оплата на сайте → уведомление в Telegram

Если на сайте (лендинге или отдельном) есть приём оплаты и нужно уведомить пользователя в Telegram:

**POST** `{BOT_API_URL}/api/webhook/site`

Заголовки:
```
X-Site-Secret: {SITE_WEBHOOK_SECRET}
Content-Type: application/json
```

Тело:
```json
{
  "event": "payment_succeeded",
  "user_phone": "+79001234567",
  "amount": 5000,
  "order_id": "order_123",
  "metadata": {}
}
```

- `SITE_WEBHOOK_SECRET` — отдельный секрет, хранится в .env сайта и бота
- Бот ищет пользователя по `phone`, шлёт сообщение в Telegram
- Идемпотентность: при повторной отправке (retry) бот проверяет `order_id`, не шлёт дубль

---

## 5. notify-winner (уже есть?)

Если лендинг при выигрыше в игре «Угадай ИИ-клона» шлёт уведомление в Telegram — контракт в `BOT_API_CONTRACT.md`. Убедиться, что используется корректный секрет и URL.

---

## 6. Чек-лист для лендинга

- [ ] Добавлены `BOT_API_URL`, `ADMIN_API_SECRET` в .env
- [ ] Реализованы серверные вызовы к API бота (не из браузера)
- [ ] Дашборд: блоки с данными бота
- [ ] Лиды: объединённый вид (лендинг + бот)
- [ ] Рассылки: форма, превью, POST broadcast
- [ ] Автоуведомления: CRUD правил
- [ ] Статистика: воронка бота
- [ ] (Опционально) Webhook оплаты: POST /api/webhook/site при payment_succeeded
- [ ] Секреты не попадают в HTML/JS (только сервер)

---

## 7. Порядок реализации

1. **Бот** реализует API (`/api/admin/*`, `/api/webhook/site`) — см. PATCH_2
2. **Лендинг** добавляет конфиг и первые вызовы (stats, funnel)
3. **Лендинг** расширяет UI (лиды, рассылки, уведомления)
4. **Интеграция** webhook оплаты (если нужна)

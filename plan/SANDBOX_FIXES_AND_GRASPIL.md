# Sandbox: что не работает и как чинить

## 1. bot-sandbox.neurounit.fun — «Страница недоступна» (ERR_EMPTY_RESPONSE)

**Что это за ссылка.** `bot-sandbox.neurounit.fun` — это **HTTP API бота**, а не веб-сайт. Здесь нет лендинга: только health-check и эндпоинты для админки. Открывать её в браузере имеет смысл только для проверки (`/health`, `/api/admin/*`).

**Причина ERR_EMPTY_RESPONSE.** Nginx проксирует `location /` на `127.0.0.1:18443`. Если Gunicorn (бот) не слушает или не отвечает — upstream не отдаёт данные, nginx возвращает пустой ответ → браузер показывает ERR_EMPTY_RESPONSE.

**Диагностика:**
```bash
# На сервере
systemctl status hydra-bot-sandbox
ss -tlnp | grep 18443
curl -sS -m 5 http://127.0.0.1:18443/health
journalctl -u hydra-bot-sandbox -n 100 --no-pager
```

Если `curl` таймаутит — бот не запустился или падает при старте (часто: Redis/Postgres, некорректный BOT_TOKEN, ошибка в on_startup).

**Когда бот работает**, по `/` и `/health` возвращается JSON `{"service":"hydra-bot","postgres":"ok","redis":"ok"}`. Для человекопонятной страницы см. реализацию `handle_root` в bot.py.

---

## 2. Bot API недоступен (лендинг не видит данные)

**Проверить в `.env` лендинга:**
```
BOT_API_URL=http://bot-sandbox.neurounit.fun
ADMIN_API_SECRET=<то же значение, что в .env бота>
```

Для sandbox использовать **HTTP**, т.к. SSL для `bot-sandbox` ещё не выпущен.  
Секрет взять с сервера бота: `grep ADMIN_API_SECRET /opt/hydra_bot_sandbox/.env`.

**Дополнительно.** По логам воркеры бота перезапускаются или зависают (Unclosed client session, Worker exiting). Стоит перезапустить:
```bash
sudo systemctl restart hydra-bot-sandbox hydra-worker-sandbox
```
и проверить логи:
```bash
journalctl -u hydra-bot-sandbox -f
```
Если есть ошибки подключения к Redis/PostgreSQL — поправить REDIS_URL, DB_HOST в `.env` бота.

---

## 3. Правила автоуведомлений — должны быть прямо в админке

**Бот.** API уже реализован и работает:
- `GET /api/admin/notification-rules` — список
- `POST /api/admin/notification-rules` — создание
- `PUT /api/admin/notification-rules/{id}` — изменение
- `DELETE /api/admin/notification-rules/{id}` — удаление

**Лендинг.** Нужно реализовать UI **прямо в админке** на странице автоуведомлений:
- Таблица/список правил (GET)
- Форма создания: название, текст, сегмент, триггер (`scheduled_once` / `scheduled_recurring`), `trigger_config`:
  - `scheduled_once`: `{"send_at": "2025-03-15T10:00:00+03:00"}`
  - `scheduled_recurring`: `{"hour": 10, "minute": 0, "days": [0,1,2,3,4,5,6]}` (пн=0, вс=6)
- Редактирование и удаление (PUT, DELETE)
- Переключатель вкл/выкл (поле `enabled`)

Сообщение «Правила не реализованы / API недоступен» появляется, когда лендинг не может достучаться до бота (BOT_API_URL, ADMIN_API_SECRET) **или** когда в лендинге нет соответствующего UI. Контракт для лендинга — в `REQUIREMENTS_FOR_LANDING.md`, раздел 3.4.

---

## 4. Graspil — что даёт API и почему «просто ссылку» не хватает

**Изучены методы Graspil API** (docs.graspil.com):

| Метод | Назначение |
|-------|------------|
| `POST /v1/send-batch-update` | Отправка batch updates в Graspil |
| `POST /v1/send-update` | Отправка одного update в реальном времени |

**Чего нет в API.** Отдельного API для чтения аналитики, метрик, отчётов или выгрузки дашборда **нет**. Все отчёты (MAU/WAU/DAU, Actions, Bounce, Sessions, Conversions, UTM) доступны только в веб-интерфейсе app.graspil.com после авторизации.

**Дашборд запаролен.** Уникальной прямой ссылки на «ваш» дашборд нет — пользователь логинится на app.graspil.com и видит свои подключённые боты. Ссылка на бота внутри Graspil требует уже авторизованной сессии.

**Что можно сделать в админке:**
- Добавить `GRASPIL_DASHBOARD_URL=https://app.graspil.com` в конфиг лендинга.
- В блоке «Graspil» показывать кнопку «Открыть Graspil» → переход на app.graspil.com. Пользователь заходит сам.
- Никаких данных из Graspil в нашу админку «подтягивать» нельзя — API этого не поддерживает.

---

## 5. Чеклист для работы админки

| Шаг | Действие |
|-----|----------|
| 1 | Перезапустить `hydra-bot-sandbox`, проверить логи |
| 2 | В .env лендинга: `BOT_API_URL=http://bot-sandbox.neurounit.fun` |
| 3 | Скопировать `ADMIN_API_SECRET` из .env бота в .env лендинга |
| 4 | Проверить: `curl -H "X-Admin-Secret: СЕКРЕТ" http://bot-sandbox.neurounit.fun/api/admin/stats` |
| 5 | Выпустить SSL (когда DNS готов): `certbot --nginx -d bot-sandbox.neurounit.fun` |
| 6 | После SSL переключить лендинг на `BOT_API_URL=https://bot-sandbox.neurounit.fun` |

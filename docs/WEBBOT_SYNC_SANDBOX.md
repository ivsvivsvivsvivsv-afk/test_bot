# Синхронизация: WebBot Sandbox — сайт и бот

**Дата:** 2026-03-17  
**Проблема:** «Сессия не найдена» при старте WebBot. Нужно синхронизировать домены и проверить цепочку.

---

## 1. Карта доменов и серверов

| Домен | Сервер | Роль |
|-------|--------|------|
| **sandbox.neurounit.fun** | 91.107.121.129 (сайт) | Лендинг sandbox, `/webbot` — WebBot UI |
| **webbot.neurounit.fun** | 91.107.121.129 (сайт) | WebBot UI (тот же сервер) |
| **bot-sandbox.neurounit.fun** | 82.146.39.44 (бот) | Backend бота sandbox |

**Сайт и бот — разные серверы.** Nginx на сайте проксирует `/api/web/*` и `/static/media/*` на бота.

---

## 2. Цепочка запросов WebBot

```
Браузер (sandbox.neurounit.fun/webbot или webbot.neurounit.fun)
    → POST /api/web/session/start
    → Nginx на 91.107.121.129 (location /api/web/)
    → proxy_pass https://bot-sandbox.neurounit.fun
    → Бот на 82.146.39.44
```

**BASE URL для фронта:**
- `webbot.neurounit.fun` → `location.origin` (same-origin, прокси)
- `sandbox.neurounit.fun/webbot` → `WEB_BOT_API_URL` = `https://sandbox.neurounit.fun` (прокси)

---

## 3. Текущая проверка (17.03.2026)

| Проверка | Результат |
|----------|-----------|
| `GET https://bot-sandbox.neurounit.fun/health` | 200 OK |
| `POST https://bot-sandbox.neurounit.fun/api/web/session/start` | **404 Not Found** |
| `POST https://sandbox.neurounit.fun/api/web/session/start` | **404 Not Found** (прокси → бот) |
| `POST https://webbot.neurounit.fun/api/web/session/start` | **404 Not Found** (прокси → бот) |

**Вывод:** Прокси работает. **404 возвращает бот** — endpoint `/api/web/session/start` на боте не отвечает или путь другой.

---

## 4. Что проверить команде бота

1. **Endpoint зарегистрирован?**  
   `handlers/web_flow_http.py` → `register_web_flow_routes` → `POST /api/web/session/start`

2. **Прямой вызов с сервера бота:**
   ```bash
   curl -i -X POST "https://bot-sandbox.neurounit.fun/api/web/session/start" \
     -H "Content-Type: application/json" \
     -d '{"client_type":"web","scenario_id":"web_l1","ab_variant":"a","utm_source":"test"}'
   ```
   Ожидается: **200** и JSON с `session_token`, `state_snapshot`.

3. **Альтернативный путь?**  
   Если бот использует `/api/web/v1/session/start` — нужно обновить фронт и nginx.

4. **Логи бота** при запросе:
   ```bash
   journalctl -u hydra-bot-sandbox -n 50 -f
   ```

---

## 5. Конфиг сайта (sandbox)

**Файл:** `/var/www/neurounit_sandbox/.env`
```
BOT_API_URL=https://bot-sandbox.neurounit.fun
WEB_BOT_API_URL=https://sandbox.neurounit.fun
ADMIN_API_SECRET=<sandbox secret>
```

**Nginx:** `proxy_pass https://bot-sandbox.neurounit.fun` (без слэша в конце — URI передаётся целиком).

---

## 6. Контракт API (ожидаемый)

**POST** `/api/web/session/start`

Request:
```json
{
  "client_type": "web",
  "scenario_id": "web_l1",
  "ab_variant": "a",
  "utm_source": "webbot",
  "utm_medium": "",
  "utm_campaign": "",
  "referrer": ""
}
```

Response 200:
```json
{
  "ok": true,
  "session_token": "sess_xxx",
  "state_snapshot": {
    "step": "welcome",
    "step_id": "welcome",
    "state_version": 1,
    "ui_payload": {
      "text": "...",
      "actions": [{ "id": "begin", "label": "Начать квест" }]
    }
  }
}
```

---

## 7. Действия

- [ ] **Команда бота:** Убедиться, что `POST /api/web/session/start` возвращает 200 (не 404)
- [ ] **Команда сайта:** После исправления бота — повторить smoke-тест
- [ ] **CORS:** Бот должен разрешать `sandbox.neurounit.fun`, `webbot.neurounit.fun`, `neurounit.fun`

import os
import re
import json
from datetime import datetime

import telebot
from telebot import types
from flask import Flask, request

# ================== ENV ==================
# Required (set in Amvera variables/secrets):
# - TELEGRAM_BOT_TOKEN
# - WEBHOOK_URL = https://rs-zhurkinigor.amvera.io
# - WEBHOOK_SECRET = random long string
# Optional:
# - ADMIN_IDS = "123,456"
# - DATA_DIR = /data
# - KSON_*_VIDEO_NOTE_FILE_ID

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://rs-zhurkinigor.amvera.io")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
ADMIN_IDS = os.getenv("ADMIN_IDS", "0")

DATA_DIR = os.getenv("DATA_DIR", "/data")
IMAGES_PATH = os.path.join(DATA_DIR, "images.json")

KSON_START_VIDEO_NOTE_FILE_ID = os.getenv("KSON_START_VIDEO_NOTE_FILE_ID", "")
KSON_SUCCESS_VIDEO_NOTE_FILE_ID = os.getenv("KSON_SUCCESS_VIDEO_NOTE_FILE_ID", "")
KSON_HACKATHON_VIDEO_NOTE_FILE_ID = os.getenv("KSON_HACKATHON_VIDEO_NOTE_FILE_ID", "")

if not API_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL not set")
if not WEBHOOK_SECRET:
    raise ValueError("WEBHOOK_SECRET not set")

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)
users_db = {}

# ================== COMICS (15 images) ==================
IMAGES = {
    "command_center": "",
    "video_generator": "",
    "avatar_choice": "",
    "professions_overview": "",

    "prof_management": "",
    "prof_analytics": "",
    "prof_copywriting": "",
    "prof_design": "",
    "prof_marketing": "",

    "levels_3": "",
    "prompt_artifact": "",
    "contacts": "",

    "hackathon": "",
    "hackathon_qualify": "",
    "hackathon_register": "",
}

CAPTIONS = {
    "command_center": "🦸 Командный пункт активирован.\nВыбери портал.",
    "video_generator": "🎬 Портал генератора видео.\nЗапускаем конвейер.",
    "avatar_choice": "🦸 Выбор аватара.\nФрилансер или Босс?",
    "professions_overview": "🎒 Выбор профессии.\nОпредели класс героя.",

    "prof_management": "🧠 Класс: Менеджмент.\nВыбери уровень силы.",
    "prof_analytics": "📈 Класс: Аналитика.\nВыбери уровень силы.",
    "prof_copywriting": "✍️ Класс: Копирайтинг.\nВыбери уровень силы.",
    "prof_design": "🎨 Класс: Дизайн.\nВыбери уровень силы.",
    "prof_marketing": "📊 Класс: Маркетинг.\nВыбери уровень силы.",

    "levels_3": "⚡ 3 уровня: Новичок / Спец / Гений.",
    "prompt_artifact": "🎯 Артефакт‑промпт получен.\nИдём в Perplexity.",
    "contacts": "📱 Закрепляем доступ.\nТелефон и email.",

    "hackathon": "🏆 Арена открыта.\nИспытай силы.",
    "hackathon_qualify": "🏆 Выбор лиги.\nСпец / Гений / ИИ‑проект.",
    "hackathon_register": "📝 Регистрация на арену.\nТелефон и email.",
}

def webhook_path():
    return f"/webhook/{WEBHOOK_SECRET}"

def load_images():
    try:
        if os.path.exists(IMAGES_PATH):
            with open(IMAGES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k in IMAGES.keys():
                    if k in data and isinstance(data[k], str):
                        IMAGES[k] = data[k]
    except Exception:
        pass

def save_images():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(IMAGES_PATH, "w", encoding="utf-8") as f:
            json.dump(IMAGES, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def send_comic(chat_id, key):
    file_id = IMAGES.get(key, "")
    caption = CAPTIONS.get(key, "")
    if file_id:
        try:
            bot.send_photo(chat_id, file_id, caption=caption)
            return
        except Exception:
            pass
    if caption:
        bot.send_message(chat_id, caption)

# ================== PROMPTS ==================
PROMPTS = {
    "level1_boss": "Я стартапер/предприниматель в области [укажите вашу сферу]. Проанализируй моих топ-3 конкурентов в интернете (назови реальные компании): 1) Их сильные стороны, 2) Слабые стороны, 3) Как они используют ИИ для автоматизации. Дай мне конкретные идеи, как я могу обойти их используя нейросети для управления процессами.",
    "level2_boss": "Я владелец компании размером 10-15 человек. Напиши детальный бизнес-кейс: Как ИИ-ассистент может сократить расходы на 40% в первый год? Включи: 1) Точные процессы для автоматизации, 2) Расчет экономии по ролям, 3) ROI и payback period, 4) Внедрение по месяцам, 5) Риски и как их минимизировать, 6) Примеры реальных компаний которые это сделали.",
    "level3_boss": "Я CEO компании. Создай стратегию полной трансформации: Как построить автономную систему, где ИИ-агенты полностью управляют бизнес-процессами без людей? Дай мне: 1) Архитектуру системы (какие ИИ-агенты, как они взаимодействуют), 2) Какие процессы автоматизировать в первую очередь для MAX ROI, 3) Полный roadmap на 12 месяцев, 4) Метрики успеха для каждого этапа, 5) Как переучить команду на роль супервизоров ИИ, 6) Бюджет и точные сроки, 7) Примеры компаний которые масштабировались 10x через ИИ автоматизацию.",

    "level1_copywriting": "Я фрилансер, специализирующийся на копирайтинге. Напиши 3 мега-продающих заголовка для посадочной страницы курса 'Как стать ИИ-супер-фрилансером'. Каждый заголовок должен срабатывать на боль: нехватка клиентов, низкие ставки, конкуренция. Дай мне готовую структуру лендинга с копией.",
    "level2_copywriting": "Я копирайтер. Напиши полный продающий email-последовательность (5 писем) для привлечения клиентов на курс 'Нейро-юнит'. Каждое письмо должно: 1) Вызывать боль, 2) Показывать решение через ИИ, 3) Давать социальное доказательство, 4) Заканчиваться CTA.",
    "level3_copywriting": "Я копирайтер-эксперт. Создай вирусную контент-стратегию для TikTok, которая будет привлекать фрилансеров на курс 'Нейро-юнит'. Дай: 1) 10 идей вирусных видео, 2) Скрипты для каждого, 3) Когда постить, 4) Как измерять результаты, 5) Как превращать лайки в продажи курса.",

    "level1_design": "Я UI/UX дизайнер. Напиши prompt для ChatGPT, чтобы создать макеты 5 вариантов посадочной страницы курса 'Нейро-юнит для дизайнеров'. Промт должен включить: 1) Цветовую схему, 2) Layout, 3) Типографию, 4) CTA элементы.",
    "level2_design": "Я дизайнер. Проанализируй топ-10 самых конвертящих лендингов в интернете (укажи реальные примеры). Для каждого скажи: 1) Почему он продает, 2) Какой психологический принцип использует, 3) Как я могу применить это в своем дизайне, 4) Какие ошибки допускают конкуренты.",
    "level3_design": "Я опытный дизайнер. Создай систему, как автоматизировать весь процесс дизайна посадочных страниц используя ИИ-генераторы (Figma AI, MidJourney, Runwayml). Дай: 1) Полный workflow, 2) Какие инструменты использовать на каждом этапе, 3) Как сохранить индивидуальность, 4) Как масштабировать и продавать дизайн.",

    "level1_marketing": "Я маркетолог. Напиши GTM (go-to-market) стратегию для курса 'Нейро-юнит'. Включи: 1) Целевую аудиторию, 2) Каналы привлечения, 3) Бюджет на каждый канал, 4) Метрики успеха, 5) Как привлечь первых 100 учеников.",
    "level2_marketing": "Я маркетолог. Проанализируй, почему ИИ-курсы продаются хорошо (реальные примеры: Udemy, Skillshare). Скажи: 1) Общие закономерности, 2) Что работает в описании, 3) Какие боли они решают, 4) Как они позиционируют себя, 5) Прайсинг-стратегия.",
    "level3_marketing": "Я маркетолог-эксперт. Напиши полную стратегию вирусного роста для курса 'Нейро-юнит'. Включи: 1) Как сделать его реферальным, 2) Как создать сообщество, 3) Как использовать ИИ для персонализации маркетинга, 4) Как масштабировать на 10k студентов, 5) LTV и CAC.",

    "level1_analytics": "Я аналитик. Дай мне промт-шаблон для создания дашборда в Excel/Google Sheets, который показывает ключевые метрики онлайн-курса: 1) Конверсия, 2) Retention, 3) Средний чек, 4) LTV. Включи формулы и как их понимать.",
    "level2_analytics": "Я аналитик данных. Напиши аналитический отчет: Какие метрики важны для трекинга успеха ИИ-фрилансера? Включи: 1) Метрики заработка, 2) Метрики скорости выполнения задач, 3) Метрики качества, 4) Как их сравнивать с фрилансерами без ИИ.",
    "level3_analytics": "Я senior аналитик. Создай систему аналитики, которая показывает ROI от внедрения ИИ в бизнес. Дай: 1) Какие данные собирать, 2) Как их обрабатывать, 3) Визуализация для топ-менеджмента, 4) Предиктивные модели, 5) Как принимать решения на основе данных.",

    "level1_management": "Я менеджер/руководитель. Помоги внедрить ИИ в ежедневную работу. Составь список из 10 задач, которые можно делегировать ИИ уже сегодня (планирование, отчеты, письма, контроль задач, подготовка встреч). Для каждой задачи: пример промпта и ожидаемый результат.",
    "level2_management": "Я менеджер проектов/операционный менеджер. Составь систему управления задачами с ИИ: как вести бэклог, приоритизацию, статусы, риски, коммуникации и отчеты, чтобы экономить 5–10 часов в неделю. Дай шаблоны промптов и регламент на 7 дней внедрения.",
    "level3_management": "Я руководитель. Создай архитектуру 'ИИ-операционного ассистента': процессы, роли, входные данные, шаблоны, контроль качества и метрики эффективности. Цель: ускорить принятие решений и снизить ручной менеджмент в 3–5 раз. Дай пошаговый roadmap внедрения.",
}

PERPLEXITY_HELP = (
    "📱 **КАК НАЧАТЬ РАБОТУ С PERPLEXITY:**\n\n"
    "1. Откройте браузер и перейдите на https://www.perplexity.ai\n"
    "2. Нажмите **Sign Up** и создайте аккаунт (email или Google)\n"
    "3. После входа вы увидите поле для ввода запросов\n"
    "4. **Скопируйте промт ниже и вставьте его в Perplexity**\n"
    "5. Нажмите Enter и дождитесь результата\n"
    "6. Когда Perplexity выдаст ответ, **скопируйте результат и отправьте мне сюда или скриншот**\n\n"
    "⚡ **В день можно делать 3 глубоких исследования бесплатно!**"
)

AI_CHECKLIST_TEXT = (
    "📎 **БЕСПЛАТНЫЙ ЧЕК‑ЛИСТ ПО ИИ (стартовый набор):**\n"
    "1) 5 задач, которые лучше всего делегировать ИИ (текст, идеи, структура, анализ, план).\n"
    "2) Формула промпта: Роль → Контекст → Цель → Формат → Ограничения → Пример.\n"
    "3) Шаблон: «Ты — [роль]. Контекст: [ситуация]. Цель: [что нужно]. Формат: [таблица/список]. Ограничения: [срок/тон].»\n"
    "4) Проверка качества: попроси ИИ дать 3 альтернативы + список рисков/ошибок.\n"
    "5) Автоматизация: если задача повторяется 2+ раза в неделю — пора делать пайплайн.\n"
)

# ================== VALIDATION / LEADS ==================
def is_valid_phone(phone: str) -> bool:
    digits = re.sub(r"\D", "", phone or "")
    return len(digits) in (10, 11)

def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email or ""))

def send_lead_to_admin(name, phone, email, path, specialty=None, level=None, extra=None):
    try:
        admin_ids = [int(i.strip()) for i in ADMIN_IDS.split(",") if i.strip().isdigit()]
        if not admin_ids:
            return False

        extra_text = ""
        if extra and isinstance(extra, dict):
            for k, v in extra.items():
                extra_text += f"\n{k}: {v}"

        msg = (
            f"🔥 **НОВЫЙ ЛИД**\n\n"
            f"👤 Имя: {name}\n"
            f"📱 Телефон: {phone}\n"
            f"📧 Email: {email}\n"
            f"🎯 Тип: {path}\n"
            f"💼 Специальность: {specialty or '-'}\n"
            f"📚 Уровень: {level or '-'}\n"
            f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            f"{extra_text}"
        )

        for admin_id in admin_ids:
            bot.send_message(admin_id, msg, parse_mode="Markdown")
        return True
    except Exception:
        return False

def safe_send_video_note(chat_id, file_id, fallback_text):
    if file_id:
        try:
            bot.send_video_note(chat_id, file_id)
            return
        except Exception:
            pass
    bot.send_message(chat_id, fallback_text, parse_mode="Markdown")

# ================== ADMIN HTTP ==================
@app.get("/ping")
def ping():
    return "ok", 200

@app.post("/setup-webhook")
def setup_webhook():
    # Защита: только если заголовок совпадает с WEBHOOK_SECRET
    header_secret = request.headers.get("X-Setup-Secret", "")
    if header_secret != WEBHOOK_SECRET:
        return "forbidden", 403

    url = f"{WEBHOOK_URL}{webhook_path()}"
    bot.set_webhook(url=url)
    return "ok", 200

@app.post("/webhook/<secret>")
def webhook(secret):
    if secret != WEBHOOK_SECRET:
        return "forbidden", 403

    json_data = request.get_json(force=True, silent=True) or {}
    update = telebot.types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return "ok", 200

# ================== IMAGE BINDING ==================
@bot.message_handler(commands=["setimg"])
def setimg_cmd(msg):
    chat_id = msg.chat.id
    parts = (msg.text or "").split()
    if len(parts) < 2:
        bot.send_message(chat_id, "Команда: /setimg <key>\nНапример: /setimg command_center")
        return

    key = parts[1].strip()
    if key not in IMAGES:
        bot.send_message(chat_id, "Неизвестный key.\nНапиши /imgkeys чтобы увидеть список.")
        return

    users_db.setdefault(chat_id, {})
    users_db[chat_id]["stage"] = "waiting_image"
    users_db[chat_id]["waiting_image_key"] = key
    bot.send_message(chat_id, f"Ок. Отправь картинку для ключа: {key}")

@bot.message_handler(commands=["imgkeys"])
def imgkeys_cmd(msg):
    chat_id = msg.chat.id
    keys = "\n".join([f"- {k}" for k in IMAGES.keys()])
    bot.send_message(chat_id, "Ключи картинок:\n" + keys)

@bot.message_handler(commands=["imglist"])
def imglist_cmd(msg):
    chat_id = msg.chat.id
    lines = [f"{k}: {'OK' if v else 'EMPTY'}" for k, v in IMAGES.items()]
    bot.send_message(chat_id, "🖼 Статус картинок:\n" + "\n".join(lines))

@bot.message_handler(content_types=["photo", "document"])
def receive_image(msg):
    chat_id = msg.chat.id
    if users_db.get(chat_id, {}).get("stage") != "waiting_image":
        return

    key = users_db[chat_id].get("waiting_image_key")
    if not key:
        bot.send_message(chat_id, "Ошибка key. Напиши /setimg command_center")
        users_db[chat_id]["stage"] = "start"
        return

    file_id = msg.photo[-1].file_id if msg.content_type == "photo" else msg.document.file_id
    IMAGES[key] = file_id
    save_images()

    users_db[chat_id]["stage"] = "start"
    users_db[chat_id].pop("waiting_image_key", None)
    bot.send_message(chat_id, f"✅ Картинка сохранена: {key}")

# ================== USER FLOWS ==================
@bot.message_handler(commands=["start"])
def start(msg):
    chat_id = msg.chat.id
    users_db[chat_id] = {"stage": "start", "name": msg.from_user.first_name or "User"}

    send_comic(chat_id, "command_center")

    safe_send_video_note(
        chat_id,
        KSON_START_VIDEO_NOTE_FILE_ID,
        "📺 **Видеокружок KSON (заглушка):**\n"
        "«Добро пожаловать в Нейро‑Юнит. Выбирай портал: генератор видео, обучение ИИ или арена‑хакатон.»",
    )

    bot.send_message(
        chat_id,
        "👾 **СИСТЕМА АКТИВИРОВАНА.**\n\nТы в командном центре. Выбери портал:",
        parse_mode="Markdown",
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("🎬 Генератор видео", callback_data="go_video_bot"))
    markup.add(types.InlineKeyboardButton("🎓 Обучение ИИ (Нейро‑Юнит)", callback_data="go_learning"))
    markup.add(types.InlineKeyboardButton("🏆 Онлайн‑хакатон (для профи)", callback_data="go_hackathon"))
    bot.send_message(chat_id, "Выбирай:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "go_video_bot")
def go_video_bot(call):
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    users_db[chat_id]["path"] = "video_bot"
    send_comic(chat_id, "video_generator")
    bot.send_message(chat_id, "🎬 Портал «Генератор видео» открыт. (Заглушка: тут будет ссылка/переход на другого бота.)")

@bot.callback_query_handler(func=lambda c: c.data == "go_learning")
def go_learning(call):
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    users_db[chat_id]["stage"] = "start"
    users_db[chat_id]["path"] = "learning"

    send_comic(chat_id, "avatar_choice")

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("🎒 Фрилансер / Найм", callback_data="freelancer"))
    markup.add(types.InlineKeyboardButton("💼 Предприниматель / Босс", callback_data="boss"))

    bot.send_message(
        chat_id,
        "👾 **СИСТЕМА ОБНАРУЖЕНА.**\n\nВыбери своего Аватара:",
        parse_mode="Markdown",
        reply_markup=markup,
    )

@bot.callback_query_handler(func=lambda c: c.data == "go_hackathon")
def go_hackathon(call):
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    users_db[chat_id]["path"] = "hackathon"
    users_db[chat_id]["stage"] = "hackathon_qualify"

    send_comic(chat_id, "hackathon")

    bot.send_message(
        chat_id,
        "🏆 **АРЕНА ОТКРЫТА.**\n"
        "Чтобы подобрать тебе правильную лигу — ответь одним кликом:",
        parse_mode="Markdown",
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("⚡ Спец", callback_data="hack_tier_spec"))
    markup.add(types.InlineKeyboardButton("💥 Гений", callback_data="hack_tier_genius"))
    markup.add(types.InlineKeyboardButton("🤖 Уже есть ИИ‑проект", callback_data="hack_tier_project"))
    bot.send_message(chat_id, "Твой уровень:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["hack_tier_spec", "hack_tier_genius", "hack_tier_project"])
def hackathon_qualify(call):
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    users_db[chat_id]["hackathon_tier"] = call.data.replace("hack_tier_", "")
    users_db[chat_id]["stage"] = "hackathon_registration_wait_phone"

    send_comic(chat_id, "hackathon_qualify")

    safe_send_video_note(
        chat_id,
        KSON_HACKATHON_VIDEO_NOTE_FILE_ID,
        "📺 **Видеокружок KSON (хакатон, заглушка):**\n"
        "«Мини‑задачи, таймер, рейтинг и призовые места. Регистрируйся — и увидимся на арене.»",
    )

    send_comic(chat_id, "hackathon_register")
    bot.send_message(chat_id, "📱 Оставь номер телефона (11 цифр):")

@bot.callback_query_handler(func=lambda c: c.data in ["freelancer", "boss"])
def path_select(call):
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    users_db[chat_id]["path"] = call.data

    if call.data == "freelancer":
        send_comic(chat_id, "professions_overview")

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🧠 Менеджмент", callback_data="management"))
        markup.add(types.InlineKeyboardButton("📈 Аналитика", callback_data="analytics"))
        markup.add(types.InlineKeyboardButton("✍️ Копирайтинг", callback_data="copywriting"))
        markup.add(types.InlineKeyboardButton("🎨 Дизайн", callback_data="design"))
        markup.add(types.InlineKeyboardButton("📊 Маркетинг", callback_data="marketing"))

        bot.send_message(chat_id, "🎒 **ПРОФЕССИИ**\n\nВыбери направление:", parse_mode="Markdown", reply_markup=markup)

    else:
        send_comic(chat_id, "levels_3")

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📚 Уровень 1 — Новичок", callback_data="level_1_boss"))
        markup.add(types.InlineKeyboardButton("📘 Уровень 2 — Спец", callback_data="level_2_boss"))
        markup.add(types.InlineKeyboardButton("📕 Уровень 3 — Гений", callback_data="level_3_boss"))

        bot.send_message(chat_id, "💼 **БОСС**\n\nВыбери уровень:", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["copywriting", "design", "marketing", "analytics", "management"])
def specialty_select(call):
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    users_db[chat_id]["specialty"] = call.data

    prof_key_map = {
        "management": "prof_management",
        "analytics": "prof_analytics",
        "copywriting": "prof_copywriting",
        "design": "prof_design",
        "marketing": "prof_marketing",
    }
    send_comic(chat_id, prof_key_map.get(call.data, "professions_overview"))
    send_comic(chat_id, "levels_3")

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("📚 Уровень 1 — Новичок", callback_data=f"level_1_{call.data}"))
    markup.add(types.InlineKeyboardButton("📘 Уровень 2 — Спец", callback_data=f"level_2_{call.data}"))
    markup.add(types.InlineKeyboardButton("📕 Уровень 3 — Гений", callback_data=f"level_3_{call.data}"))

    bot.send_message(chat_id, "⚡ Выбери уровень силы:", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("level_"))
def level_select(call):
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})

    parts = call.data.split("_")
    level = parts[1]
    specialty = "_".join(parts[2:])

    users_db[chat_id]["current_level"] = level
    users_db[chat_id]["stage"] = "waiting_result"

    prompt_key = f"level{level}_{specialty}"
    if prompt_key not in PROMPTS:
        bot.send_message(chat_id, "⚠️ Для этого уровня пока нет задания. Напиши /start")
        return

    send_comic(chat_id, "prompt_artifact")

    prompt = PROMPTS[prompt_key]
    bot.send_message(chat_id, f"🎯 **ЗАДАНИЕ УРОВНЯ {level}:**\n\n{prompt}", parse_mode="Markdown")

    safe_send_video_note(
        chat_id,
        KSON_SUCCESS_VIDEO_NOTE_FILE_ID,
        "📺 **Видеокружок KSON (кейс, заглушка):**\n"
        "«Я собрал ИИ‑проект, который приносит доход: боль → продукт → контент → лид → воронка.\n"
        "ИИ закрыл контент, упаковку оффера и рутину. Система важнее магии.»",
    )

    bot.send_message(chat_id, PERPLEXITY_HELP, parse_mode="Markdown")
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Выполнил!", callback_data="done"))
    bot.send_message(chat_id, "Когда выполнишь — нажми кнопку:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "done")
def done(call):
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    users_db[chat_id]["stage"] = "waiting_phone"

    send_comic(chat_id, "contacts")
    bot.send_message(chat_id, "📱 Оставь номер телефона (11 цифр):")

@bot.message_handler(content_types=["text"])
def handle_text(msg):
    chat_id = msg.chat.id

    if chat_id not in users_db:
        bot.send_message(chat_id, "Напиши /start")
        return

    stage = users_db[chat_id].get("stage")

    if stage == "hackathon_registration_wait_phone":
        if is_valid_phone(msg.text):
            users_db[chat_id]["phone"] = msg.text
            users_db[chat_id]["stage"] = "hackathon_registration_wait_email"
            bot.send_message(chat_id, "📧 Теперь введи email:")
        else:
            bot.send_message(chat_id, "❌ Некорректный номер. Введи снова:")
        return

    if stage == "hackathon_registration_wait_email":
        if is_valid_email(msg.text):
            users_db[chat_id]["email"] = msg.text

            name = users_db[chat_id].get("name", "Unknown")
            phone = users_db[chat_id].get("phone", "")
            tier = users_db[chat_id].get("hackathon_tier", "-")

            send_lead_to_admin(
                name, phone, msg.text, "hackathon",
                specialty="hackathon",
                level="-",
                extra={"🏆 Лига": tier},
            )

            bot.send_message(
                chat_id,
                "✅ **Ты зарегистрирован на онлайн‑хакатон!**\n"
                "Скоро придёт пакет участника.\n\n" + AI_CHECKLIST_TEXT,
                parse_mode="Markdown",
            )
            users_db[chat_id]["stage"] = "start"
        else:
            bot.send_message(chat_id, "❌ Некорректный email. Введи снова:")
        return

    if stage == "waiting_phone":
        if is_valid_phone(msg.text):
            users_db[chat_id]["phone"] = msg.text
            users_db[chat_id]["stage"] = "waiting_email"
            bot.send_message(chat_id, "📧 Теперь введи email:")
        else:
            bot.send_message(chat_id, "❌ Некорректный номер. Введи снова:")
        return

    if stage == "waiting_email":
        if is_valid_email(msg.text):
            users_db[chat_id]["email"] = msg.text

            name = users_db[chat_id].get("name", "Unknown")
            phone = users_db[chat_id].get("phone", "")
            path = users_db[chat_id].get("path", "")
            specialty = users_db[chat_id].get("specialty")
            level = users_db[chat_id].get("current_level")

            send_lead_to_admin(name, phone, msg.text, path, specialty, level)

            bot.send_message(
                chat_id,
                "✅ **Контакты получены!**\n"
                "Менеджер свяжется и пришлёт материалы.\n\n" + AI_CHECKLIST_TEXT,
                parse_mode="Markdown",
            )
            users_db[chat_id]["stage"] = "start"
        else:
            bot.send_message(chat_id, "❌ Некорректный email. Введи снова:")
        return

    bot.send_message(chat_id, "Чтобы начать — напиши /start")

# ================== LOAD PERSISTED IMAGES ==================
load_images()

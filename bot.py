import os
import re
import json
import random
from datetime import datetime

import telebot
from telebot import types
from flask import Flask, request

# ================== ENV ==================
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://rs-zhurkinigor.amvera.io")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
ADMIN_IDS = os.getenv("ADMIN_IDS", "0")

DATA_DIR = os.getenv("DATA_DIR", "/data")
IMAGES_PATH = os.path.join(DATA_DIR, "images.json")

TEXTS_PATH = os.getenv("TEXTS_PATH", "texts.json")

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

# ================== TEXTS ==================
def load_texts():
    fallback = {
        "buttons": {},
        "messages": {},
        "kson": {},
        "system": {},
        "perplexity": {},
        "checklist": {},
        "comics": {"captions": {}}
    }
    try:
        if os.path.exists(TEXTS_PATH):
            with open(TEXTS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {**fallback, **data}
    except Exception:
        pass
    return fallback

TEXTS = load_texts()

def get_path(dct, path, default=""):
    cur = dct
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur

def t(path, default="", **kwargs):
    s = get_path(TEXTS, path, default)
    if isinstance(s, str) and kwargs:
        try:
            return s.format(**kwargs)
        except Exception:
            return s
    return s if isinstance(s, str) else default

def btn(path, default=""):
    return t(path, default)

def pick_after_done():
    arr = get_path(TEXTS, "messages.after_done_random", [])
    if isinstance(arr, list) and arr:
        return random.choice([x for x in arr if isinstance(x, str)] or [""])
    return ""

# ================== HELPERS: callbacks/UX ==================
def ack(call, remove_keyboard=False):
    # Prevent "loading" spinner and repeated taps.
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    if remove_keyboard:
        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )
        except Exception:
            pass

def safe_send_video_note(chat_id, file_id, fallback_text):
    if file_id:
        try:
            bot.send_video_note(chat_id, file_id)
            return True
        except Exception:
            pass
    if fallback_text:
        bot.send_message(chat_id, fallback_text, parse_mode="Markdown")
    return False

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
    caption = t(f"comics.captions.{key}", "")
    if file_id:
        try:
            bot.send_photo(chat_id, file_id, caption=caption)
            return
        except Exception:
            pass
    if caption:
        bot.send_message(chat_id, caption)

# ================== PROMPTS (left in code) ==================
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

    "level1_video_creator": "Я видео‑креатор. Придумай 10 вирусных идей коротких видео (Reels/TikTok) под мою нишу [укажи нишу]. Для каждой: хук 2 секунды, сценарий 15–30 сек, CTA, и какая эмоция должна быть в кадре.",
    "level2_video_creator": "Я видео‑креатор. Составь контент‑систему на 30 дней: рубрики, частота, форматы, сценарные шаблоны, чек‑лист монтажа и публикации. Укажи, как использовать ИИ (сценарий, субтитры, монтаж, обложки).",
    "level3_video_creator": "Я видео‑креатор/продюсер. Создай стратегию масштабирования: команда, пайплайн, инструменты ИИ, метрики, бюджет, и план на 12 недель для роста. Дай риск‑менеджмент и шаблоны промптов."
}

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

# ================== ADMIN HTTP ==================
@app.get("/ping")
def ping():
    return "ok", 200

@app.post("/setup-webhook")
def setup_webhook():
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
        bot.send_message(chat_id, t("system.setimg_usage", "Команда: /setimg <key>"))
        return

    key = parts[1].strip()
    if key not in IMAGES:
        bot.send_message(chat_id, t("system.unknown_img_key", "Неизвестный key."))
        return

    users_db.setdefault(chat_id, {})
    users_db[chat_id]["stage"] = "waiting_image"
    users_db[chat_id]["waiting_image_key"] = key
    bot.send_message(chat_id, f"Ок. Отправь картинку для ключа: {key}")

@bot.message_handler(commands=["imgkeys"])
def imgkeys_cmd(msg):
    chat_id = msg.chat.id
    keys = "\n".join([f"- {k}" for k in IMAGES.keys()])
    bot.send_message(chat_id, t("system.img_keys_title", "Ключи:\n{keys}", keys=keys))

@bot.message_handler(commands=["imglist"])
def imglist_cmd(msg):
    chat_id = msg.chat.id
    lines = "\n".join([f"{k}: {'OK' if v else 'EMPTY'}" for k, v in IMAGES.items()])
    bot.send_message(chat_id, t("system.img_status_title", "Статус:\n{lines}", lines=lines))

@bot.message_handler(content_types=["photo", "document"])
def receive_image(msg):
    chat_id = msg.chat.id
    if users_db.get(chat_id, {}).get("stage") != "waiting_image":
        return

    key = users_db[chat_id].get("waiting_image_key")
    if not key:
        bot.send_message(chat_id, t("system.img_key_error", "Ошибка key."))
        users_db[chat_id]["stage"] = "start"
        return

    file_id = msg.photo[-1].file_id if msg.content_type == "photo" else msg.document.file_id
    IMAGES[key] = file_id
    save_images()

    users_db[chat_id]["stage"] = "start"
    users_db[chat_id].pop("waiting_image_key", None)
    bot.send_message(chat_id, t("system.img_saved", "✅ Сохранено: {key}", key=key))

# ================== USER FLOWS ==================
@bot.message_handler(commands=["start"])
def start(msg):
    chat_id = msg.chat.id
    users_db[chat_id] = {"stage": "start", "name": msg.from_user.first_name or "User"}

    # Screen: command center (comic = main смысл). No duplicate text blocks.
    send_comic(chat_id, "command_center")

    # Optional videonote; fallback is SHORT and doesn't repeat "choose portal"
    safe_send_video_note(chat_id, KSON_START_VIDEO_NOTE_FILE_ID, t("kson.start_fallback", ""))

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(btn("buttons.portal_video", "🎬 Генератор видео"), callback_data="go_video_bot"))
    markup.add(types.InlineKeyboardButton(btn("buttons.portal_learning", "🎓 Обучение"), callback_data="go_learning"))
    markup.add(types.InlineKeyboardButton(btn("buttons.portal_hackathon", "🏆 Хакатон"), callback_data="go_hackathon"))
    bot.send_message(chat_id, btn("buttons.choose", "Выбирай:"), reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "go_video_bot")
def go_video_bot(call):
    ack(call, remove_keyboard=True)
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    users_db[chat_id]["path"] = "video_bot"

    send_comic(chat_id, "video_generator")
    bot.send_message(chat_id, t("messages.video_bot_opened", ""))

@bot.callback_query_handler(func=lambda c: c.data == "go_learning")
def go_learning(call):
    ack(call, remove_keyboard=True)
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    users_db[chat_id]["stage"] = "start"
    users_db[chat_id]["path"] = "learning"

    send_comic(chat_id, "avatar_choice")

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(btn("buttons.avatar_freelancer", "🎒 Фрилансер"), callback_data="freelancer"))
    markup.add(types.InlineKeyboardButton(btn("buttons.avatar_boss", "💼 Босс"), callback_data="boss"))
    markup.add(types.InlineKeyboardButton(btn("buttons.avatar_artist", "🎭 Артист"), callback_data="artist"))
    bot.send_message(chat_id, t("messages.learning_avatar_title", ""), parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "go_hackathon")
def go_hackathon(call):
    ack(call, remove_keyboard=True)
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    users_db[chat_id]["path"] = "hackathon"
    users_db[chat_id]["stage"] = "hackathon_qualify"

    send_comic(chat_id, "hackathon")
    bot.send_message(chat_id, t("messages.hack_arena_open", ""), parse_mode="Markdown")

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(btn("buttons.hack_tier_spec", "⚡ Спец"), callback_data="hack_tier_spec"))
    markup.add(types.InlineKeyboardButton(btn("buttons.hack_tier_genius", "💥 Гений"), callback_data="hack_tier_genius"))
    markup.add(types.InlineKeyboardButton(btn("buttons.hack_tier_project", "🤖 ИИ‑проект"), callback_data="hack_tier_project"))
    bot.send_message(chat_id, t("messages.hack_your_level", "Твой уровень:"), reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["hack_tier_spec", "hack_tier_genius", "hack_tier_project"])
def hackathon_qualify(call):
    ack(call, remove_keyboard=True)
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    users_db[chat_id]["hackathon_tier"] = call.data.replace("hack_tier_", "")
    users_db[chat_id]["stage"] = "hackathon_registration_wait_phone"

    # One screen = one comic about registration.
    send_comic(chat_id, "hackathon_register")

    # Optional videonote; short fallback only
    safe_send_video_note(chat_id, KSON_HACKATHON_VIDEO_NOTE_FILE_ID, t("kson.hackathon_fallback", ""))

    bot.send_message(chat_id, t("messages.ask_phone", "📱 Телефон:"))

@bot.callback_query_handler(func=lambda c: c.data in ["freelancer", "boss", "artist"])
def path_select(call):
    ack(call, remove_keyboard=True)
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    users_db[chat_id]["path"] = call.data

    if call.data in ["freelancer", "artist"]:
        send_comic(chat_id, "professions_overview")

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(btn("buttons.prof_management", "🧠 Менеджмент"), callback_data="management"))
        markup.add(types.InlineKeyboardButton(btn("buttons.prof_analytics", "📈 Аналитика"), callback_data="analytics"))
        markup.add(types.InlineKeyboardButton(btn("buttons.prof_copywriting", "✍️ Копирайтинг"), callback_data="copywriting"))
        markup.add(types.InlineKeyboardButton(btn("buttons.prof_design", "🎨 Дизайн"), callback_data="design"))
        markup.add(types.InlineKeyboardButton(btn("buttons.prof_marketing", "📊 Маркетинг"), callback_data="marketing"))
        markup.add(types.InlineKeyboardButton(btn("buttons.prof_video_creator", "🎬 Видео‑креатор"), callback_data="video_creator"))
        markup.add(types.InlineKeyboardButton(btn("buttons.prof_other", "✍️ Другое"), callback_data="other_specialty"))

        bot.send_message(chat_id, t("messages.freelancer_professions_title", ""), parse_mode="Markdown", reply_markup=markup)
    else:
        send_comic(chat_id, "levels_3")
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(btn("buttons.level_1", "📚 Уровень 1"), callback_data="level_1_boss"))
        markup.add(types.InlineKeyboardButton(btn("buttons.level_2", "📘 Уровень 2"), callback_data="level_2_boss"))
        markup.add(types.InlineKeyboardButton(btn("buttons.level_3", "📕 Уровень 3"), callback_data="level_3_boss"))
        bot.send_message(chat_id, t("messages.boss_levels_title", ""), parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "other_specialty")
def other_specialty(call):
    ack(call, remove_keyboard=True)
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    users_db[chat_id]["stage"] = "waiting_specialty_text"
    bot.send_message(chat_id, t("messages.other_specialty_ask", ""))

@bot.callback_query_handler(func=lambda c: c.data in ["copywriting", "design", "marketing", "analytics", "management", "video_creator"])
def specialty_select(call):
    ack(call, remove_keyboard=True)
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    users_db[chat_id]["specialty"] = call.data

    prof_key_map = {
        "management": "prof_management",
        "analytics": "prof_analytics",
        "copywriting": "prof_copywriting",
        "design": "prof_design",
        "marketing": "prof_marketing",
        "video_creator": "professions_overview"
    }
    # Keep profession comic (class) AND then levels? -> remove duplicate meaning by not sending levels comic here.
    send_comic(chat_id, prof_key_map.get(call.data, "professions_overview"))

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(btn("buttons.level_1", "📚 Уровень 1"), callback_data=f"level_1_{call.data}"))
    markup.add(types.InlineKeyboardButton(btn("buttons.level_2", "📘 Уровень 2"), callback_data=f"level_2_{call.data}"))
    markup.add(types.InlineKeyboardButton(btn("buttons.level_3", "📕 Уровень 3"), callback_data=f"level_3_{call.data}"))
    bot.send_message(chat_id, t("messages.choose_power_level", ""), parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("level_"))
def level_select(call):
    ack(call, remove_keyboard=True)
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})

    parts = call.data.split("_")
    level = parts[1]
    specialty = "_".join(parts[2:])

    users_db[chat_id]["current_level"] = level
    users_db[chat_id]["stage"] = "waiting_result"

    prompt_key = f"level{level}_{specialty}"
    if prompt_key not in PROMPTS:
        bot.send_message(chat_id, t("messages.level_prompt_missing", ""))
        return

    send_comic(chat_id, "prompt_artifact")

    prompt = PROMPTS[prompt_key]
    if users_db.get(chat_id, {}).get("specialty") == "other":
        ctx = users_db.get(chat_id, {}).get("specialty_text", "")
        if ctx:
            prompt = prompt + f"\n\nКонтекст пользователя: его сфера — {ctx}."

    bot.send_message(chat_id, t("messages.prompt_task_title", "", level=level, prompt=prompt), parse_mode="Markdown")

    # Optional: send videonote; fallback is short
    safe_send_video_note(chat_id, KSON_SUCCESS_VIDEO_NOTE_FILE_ID, t("kson.success_fallback", ""))

    # Combine instructions + done prompt into one message (so fewer blocks)
    text = t("perplexity.help", "")
    done_line = t("messages.perplexity_done_prompt", "")
    if done_line:
        text = (text + "\n\n" + done_line).strip()

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(btn("buttons.done", "✅ Выполнил!"), callback_data="done"))
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

    if level == "3":
        bot.send_message(chat_id, t("messages.hackathon_invite_lvl3", ""), parse_mode="Markdown")
        hk = types.InlineKeyboardMarkup()
        hk.add(types.InlineKeyboardButton(btn("buttons.hackathon_join", "🏆 Хочу на хакатон"), callback_data="go_hackathon"))
        bot.send_message(chat_id, " ", reply_markup=hk)

@bot.callback_query_handler(func=lambda c: c.data == "done")
def done(call):
    ack(call, remove_keyboard=True)
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    users_db[chat_id]["stage"] = "waiting_phone"

    send_comic(chat_id, "contacts")

    rnd = pick_after_done()
    if rnd:
        bot.send_message(chat_id, rnd)

    bot.send_message(chat_id, t("messages.ask_phone", ""))

@bot.message_handler(content_types=["text"])
def handle_text(msg):
    chat_id = msg.chat.id

    if chat_id not in users_db:
        bot.send_message(chat_id, t("messages.unknown_user_start", "Напиши /start"))
        return

    stage = users_db[chat_id].get("stage")

    if stage == "waiting_specialty_text":
        users_db[chat_id]["specialty"] = "other"
        users_db[chat_id]["specialty_text"] = (msg.text or "").strip()
        users_db[chat_id]["stage"] = "waiting_result"

        # Show levels selection for "other": no duplicate levels comic needed if you already want 1 screen.
        send_comic(chat_id, "levels_3")

        markup = types.InlineKeyboardMarkup(row_width=1)
        # Keep same behavior as your original code: it routes to analytics prompts.
        markup.add(types.InlineKeyboardButton(btn("buttons.level_1", "📚 Уровень 1"), callback_data="level_1_analytics"))
        markup.add(types.InlineKeyboardButton(btn("buttons.level_2", "📘 Уровень 2"), callback_data="level_2_analytics"))
        markup.add(types.InlineKeyboardButton(btn("buttons.level_3", "📕 Уровень 3"), callback_data="level_3_analytics"))
        bot.send_message(chat_id, t("messages.choose_power_level", ""), parse_mode="Markdown", reply_markup=markup)
        return

    if stage == "hackathon_registration_wait_phone":
        if is_valid_phone(msg.text):
            users_db[chat_id]["phone"] = msg.text
            users_db[chat_id]["stage"] = "hackathon_registration_wait_email"
            bot.send_message(chat_id, t("messages.ask_email", ""))
        else:
            bot.send_message(chat_id, t("messages.invalid_phone", ""))
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

            checklist = t("checklist.ai_checklist_text", "")
            bot.send_message(chat_id, t("messages.final_hack_registered", "", checklist=checklist), parse_mode="Markdown")

            ann = t("messages.workshop_announce", "")
            if ann:
                mk = types.InlineKeyboardMarkup()
                mk.add(types.InlineKeyboardButton(btn("buttons.workshop_cta_text", "Записаться"), url=t("messages.workshop_cta_url", "https://example.com/workshop")))
                bot.send_message(chat_id, ann, parse_mode="Markdown", reply_markup=mk)

            users_db[chat_id]["stage"] = "start"
        else:
            bot.send_message(chat_id, t("messages.invalid_email", ""))
        return

    if stage == "waiting_phone":
        if is_valid_phone(msg.text):
            users_db[chat_id]["phone"] = msg.text
            users_db[chat_id]["stage"] = "waiting_email"
            bot.send_message(chat_id, t("messages.ask_email", ""))
        else:
            bot.send_message(chat_id, t("messages.invalid_phone", ""))
        return

    if stage == "waiting_email":
        if is_valid_email(msg.text):
            users_db[chat_id]["email"] = msg.text

            name = users_db[chat_id].get("name", "Unknown")
            phone = users_db[chat_id].get("phone", "")
            path = users_db[chat_id].get("path", "")
            specialty = users_db[chat_id].get("specialty")
            level = users_db[chat_id].get("current_level")

            extra = {}
            if specialty == "other":
                extra["🧩 Сфера (other)"] = users_db[chat_id].get("specialty_text", "")

            send_lead_to_admin(name, phone, msg.text, path, specialty, level, extra=extra)

            checklist = t("checklist.ai_checklist_text", "")
            bot.send_message(chat_id, t("messages.final_contacts_received", "", checklist=checklist), parse_mode="Markdown")

            ann = t("messages.workshop_announce", "")
            if ann:
                mk = types.InlineKeyboardMarkup()
                mk.add(types.InlineKeyboardButton(btn("buttons.workshop_cta_text", "Записаться"), url=t("messages.workshop_cta_url", "https://example.com/workshop")))
                bot.send_message(chat_id, ann, parse_mode="Markdown", reply_markup=mk)

            users_db[chat_id]["stage"] = "start"
        else:
            bot.send_message(chat_id, t("messages.invalid_email", ""))
        return

    bot.send_message(chat_id, t("messages.need_start", "Чтобы начать — напиши /start"))

# ================== LOAD PERSISTED IMAGES ==================
load_images()

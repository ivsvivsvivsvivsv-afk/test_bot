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

TEXTS_PATH = os.getenv("TEXTS_PATH", "texts.json")

DATA_DIR = os.getenv("DATA_DIR", "/data")
IMAGES_PATH = os.path.join(DATA_DIR, "images.json")

if not API_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL not set")
if not WEBHOOK_SECRET:
    raise ValueError("WEBHOOK_SECRET not set")

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)
users_db = {}

# ================== TEXTS (JSON) ==================
def load_texts():
    defaults = {
        "start_title": "👾 **СИСТЕМА ОБНАРУЖЕНА.**\n\nВыбери своего аватара:",
        "freelancer_title": "🎒 **НЕЙРО-ФРИЛАНСЕР**\n\nВ какой области ты работаешь?",
        "boss_title": "💼 **НЕЙРО-БОСС**\n\nВыбери уровень исследования:",
        "artist_title": "🎭 **НЕЙРО-АРТИСТ**\n\nВ какой области ты создаёшь контент/искусство?",
        "choose_level_title": "🎯 Отлично! Выбери уровень сложности:",
        "done_button_text": "Когда выполнишь в Perplexity — нажми кнопку:",
        "ask_phone": "Отлично! Твой номер телефона (10–11 цифр):",
        "ask_email": "Спасибо! Твой email:",
        "thanks_final": "✅ **Спасибо!** Менеджер свяжется в течение часа!",
        "hackathon_invite_lvl3": "🏆 **Приглашение на хакатон:**\n\nЕсли выбрал уровень 3 — тебе точно туда. Хочешь получить приглашение?",
        "workshop_announce": "🎓 **Онлайн воркшоп (анонс):**\n\nДата: уточняется\nДлительность: 90 минут\nФормат: Zoom + домашка\nЧто будет:\n- Разбор твоего кейса\n- Промпты: как получать сильные ответы\n- Упаковка результата в продукт\n\nЧтобы попасть — нажми кнопку ниже (заглушка).",
        "workshop_cta_text": "Записаться на воркшоп",
        "workshop_cta_url": "https://example.com/workshop",
        "after_done_random": [
            "Супер. Видно, что ты реально сделал работу. Сейчас я дам пару правок, чтобы стало в 2 раза сильнее.",
            "Отличный результат. Есть несколько мест, которые можно докрутить — и получится очень продающе.",
            "Хорошая база. Сейчас подсвечу, где усилить структуру и конкретику.",
            "Круто. Давай улучшим: 1) чёткость оффера 2) примеры 3) формат выдачи.",
            "Мощно. Но если хочешь уровень PRO — нужно чуть больше цифр и шагов. Подскажу.",
            "Уже неплохо. Вижу потенциал на реальный проект — добавлю рекомендации по упаковке.",
            "Сильно. Осталось сделать это более прикладным: план действий + метрики + примеры.",
            "Класс! Сейчас дам корректировки, чтобы это можно было сразу внедрять.",
            "Отлично. Пара правок — и результат станет на порядок полезнее.",
            "Сделано круто. Сейчас покажу, где усилить «вау‑эффект» и практичность."
        ]
    }
    try:
        with open(TEXTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            defaults.update(data)
    except Exception:
        pass
    return defaults

TEXTS = load_texts()

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

    "level1_video_creator": "Я видео‑креатор. Придумай 10 вирусных идей коротких видео (Reels/TikTok) под мою нишу [укажи нишу]. Для каждой: хук 2 секунды, сценарий 15–30 сек, CTA, и какая эмоция должна быть в кадре.",
    "level2_video_creator": "Я видео‑креатор. Составь контент‑систему на 30 дней: рубрики, частота, форматы, сценарные шаблоны, чек‑лист монтажа и публикации. Укажи, как использовать ИИ (сценарий, субтитры, монтаж, обложки).",
    "level3_video_creator": "Я видео‑креатор/продюсер. Создай стратегию масштабирования в мини‑медиа: команда, пайплайн, инструменты ИИ, метрики, бюджет, и план на 12 недель для роста. Дай риск‑менеджмент и шаблоны промптов."
}

PERPLEXITY_HELP_DEFAULT = (
    "📱 **КАК НАЧАТЬ РАБОТУ С PERPLEXITY:**\n\n"
    "1. Откройте браузер и перейдите на https://www.perplexity.ai\n"
    "2. Зарегистрируйтесь\n"
    "3. Вставьте промпт\n"
    "4. Скопируйте ответ и пришлите сюда\n"
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

# ================== WEBHOOK ==================
def webhook_path():
    return f"/webhook/{WEBHOOK_SECRET}"

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

# ================== UI HELPERS ==================
def avatar_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("🎒 Фрилансер", callback_data="freelancer"))
    markup.add(types.InlineKeyboardButton("💼 Предприниматель", callback_data="boss"))
    markup.add(types.InlineKeyboardButton("🎭 Артист", callback_data="artist"))
    return markup

def professions_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("✍️ Копирайтинг", callback_data="copywriting"))
    markup.add(types.InlineKeyboardButton("🎨 Дизайн", callback_data="design"))
    markup.add(types.InlineKeyboardButton("📊 Маркетинг", callback_data="marketing"))
    markup.add(types.InlineKeyboardButton("📈 Аналитика", callback_data="analytics"))
    markup.add(types.InlineKeyboardButton("🎬 Видео‑креатор", callback_data="video_creator"))
    markup.add(types.InlineKeyboardButton("✍️ Другое", callback_data="other_specialty"))
    return markup

def levels_keyboard(specialty):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("📚 Уровень 1", callback_data=f"level_1_{specialty}"))
    markup.add(types.InlineKeyboardButton("📘 Уровень 2", callback_data=f"level_2_{specialty}"))
    markup.add(types.InlineKeyboardButton("📕 Уровень 3", callback_data=f"level_3_{specialty}"))
    return markup

def hackathon_keyboard():
    mk = types.InlineKeyboardMarkup(row_width=1)
    mk.add(types.InlineKeyboardButton("🏆 Хочу на хакатон", callback_data="go_hackathon"))
    return mk

def workshop_keyboard():
    url = TEXTS.get("workshop_cta_url", "https://example.com/workshop")
    text = TEXTS.get("workshop_cta_text", "Записаться на воркшоп")
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton(text, url=url))
    return mk

# ================== HANDLERS ==================
@bot.message_handler(commands=["start"])
def start(msg):
    chat_id = msg.chat.id
    users_db[chat_id] = {"stage": "start", "name": msg.from_user.first_name or "User"}
    bot.send_message(chat_id, TEXTS["start_title"], parse_mode="Markdown", reply_markup=avatar_keyboard())

@bot.callback_query_handler(func=lambda c: c.data in ["freelancer", "boss", "artist"])
def path_select(call):
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    users_db[chat_id]["path"] = call.data

    if call.data == "boss":
        bot.send_message(chat_id, TEXTS["boss_title"], parse_mode="Markdown", reply_markup=levels_keyboard("boss"))
        return

    title = TEXTS["freelancer_title"] if call.data == "freelancer" else TEXTS["artist_title"]
    bot.send_message(chat_id, title, parse_mode="Markdown", reply_markup=professions_keyboard())

@bot.callback_query_handler(func=lambda c: c.data in ["copywriting", "design", "marketing", "analytics", "video_creator"])
def specialty_select(call):
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    users_db[chat_id]["specialty"] = call.data
    users_db[chat_id]["stage"] = "choosing_level"
    bot.send_message(chat_id, TEXTS["choose_level_title"], parse_mode="Markdown", reply_markup=levels_keyboard(call.data))

@bot.callback_query_handler(func=lambda c: c.data == "other_specialty")
def other_specialty(call):
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    users_db[chat_id]["stage"] = "waiting_specialty_text"
    bot.send_message(chat_id, "Напиши свою сферу одним сообщением (например: SMM, музыка, монтаж, продюсирование):")

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
    prompt = PROMPTS.get(prompt_key)

    # Для "other" будет fallback: используем промпт аналитики и подставим сферу
    if not prompt and specialty == "other":
        prompt = PROMPTS.get(f"level{level}_analytics")
        if prompt:
            specialty_text = users_db[chat_id].get("specialty_text", "")
            if specialty_text:
                prompt = prompt + f"\n\nКонтекст пользователя: его сфера — {specialty_text}."

    if not prompt:
        bot.send_message(chat_id, "⚠️ Для этого уровня пока нет задания. Напиши /start")
        return

    bot.send_message(chat_id, f"🎯 **ЗАДАНИЕ УРОВНЯ {level}:**\n\n{prompt}", parse_mode="Markdown")

    perplexity_help = TEXTS.get("perplexity_help", PERPLEXITY_HELP_DEFAULT)
    bot.send_message(chat_id, perplexity_help, parse_mode="Markdown")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Выполнил!", callback_data="done"))
    bot.send_message(chat_id, TEXTS["done_button_text"], reply_markup=markup)

    if level == "3":
        bot.send_message(chat_id, TEXTS["hackathon_invite_lvl3"], parse_mode="Markdown", reply_markup=hackathon_keyboard())

@bot.callback_query_handler(func=lambda c: c.data == "done")
def done(call):
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})

    variants = TEXTS.get("after_done_random", [])
    if isinstance(variants, list) and variants:
        bot.send_message(chat_id, random.choice(variants))

    users_db[chat_id]["stage"] = "waiting_phone"
    bot.send_message(chat_id, TEXTS["ask_phone"])

@bot.callback_query_handler(func=lambda c: c.data == "go_hackathon")
def go_hackathon(call):
    chat_id = call.message.chat.id
    users_db.setdefault(chat_id, {"stage": "start", "name": call.from_user.first_name or "User"})
    bot.send_message(chat_id, "🏆 Ок! Напиши «ХАКАТОН» одним словом — и менеджер пришлёт условия/регламент.")

@bot.message_handler(content_types=["text"])
def handle_text(msg):
    chat_id = msg.chat.id

    if chat_id not in users_db:
        bot.send_message(chat_id, "Напиши /start")
        return

    stage = users_db[chat_id].get("stage")

    if stage == "waiting_specialty_text":
        users_db[chat_id]["specialty"] = "other"
        users_db[chat_id]["specialty_text"] = (msg.text or "").strip()
        users_db[chat_id]["stage"] = "choosing_level"
        bot.send_message(chat_id, TEXTS["choose_level_title"], parse_mode="Markdown", reply_markup=levels_keyboard("other"))
        return

    if stage == "waiting_phone":
        if is_valid_phone(msg.text):
            users_db[chat_id]["phone"] = msg.text
            users_db[chat_id]["stage"] = "waiting_email"
            bot.send_message(chat_id, TEXTS["ask_email"])
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

            extra = {}
            if specialty == "other":
                extra["🧩 Сфера (other)"] = users_db[chat_id].get("specialty_text", "")

            send_lead_to_admin(name, phone, msg.text, path, specialty, level, extra=extra)

            bot.send_message(chat_id, TEXTS["thanks_final"], parse_mode="Markdown")
            bot.send_message(chat_id, TEXTS["workshop_announce"], parse_mode="Markdown", reply_markup=workshop_keyboard())

            users_db[chat_id]["stage"] = "start"
        else:
            bot.send_message(chat_id, "❌ Некорректный email. Введи снова:")
        return

    # fallback
    bot.send_message(chat_id, "Чтобы начать — напиши /start")

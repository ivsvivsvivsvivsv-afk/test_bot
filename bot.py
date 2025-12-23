import telebot
from telebot import types
import os
import re
from flask import Flask, request
from datetime import datetime

# ===== CONFIG =====
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_IDS = os.getenv('ADMIN_IDS', '0')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://rs-zhurkinigor.amvera.io')

if not API_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL not set")

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)
users_db = {}

# ===== PROMPTS =====
PROMPTS = {
    'level1_boss': "Я стартапер/предприниматель в области [укажите вашу сферу]. Проанализируй моих топ-3 конкурентов в интернете (назови реальные компании): 1) Их сильные стороны, 2) Слабые стороны, 3) Как они используют ИИ для автоматизации. Дай мне конкретные идеи, как я могу обойти их используя нейросети для управления процессами.",
    'level2_boss': "Я владелец компании размером 10-15 человек. Напиши детальный бизнес-кейс: Как ИИ-ассистент может сократить расходы на 40% в первый год? Включи: 1) Точные процессы для автоматизации, 2) Расчет экономии по ролям, 3) ROI и payback period, 4) Внедрение по месяцам, 5) Риски и как их минимизировать, 6) Примеры реальных компаний которые это сделали.",
    'level3_boss': "Я CEO компании. Создай стратегию полной трансформации: Как построить автономную систему, где ИИ-агенты полностью управляют бизнес-процессами без людей? Дай мне: 1) Архитектуру системы (какие ИИ-агенты, как они взаимодействуют), 2) Какие процессы автоматизировать в первую очередь для MAX ROI, 3) Полный roadmap на 12 месяцев, 4) Метрики успеха для каждого этапа, 5) Как переучить команду на роль супервизоров ИИ, 6) Бюджет и точные сроки, 7) Примеры компаний которые масштабировались 10x через ИИ автоматизацию.",
    'level1_copywriting': "Я фрилансер, специализирующийся на копирайтинге. Напиши 3 мега-продающих заголовка для посадочной страницы курса 'Как стать ИИ-супер-фрилансером'. Каждый заголовок должен срабатывать на боль: нехватка клиентов, низкие ставки, конкуренция. Дай мне готовую структуру лендинга с копией.",
    'level2_copywriting': "Я копирайтер. Напиши полный продающий email-последовательность (5 писем) для привлечения клиентов на курс 'Нейро-юнит'. Каждое письмо должно: 1) Вызывать боль, 2) Показывать решение через ИИ, 3) Давать социальное доказательство, 4) Заканчиваться CTA.",
    'level3_copywriting': "Я копирайтер-эксперт. Создай вирусную контент-стратегию для TikTok, которая будет привлекать фрилансеров на курс 'Нейро-юнит'. Дай: 1) 10 идей вирусных видео, 2) Скрипты для каждого, 3) Когда постить, 4) Как измерять результаты, 5) Как превращать лайки в продажи курса.",
    'level1_design': "Я UI/UX дизайнер. Напиши prompt для ChatGPT, чтобы создать макеты 5 вариантов посадочной страницы курса 'Нейро-юнит для дизайнеров'. Промт должен включить: 1) Цветовую схему, 2) Layout, 3) Типографию, 4) CTA элементы.",
    'level2_design': "Я дизайнер. Проанализируй топ-10 самых конвертящих лендингов в интернете (укажи реальные примеры). Для каждого скажи: 1) Почему он продает, 2) Какой психологический принцип использует, 3) Как я могу применить это в своем дизайне, 4) Какие ошибки допускают конкуренты.",
    'level3_design': "Я опытный дизайнер. Создай систему, как автоматизировать весь процесс дизайна посадочных страниц используя ИИ-генераторы (Figma AI, MidJourney, Runwayml). Дай: 1) Полный workflow, 2) Какие инструменты использовать на каждом этапе, 3) Как сохранить индивидуальность, 4) Как масштабировать и продавать дизайн.",
    'level1_marketing': "Я маркетолог. Напиши GTM (go-to-market) стратегию для курса 'Нейро-юнит'. Включи: 1) Целевую аудиторию, 2) Каналы привлечения, 3) Бюджет на каждый канал, 4) Метрики успеха, 5) Как привлечь первых 100 учеников.",
    'level2_marketing': "Я маркетолог. Проанализируй, почему ИИ-курсы продаются хорошо (реальные примеры: Udemy, Skillshare). Скажи: 1) Общие закономерности, 2) Что работает в описании, 3) Какие боли они решают, 4) Как они позиционируют себя, 5) Прайсинг-стратегия.",
    'level3_marketing': "Я маркетолог-эксперт. Напиши полную стратегию вирусного роста для курса 'Нейро-юнит'. Включи: 1) Как сделать его реферальным, 2) Как создать сообщество, 3) Как использовать ИИ для персонализации маркетинга, 4) Как масштабировать на 10k студентов, 5) LTV и CAC.",
    'level1_analytics': "Я аналитик. Дай мне промт-шаблон для создания дашборда в Excel/Google Sheets, который показывает ключевые метрики онлайн-курса: 1) Конверсия, 2) Retention, 3) Средний чек, 4) LTV. Включи формулы и как их понимать.",
    'level2_analytics': "Я аналитик данных. Напиши аналитический отчет: Какие метрики важны для трекинга успеха ИИ-фрилансера? Включи: 1) Метрики заработка, 2) Метрики скорости выполнения задач, 3) Метрики качества, 4) Как их сравнивать с фрилансерами без ИИ.",
    'level3_analytics': "Я senior аналитик. Создай систему аналитики, которая показывает ROI от внедрения ИИ в бизнес. Дай: 1) Какие данные собирать, 2) Как их обрабатывать, 3) Визуализация для топ-менеджмента, 4) Предиктивные модели, 5) Как принимать решения на основе данных."
}

PERPLEXITY_HELP = "📱 **КАК НАЧАТЬ РАБОТУ С PERPLEXITY:**\n\n1. Откройте браузер и перейдите на https://www.perplexity.ai\n2. Нажмите **Sign Up** и создайте аккаунт (email или Google)\n3. После входа вы увидите поле для ввода запросов\n4. **Скопируйте промт ниже и вставьте его в Perplexity**\n5. Нажмите Enter и дождитесь результата\n6. Когда Perplexity выдаст ответ, **скопируйте результат и отправьте мне сюда или скриншот**\n\n⚡ **В день можно делать 3 глубоких исследования бесплатно!**"

# ===== VALIDATION =====
def is_valid_phone(phone):
    digits = re.sub(r'\D', '', phone)
    return len(digits) in [10, 11]

def is_valid_email(email):
    return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email)

def send_lead_to_admin(name, phone, email, path, specialty=None, level=None):
    try:
        admin_ids = [int(id.strip()) for id in ADMIN_IDS.split(',') if id.strip().isdigit()]
        if not admin_ids:
            return False
        
        msg = f"🔥 **НОВЫЙ ЛИД**\n\n👤 Имя: {name}\n📱 Телефон: {phone}\n📧 Email: {email}\n🎯 Тип: {path}\n💼 Специальность: {specialty or '-'}\n📚 Уровень: {level or '-'}\n⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        for admin_id in admin_ids:
            bot.send_message(admin_id, msg, parse_mode='Markdown')
        return True
    except:
        return False

# ===== HANDLERS =====
@bot.message_handler(commands=['start'])
def start(msg):
    chat_id = msg.chat.id
    users_db[chat_id] = {'stage': 'start', 'name': msg.from_user.first_name or 'User'}
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton('🎒 Фрилансер', callback_data='freelancer'))
    markup.add(types.InlineKeyboardButton('💼 Предприниматель', callback_data='boss'))
    
    bot.send_message(chat_id, "👾 **СИСТЕМА ОБНАРУЖЕНА.**\n\nТы пришел из ТикТока. Видел, что творит ИИ в реальном времени?\nЗдесь, за кулисами, мы не просто смотрим. Мы управляем этим.\n\nВыбери своего Аватара:", parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ['freelancer', 'boss'])
def path_select(call):
    chat_id = call.message.chat.id
    users_db[chat_id]['path'] = call.data
    
    if call.data == 'freelancer':
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton('✍️ Копирайтинг', callback_data='copywriting'))
        markup.add(types.InlineKeyboardButton('🎨 Дизайн', callback_data='design'))
        markup.add(types.InlineKeyboardButton('📊 Маркетинг', callback_data='marketing'))
        markup.add(types.InlineKeyboardButton('📈 Аналитика', callback_data='analytics'))
        bot.send_message(chat_id, "🎒 **НЕЙРО-ФРИЛАНСЕР**\n\nВ какой области ты работаешь?", parse_mode='Markdown', reply_markup=markup)
    else:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton('📚 Уровень 1', callback_data='level_1_boss'))
        markup.add(types.InlineKeyboardButton('📘 Уровень 2', callback_data='level_2_boss'))
        markup.add(types.InlineKeyboardButton('📕 Уровень 3', callback_data='level_3_boss'))
        bot.send_message(chat_id, "💼 **НЕЙРО-БОСС**\n\nВыбери уровень исследования:", parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ['copywriting', 'design', 'marketing', 'analytics'])
def specialty_select(call):
    chat_id = call.message.chat.id
    users_db[chat_id]['specialty'] = call.data
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton('📚 Уровень 1', callback_data=f'level_1_{call.data}'))
    markup.add(types.InlineKeyboardButton('📘 Уровень 2', callback_data=f'level_2_{call.data}'))
    markup.add(types.InlineKeyboardButton('📕 Уровень 3', callback_data=f'level_3_{call.data}'))
    
    bot.send_message(chat_id, "🎯 Отлично! Выбери уровень сложности:", parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith('level_'))
def level_select(call):
    chat_id = call.message.chat.id
    parts = call.data.split('_')
    level = parts[1]
    specialty = '_'.join(parts[2:])
    
    users_db[chat_id]['current_level'] = level
    users_db[chat_id]['stage'] = 'waiting_result'
    
    prompt_key = f'level{level}_{specialty}'
    if prompt_key in PROMPTS:
        prompt = PROMPTS[prompt_key]
        bot.send_message(chat_id, f"🎯 **ЗАДАНИЕ УРОВНЯ {level}:**\n\n{prompt}", parse_mode='Markdown')
        bot.send_message(chat_id, PERPLEXITY_HELP, parse_mode='Markdown')
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('✅ Выполнил!', callback_data='done'))
        bot.send_message(chat_id, "Когда выполнишь в Perplexity — нажми кнопку:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == 'done')
def done(call):
    chat_id = call.message.chat.id
    users_db[chat_id]['stage'] = 'waiting_phone'
    bot.send_message(chat_id, "Отлично! Твой номер телефона (11 цифр):")

@bot.message_handler(content_types=['text'])
def handle_text(msg):
    chat_id = msg.chat.id
    
    if chat_id not in users_db:
        bot.send_message(chat_id, "Напиши /start")
        return
    
    stage = users_db[chat_id].get('stage')
    
    if stage == 'waiting_phone':
        if is_valid_phone(msg.text):
            users_db[chat_id]['phone'] = msg.text
            users_db[chat_id]['stage'] = 'waiting_email'
            bot.send_message(chat_id, "Спасибо! Твой email:")
        else:
            bot.send_message(chat_id, "❌ Некорректный номер. Введи снова:")
    
    elif stage == 'waiting_email':
        if is_valid_email(msg.text):
            users_db[chat_id]['email'] = msg.text
            
            name = users_db[chat_id].get('name', 'Unknown')
            phone = users_db[chat_id].get('phone', '')
            email = msg.text
            path = users_db[chat_id].get('path', '')
            specialty = users_db[chat_id].get('specialty')
            level = users_db[chat_id].get('current_level')
            
            send_lead_to_admin(name, phone, email, path, specialty, level)
            
            bot.send_message(chat_id, "✅ **Спасибо!** Менеджер свяжется в течение часа! 🚀", parse_mode='Markdown')
        else:
            bot.send_message(chat_id, "❌ Некорректный email. Введи снова:")

# ===== WEBHOOK =====
@app.route('/webhook', methods=['POST'])
def webhook():
    json_data = request.get_json()
    update = telebot.types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return 'ok', 200

@app.route('/ping', methods=['GET'])
def ping():
    return 'ok', 200

if __name__ == '__main__':
    webhook_path = f"{WEBHOOK_URL}/webhook"
    try:
        bot.set_webhook(url=webhook_path)
        print(f"✅ Webhook установлен: {webhook_path}")
    except Exception as e:
        print(f"⚠️  Ошибка webhook: {e}")   
   port = int(os.getenv('PORT', 8080))  # ← Добавь эту строку
   app.run(host='0.0.0.0', port=port)   # ← Измени на port

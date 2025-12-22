import telebot
from telebot import types
import os
from datetime import datetime
import json

# Получаем токен из переменной окружения (безопасно)
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(API_TOKEN)

# База пользователей (в реальности — Airtable/Database)
users_db = {}

# ===== ТЕКСТОВЫЕ СЦЕНАРИИ (VIBE CODING) =====

MESSAGES = {
    'start': {
        'text': (
            "👾 **СИСТЕМА ОБНАРУЖЕНА.**\n\n"
            "Ты пришел из ТикТока. Видел, что творит ИИ в реальном времени?\n"
            "Здесь, за кулисами, мы не просто смотрим. Мы управляем этим.\n\n"
            "Чтобы выдать тебе правильный доступ, выбери своего Аватара:"
        ),
        'buttons': [
            ('🎒 Хочу профессию / Деньги', 'freelancer'),
            ('💼 У меня бизнес', 'boss'),
            ('💎 Нужна автоматизация под ключ', 'enterprise')
        ]
    },
    
    'freelancer': {
        'text': (
            "🎒 **Идентификация: НЕЙРО-ФРИЛАНСЕР.**\n\n"
            "Твоя цель: Делать контент и получать за это деньги.\n"
            "Враг: Скучная работа и копеечная зарплата.\n\n"
            "Мы покажем, как стать 'Нейро-юнитом' — спецом, который заменяет целый отдел.\n\n"
            "Готов пройти инициацию?"
        ),
        'button': ('🚀 Начать инициацию', 'start_game_freelancer')
    },
    
    'boss': {
        'text': (
            "💼 **Идентификация: НЕЙРО-БОСС.**\n\n"
            "Твоя цель: Сократить расходы и ускорить бизнес.\n"
            "Враг: Раздутый штат и человеческий фактор.\n\n"
            "Мы покажем, как один обученный Нейро-юнит + ИИ заменят тебе 5 сотрудников.\n\n"
            "Готов увидеть технологию?"
        ),
        'button': ('🚀 Начать тест-драйв', 'start_game_boss')
    },
    
    'enterprise': {
        'text': (
            "💎 **Идентификация: ЗАКАЗЧИК.**\n\n"
            "Я вижу, тебе не нужны курсы. Тебе нужно готовое решение под ключ.\n\n"
            "Мы — студия, которая создает такие системы на базе ИИ.\n\n"
            "Оставь свой контакт, и наш ведущий архитектор свяжется с тобой в течение 24 часов."
        )
    },
    
    'game': {
        'text': (
            "🎮 **УРОВЕНЬ 0: ПЕРВОЕ ОРУЖИЕ.**\n\n"
            "Прежде чем дать тебе билет на воркшоп, проверим твою связь с нейросетью.\n\n"
            "Вот секретный промт. Скопируй его и отправь в ChatGPT:\n\n"
            "`Ты — дерзкий маркетолог из будущего. Придумай 5 крутых названий для бренда кроссовок, которые светятся в темноте и стоят 5000 рублей. Они должны звучать дорого и эксклюзивно.`\n\n"
            "После того как ИИ ответит — **пришли мне результат или скриншот** (текстом или картинкой)."
        )
    },
    
    'success': {
        'text': (
            "✅ **ТЕСТ ПРОЙДЕН!**\n\n"
            "Ты доказал, что умеешь использовать инструменты.\n"
            "Теперь мы готовы показать тебе **СИСТЕМУ**.\n\n"
            "🎯 **ВОРКШОП: Как стать Нейро-Юнитом и управлять ИИ-флотом**\n\n"
            "📅 **Среда, 19:00 МСК**\n"
            "🔗 **Платформа:** Yandex.Telemost\n"
            "⏱ **Длительность:** 60 минут\n\n"
            "За это время ты:\n"
            "1️⃣ Узнаешь, почему 90% курсов по ИИ бесполезны\n"
            "2️⃣ Увидишь LIVE-демо (ИИ работает в реальном времени)\n"
            "3️⃣ Попробуешь сам (интерактив)\n"
            "4️⃣ Получишь доступ к методике\n\n"
            "🎟 **Забрать билет:**"
        ),
        'button': ('🎟 ЗАБРАТЬ БИЛЕТ', 'https://telemost.yandex.ru/j/YOUR_TELEMOST_LINK')
    }
}

# ===== ОБРАБОТЧИКИ БОТА =====

@bot.message_handler(commands=['start'])
def handle_start(message):
    """Стартовое сообщение с выбором пути"""
    chat_id = message.chat.id
    users_db[chat_id] = {'stage': 'start', 'timestamp': datetime.now().isoformat()}
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for button_text, callback_data in MESSAGES['start']['buttons']:
        markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
    
    bot.send_message(
        chat_id,
        MESSAGES['start']['text'],
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data in ['freelancer', 'boss', 'enterprise'])
def handle_path_selection(call):
    """Обработка выбора пути (Фрилансер/Босс/Заказчик)"""
    chat_id = call.message.chat.id
    path = call.data
    
    users_db[chat_id]['path'] = path
    users_db[chat_id]['stage'] = path
    
    if path == 'enterprise':
        # Для заказчиков — просим контакт, не гоняем на воркшоп
        msg = bot.send_message(chat_id, MESSAGES['enterprise']['text'], parse_mode='Markdown')
        bot.register_next_step_handler(msg, handle_enterprise_contact)
    else:
        # Для фрилансеров и боссов — игра
        message_data = MESSAGES[path]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            message_data['button'],
            callback_data=message_data['button']
        ))
        
        bot.send_message(chat_id, message_data['text'], parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('start_game_'))
def handle_game_start(call):
    """Начало игры (микро-задание)"""
    chat_id = call.message.chat.id
    users_db[chat_id]['stage'] = 'game'
    
    markup = types.InlineKeyboardMarkup()
    # Просим просто отправить результат текстом или картинкой
    
    bot.send_message(chat_id, MESSAGES['game']['text'], parse_mode='Markdown')

@bot.message_handler(content_types=['text', 'photo', 'document'])
def handle_user_response(message):
    """Обработка ответов пользователя (текст, картинка, файл)"""
    chat_id = message.chat.id
    
    # Если пользователь на этапе игры
    if chat_id in users_db and users_db[chat_id].get('stage') == 'game':
        users_db[chat_id]['game_completed'] = True
        users_db[chat_id]['completion_time'] = datetime.now().isoformat()
        
        # ВАУ-эффект: анализ
        bot.send_message(chat_id, "🔄 **Анализирую нейро-связь**...")
        
        # Успех — выдаем билет
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            MESSAGES['success']['button'],
            url=MESSAGES['success']['button']
        ))
        
        bot.send_message(chat_id, MESSAGES['success']['text'], parse_mode='Markdown', reply_markup=markup)

def handle_enterprise_contact(message):
    """Обработка контакта заказчика"""
    chat_id = message.chat.id
    users_db[chat_id]['contact'] = message.text
    users_db[chat_id]['stage'] = 'enterprise_captured'
    
    response = (
        "✅ **Принято!**\n\n"
        "Спасибо за информацию. Наш ведущий архитектор свяжется с вами в течение 24 часов.\n\n"
        "Пока можете посмотреть наше видео о том, как ИИ экономит бизнесу миллионы: [ссылка]"
    )
    
    bot.send_message(chat_id, response, parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def handle_help(message):
    """Справка по команде"""
    help_text = (
        "🤖 **Команды бота:**\n\n"
        "/start — Начать с нуля\n"
        "/help — Эта справка\n"
        "/status — Твой статус\n"
    )
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def handle_status(message):
    """Статус пользователя"""
    chat_id = message.chat.id
    
    if chat_id not in users_db:
        bot.send_message(chat_id, "❌ Ты еще не начал. Напиши /start")
    else:
        user_info = users_db[chat_id]
        status_text = f"📊 **Твой статус:**\n\nПуть: {user_info.get('path', 'не выбран')}\nЭтап: {user_info.get('stage', 'неизвестно')}"
        bot.send_message(chat_id, status_text, parse_mode='Markdown')

# ===== ГЛАВНЫЙ ЦИКЛ =====

if __name__ == '__main__':
    print("🤖 Бот запущен...")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"❌ Ошибка: {e}")

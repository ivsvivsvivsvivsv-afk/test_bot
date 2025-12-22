import telebot
from telebot import types
import os
from datetime import datetime

# Получаем токен из переменной окружения
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(API_TOKEN)

# База пользователей (в памяти)
users_db = {}

# ===== СЦЕНАРИИ (VIBE CODING) =====

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
            "Мы покажем, как стать 'Нейро-юнитом'.\n\n"
            "Готов пройти инициацию?"
        ),
        'button_text': '🚀 Начать инициацию',
        'button_callback': 'start_game_freelancer'
    },
    
    'boss': {
        'text': (
            "💼 **Идентификация: НЕЙРО-БОСС.**\n\n"
            "Твоя цель: Сократить расходы и ускорить бизнес.\n"
            "Враг: Раздутый штат и человеческий фактор.\n\n"
            "Мы покажем, как один Нейро-юнит + ИИ заменят тебе 5 сотрудников.\n\n"
            "Готов увидеть технологию?"
        ),
        'button_text': '🚀 Начать тест-драйв',
        'button_callback': 'start_game_boss'
    },
    
    'enterprise': {
        'text': (
            "💎 **Идентификация: ЗАКАЗЧИК.**\n\n"
            "Тебе нужно готовое решение под ключ.\n"
            "Мы — студия, которая создает такие системы.\n\n"
            "Оставь свой контакт, архитектор свяжется в течение 24 часов."
        )
    },
    
    'game': {
        'text': (
            "🎮 **УРОВЕНЬ 0: ПЕРВОЕ ОРУЖИЕ.**\n\n"
            "Скопируй этот промт и отправь в ChatGPT:\n\n"
            "`Ты — дерзкий маркетолог. Придумай 5 названий для светящихся кроссовок.`\n\n"
            "Пришли мне результат или скриншот."
        )
    },
    
    'success': {
        'text': (
            "✅ **ТЕСТ ПРОЙДЕН!**\n\n"
            "🎯 **ВОРКШОП: Как стать Нейро-Юнитом**\n\n"
            "📅 **Среда, 19:00 МСК**\n"
            "🔗 **Платформа:** Yandex.Telemost\n"
            "⏱ **Длительность:** 60 минут\n\n"
            "🎟 **Забрать билет:**"
        ),
        'button_text': '🎟 ЗАБРАТЬ БИЛЕТ',
        'button_url': 'https://telemost.yandex.ru/j/YOUR_TELEMOST_LINK'
    }
}

# ===== ОБРАБОТЧИКИ =====

@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    users_db[chat_id] = {'stage': 'start', 'timestamp': datetime.now().isoformat()}
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for button_text, callback_data in MESSAGES['start']['buttons']:
        markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
    
    bot.send_message(chat_id, MESSAGES['start']['text'], parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ['freelancer', 'boss', 'enterprise'])
def handle_path_selection(call):
    chat_id = call.message.chat.id
    path = call.data
    
    users_db[chat_id]['path'] = path
    users_db[chat_id]['stage'] = path
    
    if path == 'enterprise':
        msg = bot.send_message(chat_id, MESSAGES['enterprise']['text'], parse_mode='Markdown')
        bot.register_next_step_handler(msg, handle_enterprise_contact)
    else:
        message_data = MESSAGES[path]
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            message_data['button_text'], 
            callback_data=message_data['button_callback']
        ))
        bot.send_message(chat_id, message_data['text'], parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('start_game_'))
def handle_game_start(call):
    chat_id = call.message.chat.id
    users_db[chat_id]['stage'] = 'game'
    bot.send_message(chat_id, MESSAGES['game']['text'], parse_mode='Markdown')

@bot.message_handler(content_types=['text', 'photo', 'document'])
def handle_user_response(message):
    chat_id = message.chat.id
    
    if chat_id in users_db and users_db[chat_id].get('stage') == 'game':
        users_db[chat_id]['game_completed'] = True
        users_db[chat_id]['completion_time'] = datetime.now().isoformat()
        
        bot.send_message(chat_id, "🔄 **Анализирую нейро-связь**...")
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            MESSAGES['success']['button_text'], 
            url=MESSAGES['success']['button_url']
        ))
        
        bot.send_message(chat_id, MESSAGES['success']['text'], parse_mode='Markdown', reply_markup=markup)

def handle_enterprise_contact(message):
    chat_id = message.chat.id
    users_db[chat_id]['contact'] = message.text
    users_db[chat_id]['stage'] = 'enterprise_captured'
    
    response = "✅ **Принято!**\n\nНаш архитектор свяжется с вами в течение 24 часов."
    bot.send_message(chat_id, response, parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def handle_help(message):
    help_text = "🤖 **Команды:**\n\n/start — Начать\n/help — Справка"
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

# ===== ГЛАВНЫЙ ЦИКЛ =====

if __name__ == '__main__':
    print("🤖 Бот запущен...")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"❌ Ошибка: {e}")

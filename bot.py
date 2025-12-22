import telebot
import os
import sys

print("\n" + "="*70)
print("🔍 ДИАГНОСТИКА БОТА")
print("="*70)

# Шаг 1: Проверь токен
token = os.getenv('TELEGRAM_BOT_TOKEN')
print(f"\n[1] Токен установлен: {bool(token)}")
if token:
    print(f"    Первые 10 символов: {token[:10]}...")
    print(f"    Длина: {len(token)}")
    if ':' not in token:
        print("    ❌ ОШИБКА: В токене нет двоеточия! Это не Telegram токен!")
        sys.exit(1)
else:
    print("    ❌ ОШИБКА: Токен не установлен!")
    sys.exit(1)

# Шаг 2: Инициализируй бота
print(f"\n[2] Инициализация бота...")
try:
    bot = telebot.TeleBot(token)
    print("    ✅ Бот создан успешно")
except Exception as e:
    print(f"    ❌ Ошибка: {e}")
    sys.exit(1)

# Шаг 3: Проверь соединение с API
print(f"\n[3] Проверка соединения с Telegram API...")
try:
    user = bot.get_me()
    print(f"    ✅ Соединение OK")
    print(f"    Имя бота: @{user.username}")
    print(f"    ID: {user.id}")
except Exception as e:
    print(f"    ❌ Ошибка: {e}")
    print(f"    Возможные причины:")
    print(f"       - Неправильный токен")
    print(f"       - Нет интернета")
    print(f"       - Telegram API недоступен")
    sys.exit(1)

print("\n" + "="*70)
print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
print("="*70)
print("\nНапиши /start в Telegram и жди сообщение от бота...")
print("Нажми Ctrl+C чтобы остановить\n")

# Простой обработчик
@bot.message_handler(commands=['start'])
def start(message):
    print(f"\n[BOT] Сообщение от {message.from_user.first_name}: {message.text}")
    bot.send_message(message.chat.id, f"✅ Привет! Бот работает!")

# Запуск
try:
    print("[POLLING] Запуск...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
except KeyboardInterrupt:
    print("\n[STOP] Бот остановлен")
except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()

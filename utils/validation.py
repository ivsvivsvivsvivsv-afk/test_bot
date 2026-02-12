"""
Модуль валидации данных
=======================
Валидация телефонов (РФ, Беларусь) и email.
"""

import re
import logging

logger = logging.getLogger(__name__)


def validate_phone(phone: str) -> tuple[bool, str]:
    """
    Валидация и нормализация номера телефона.
    
    Поддерживаемые форматы:
    - Россия: +7, 8, 7 (мобильные и городские)
    - Беларусь: +375 (операторы 29, 25, 33, 44, 17)
    
    Args:
        phone: Номер телефона в любом формате
        
    Returns:
        (успех, нормализованный_номер или сообщение_об_ошибке)
        
    Examples:
        >>> validate_phone("+79161234567")
        (True, "+79161234567")
        >>> validate_phone("89161234567")
        (True, "+79161234567")
        >>> validate_phone("+375291234567")
        (True, "+375291234567")
        >>> validate_phone("123")
        (False, "invalid")
    """
    if not phone:
        logger.debug("Телефон пустой")
        return False, "invalid"
    
    # Очищаем от всех символов кроме цифр и +
    phone_clean = phone.strip()
    
    # Убираем все кроме цифр для анализа
    digits = re.sub(r"\D", "", phone_clean)
    
    if not digits:
        logger.debug(f"Нет цифр в телефоне: {phone}")
        return False, "invalid"
    
    logger.debug(f"Валидация телефона: '{phone}' -> digits='{digits}' (len={len(digits)})")
    
    # === БЕЛАРУСЬ (+375) ===
    # Формат: +375 XX YYY YY YY (12 цифр с кодом страны)
    # Операторы: 29, 25, 33, 44, 17
    if digits.startswith("375"):
        if len(digits) == 12:
            operator = digits[3:5]
            valid_operators = ["17", "25", "29", "33", "44"]
            if operator in valid_operators:
                result = f"+{digits}"
                logger.info(f"✅ Валидный телефон (Беларусь): {result}")
                return True, result
            else:
                logger.debug(f"Неизвестный оператор Беларуси: {operator}")
                return False, "invalid"
        else:
            logger.debug(f"Неверная длина для Беларуси: {len(digits)}")
            return False, "invalid"
    
    # === РОССИЯ (+7 / 8) ===
    # Форматы:
    # - 11 цифр: 79161234567 или 89161234567
    # - 10 цифр: 9161234567 (без кода страны)
    
    # Если начинается с 8 и 11 цифр - заменяем 8 на 7
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
        
    # Если 10 цифр - добавляем 7 в начало
    if len(digits) == 10:
        digits = "7" + digits
        
    # Если начинается с 7 и 11 цифр - это Россия
    if len(digits) == 11 and digits[0] == "7":
        # Проверяем, что после 7 идёт корректный код оператора (9XX для мобильных)
        # Но также допускаем городские номера
        result = f"+{digits}"
        logger.info(f"✅ Валидный телефон (Россия): {result}")
        return True, result
    
    # Если ничего не подошло
    logger.debug(f"Телефон не прошёл валидацию: {phone} -> {digits}")
    return False, "invalid"


def validate_email(email: str) -> tuple[bool, str]:
    """
    Валидация email адреса.
    
    Args:
        email: Email адрес
        
    Returns:
        (успех, нормализованный_email или сообщение_об_ошибке)
        
    Examples:
        >>> validate_email("Test@Gmail.COM")
        (True, "test@gmail.com")
        >>> validate_email("invalid")
        (False, "invalid")
    """
    if not email:
        logger.debug("Email пустой")
        return False, "invalid"
    
    # Нормализуем
    email = email.strip().lower()
    
    # Базовая проверка формата
    # Должен содержать @ и хотя бы одну точку после @
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    
    if not re.match(pattern, email):
        logger.debug(f"Email не прошёл regex: {email}")
        return False, "invalid"
    
    # Дополнительные проверки
    local_part, domain = email.rsplit("@", 1)
    
    # Локальная часть не должна быть пустой
    if not local_part:
        return False, "invalid"
        
    # Домен должен содержать точку
    if "." not in domain:
        return False, "invalid"
        
    # Домен не должен начинаться или заканчиваться точкой
    if domain.startswith(".") or domain.endswith("."):
        return False, "invalid"
    
    logger.info(f"✅ Валидный email: {email}")
    return True, email


# =============================================================================
# ТЕСТЫ (для отладки)
# =============================================================================

if __name__ == "__main__":
    # Тесты телефонов
    test_phones = [
        "+79161234567",      # Россия с +7
        "89161234567",       # Россия с 8
        "9161234567",        # Россия без кода
        "+7 916 123 45 67",  # Россия с пробелами
        "+375291234567",     # Беларусь +375 29
        "+375251234567",     # Беларусь +375 25
        "+375331234567",     # Беларусь +375 33
        "+375441234567",     # Беларусь +375 44
        "+375171234567",     # Беларусь +375 17 (городской)
        "375291234567",      # Беларусь без +
        "123",               # Невалидный
        "",                  # Пустой
    ]
    
    print("=" * 50)
    print("ТЕСТЫ ТЕЛЕФОНОВ")
    print("=" * 50)
    for phone in test_phones:
        ok, result = validate_phone(phone)
        status = "✅" if ok else "❌"
        print(f"{status} '{phone}' -> {result}")
    
    # Тесты email
    test_emails = [
        "test@gmail.com",
        "Test@GMAIL.COM",
        "user.name+tag@example.co.uk",
        "invalid",
        "@invalid.com",
        "invalid@",
        "",
    ]
    
    print("\n" + "=" * 50)
    print("ТЕСТЫ EMAIL")
    print("=" * 50)
    for email in test_emails:
        ok, result = validate_email(email)
        status = "✅" if ok else "❌"
        print(f"{status} '{email}' -> {result}")

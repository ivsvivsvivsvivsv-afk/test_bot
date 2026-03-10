"""
Модуль валидации данных
=======================
Валидация телефонов (РФ, Беларусь) и email.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    is_valid: bool
    normalized_value: Optional[str] = None
    error: Optional[str] = None


def validate_phone(phone: str) -> ValidationResult:
    """
    Валидация и нормализация номера телефона.
    
    Поддерживаемые форматы:
    - Россия: +7, 8, 7 (мобильные и городские)
    - Беларусь: +375 (операторы 29, 25, 33, 44, 17)
    
    Args:
        phone: Номер телефона в любом формате
        
    Returns:
        ValidationResult with is_valid, normalized_value or error.
        
    Examples:
        >>> validate_phone("+79161234567").is_valid
        True
        >>> validate_phone("89161234567").normalized_value
        '+79161234567'
        >>> validate_phone("123").is_valid
        False
    """
    _err = ValidationResult(is_valid=False, error="Неверный формат телефона. Введите номер в формате +7XXXXXXXXXX или +375XXXXXXXXX.")

    if not phone:
        return _err

    phone_clean = phone.strip()
    digits = re.sub(r"\D", "", phone_clean)

    if not digits:
        return _err

    logger.debug("Валидация телефона: '%s' -> digits='%s' (len=%d)", phone, digits, len(digits))

    # === БЕЛАРУСЬ (+375) ===
    if digits.startswith("375"):
        if len(digits) == 12:
            operator = digits[3:5]
            if operator in ("17", "25", "29", "33", "44"):
                normalized = f"+{digits}"
                logger.info("Валидный телефон (Беларусь): %s", normalized)
                return ValidationResult(is_valid=True, normalized_value=normalized)
        return _err

    # === РОССИЯ (+7 / 8) ===
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits

    if len(digits) == 11 and digits[0] == "7":
        normalized = f"+{digits}"
        logger.info("Валидный телефон (Россия): %s", normalized)
        return ValidationResult(is_valid=True, normalized_value=normalized)

    return _err


def validate_email(email: str) -> ValidationResult:
    """
    Валидация email адреса.

    Returns:
        ValidationResult with is_valid, normalized_value or error.
    """
    _err = ValidationResult(is_valid=False, error="Неверный формат email. Пример: ivan@mail.ru")

    if not email:
        return _err

    email = email.strip().lower()

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        return _err

    local_part, domain = email.rsplit("@", 1)
    if not local_part or "." not in domain:
        return _err
    if domain.startswith(".") or domain.endswith("."):
        return _err

    logger.info("Валидный email: %s", email)
    return ValidationResult(is_valid=True, normalized_value=email)


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
        r = validate_phone(phone)
        status = "✅" if r.is_valid else "❌"
        print(f"{status} '{phone}' -> {r.normalized_value or r.error}")
    
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
        r = validate_email(email)
        status = "✅" if r.is_valid else "❌"
        print(f"{status} '{email}' -> {r.normalized_value or r.error}")

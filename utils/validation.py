import re


def validate_phone(phone: str):
    if not phone:
        return False, "invalid"

    digits = re.sub(r"\D", "", phone)

    # допускаем 10-11 цифр (RU/международные варианты)
    if len(digits) < 10 or len(digits) > 11:
        return False, "invalid"

    # нормализуем под +7XXXXXXXXXX, если похоже на РФ
    if len(digits) == 10:
        digits = "7" + digits
    elif len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]

    return True, f"+{digits}"


def validate_email(email: str):
    if not email:
        return False, "invalid"

    email = email.strip().lower()
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        return False, "invalid"

    return True, email


import re


_BY_OPERATORS = {"25", "29", "33", "44"}


def validate_phone(phone: str):
    """Validate and normalize phone number.

    Supported:
      - Belarus: +375 (25|29|33|44) XXXXXXX  -> +375XXXXXXXXX (12 digits with 375 prefix)
      - Russia (mobile): +7 9XXXXXXXXX / 79XXXXXXXXX / 89XXXXXXXXX / 9XXXXXXXXX -> +79XXXXXXXXX

    Returns:
      (True, normalized_phone) or (False, "invalid")
    """
    if not phone:
        return False, "invalid"

    digits = re.sub(r"\D", "", phone)
    if not digits:
        return False, "invalid"

    # Belarus: 375 + operator(2) + number(7) => 12 digits total
    if digits.startswith("375") and len(digits) == 12:
        op = digits[3:5]
        if op in _BY_OPERATORS:
            return True, f"+{digits}"
        return False, "invalid"

    # Russia: normalize to 11 digits starting with 7
    # 8XXXXXXXXXX -> 7XXXXXXXXXX
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]

    # 9XXXXXXXXX -> 79XXXXXXXXX
    if len(digits) == 10 and digits.startswith("9"):
        digits = "7" + digits

    # 79XXXXXXXXX / +7 9XXXXXXXXX
    if len(digits) == 11 and digits.startswith("7"):
        # RU mobile numbers typically start with 79...
        if digits[1] != "9":
            return False, "invalid"
        return True, f"+{digits}"

    return False, "invalid"


def validate_email(email: str):
    if not email:
        return False, "invalid"

    email = email.strip().lower()
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        return False, "invalid"

    return True, email

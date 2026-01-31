import re


BY_MOBILE_CODES = {"25", "29", "33", "44"}


def _digits(value: str) -> str:
    return re.sub(r"\D", "", (value or "").strip())


def validate_phone(phone: str):
    """Validate Belarus (+375...) and Russia (+7..., 8..., 79..., 9...) mobile phones.

    Returns:
        (True, normalized)  where normalized is in E.164 format: +375XXXXXXXXX or +7XXXXXXXXXX
        (False, "invalid")  on error (caller shows user-friendly message).
    """

    digits = _digits(phone)
    if not digits:
        return False, "invalid"

    # -----------------------
    # Belarus: +375 (25/29/33/44) + 7 digits
    # Examples: +375291234567, +375-29-123-45-67
    # -----------------------
    if digits.startswith("375"):
        # 375 + (2 digits code) + (7 digits)
        if len(digits) == 12:
            code = digits[3:5]
            rest = digits[5:]
            if code in BY_MOBILE_CODES and len(rest) == 7:
                return True, f"+{digits}"
        return False, "invalid"

    # -----------------------
    # Russia: +7 9XX XXXXXXX
    # Allow:
    #  - +7XXXXXXXXXX (11 digits starting 7)
    #  - 8XXXXXXXXXX  -> normalize to +7
    #  - 79XXXXXXXXX  (already)
    #  - 9XXXXXXXXX   (10 digits) -> +7
    # -----------------------
    ru = digits

    if len(ru) == 11 and ru.startswith("8"):
        ru = "7" + ru[1:]

    if len(ru) == 10 and ru.startswith("9"):
        ru = "7" + ru

    if len(ru) == 11 and ru.startswith("7") and ru[1] == "9":
        return True, f"+{ru}"

    return False, "invalid"


def validate_email(email: str):
    if not email:
        return False, "invalid"

    email = email.strip().lower()
    # стандартная (достаточно строгая) regex-валидация
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        return False, "invalid"

    return True, email

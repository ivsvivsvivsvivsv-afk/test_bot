import re

# Allowed BY operators after +375
_BY_OPERATORS = {"25", "29", "33", "44"}

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def validate_phone(phone: str):
    """Validate and normalize phone number.

    Returns: (ok: bool, normalized: str|"invalid")

    Supported:
    - Belarus: +375 (25|29|33|44) XXXXXXX  -> +375XXXXXXXXX
    - Russia:  +7 9XXXXXXXXX -> +79XXXXXXXXX
      Also accept: 79XXXXXXXXX, 89XXXXXXXXX, 9XXXXXXXXX
    """
    if not phone:
        return False, "invalid"

    raw = (phone or "").strip()
    digits = re.sub(r"\D", "", raw)

    # Belarus: must contain country code 375 and be 12 digits total: 375 + 9 digits
    if digits.startswith("375") and len(digits) == 12:
        op = digits[3:5]
        if op in _BY_OPERATORS:
            return True, f"+{digits}"
        return False, "invalid"

    # Russia mobile: normalize to +79XXXXXXXXX
    # Accept 11 digits: 7xxxxxxxxxx or 8xxxxxxxxxx or 79xxxxxxxxx
    if len(digits) == 11:
        if digits[0] == "8":
            digits = "7" + digits[1:]
        # now must be 7 + 10 digits
        if digits[0] == "7" and digits[1] == "9":
            return True, f"+{digits}"
        return False, "invalid"

    # Accept 10 digits starting with 9XXXXXXXXX (RU mobile without country code)
    if len(digits) == 10 and digits[0] == "9":
        digits = "7" + digits
        return True, f"+{digits}"

    return False, "invalid"


def validate_email(email: str):
    """Standard email regex validation. Returns (ok, normalized_or_invalid)."""
    if not email:
        return False, "invalid"

    email = (email or "").strip().lower()
    if not _EMAIL_RE.match(email):
        return False, "invalid"

    return True, email

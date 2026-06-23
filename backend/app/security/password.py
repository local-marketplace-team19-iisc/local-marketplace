import re

import bcrypt

PASSWORD_MIN_LENGTH = 8
PASSWORD_PATTERN = r"^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]+$"


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against bcrypt hash."""
    if not hashed_password:
        return False
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password meets strength requirements.

    Returns (is_valid, message).
    Requirements: min 8 chars, at least 1 uppercase, 1 digit, 1 special char.
    """
    if not password:
        return False, "Password is required"

    if len(password) < PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"

    if not re.search(PASSWORD_PATTERN, password):
        return False, (
            "Password must contain at least one uppercase letter, "
            "one digit, and one special character (@$!%*?&)"
        )

    return True, "Password meets strength requirements"

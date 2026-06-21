from datetime import datetime, timedelta

from backend.app.core.config import settings

# In-memory rate limiting state
# Format: {key: [(timestamp, count), ...]}
_rate_limit_store: dict[str, list[tuple[datetime, int]]] = {}


def _cleanup_expired(key: str, window_duration: timedelta) -> None:
    """Remove expired entries from rate limit store."""
    if key not in _rate_limit_store:
        return

    now = datetime.utcnow()
    cutoff = now - window_duration
    _rate_limit_store[key] = [
        (timestamp, count) for timestamp, count in _rate_limit_store[key]
        if timestamp > cutoff
    ]

    if not _rate_limit_store[key]:
        del _rate_limit_store[key]


def check_login_rate_limit(email: str) -> tuple[bool, str]:
    """Check if login attempt is allowed for email.

    Allows up to RATE_LIMIT_FAILED_LOGIN_ATTEMPTS failed attempts
    within RATE_LIMIT_LOCKOUT_MINUTES window.

    Args:
        email: User email

    Returns:
        (allowed: bool, reason: str)
    """
    key = f"login:{email}"
    window = timedelta(minutes=settings.RATE_LIMIT_LOCKOUT_MINUTES)
    max_attempts = settings.RATE_LIMIT_FAILED_LOGIN_ATTEMPTS

    _cleanup_expired(key, window)

    if key in _rate_limit_store:
        attempt_count = sum(count for _, count in _rate_limit_store[key])
        if attempt_count >= max_attempts:
            return False, f"Too many failed login attempts. Try again in {settings.RATE_LIMIT_LOCKOUT_MINUTES} minutes."

    return True, ""


def record_failed_login(email: str) -> None:
    """Record a failed login attempt for email."""
    key = f"login:{email}"

    if key not in _rate_limit_store:
        _rate_limit_store[key] = []

    _rate_limit_store[key].append((datetime.utcnow(), 1))


def clear_failed_login(email: str) -> None:
    """Clear failed login attempts for email (on successful login)."""
    key = f"login:{email}"
    if key in _rate_limit_store:
        del _rate_limit_store[key]


def check_signup_rate_limit(ip: str) -> tuple[bool, str]:
    """Check if signup attempt is allowed from IP.

    Allows up to RATE_LIMIT_SIGNUP_PER_IP_HOUR signups
    per IP address per hour.

    Args:
        ip: Client IP address

    Returns:
        (allowed: bool, reason: str)
    """
    key = f"signup:{ip}"
    window = timedelta(hours=1)
    max_signups = settings.RATE_LIMIT_SIGNUP_PER_IP_HOUR

    _cleanup_expired(key, window)

    if key in _rate_limit_store:
        signup_count = sum(count for _, count in _rate_limit_store[key])
        if signup_count >= max_signups:
            return False, f"Too many signup attempts from this IP. Try again later."

    return True, ""


def record_signup(ip: str) -> None:
    """Record a signup attempt from IP."""
    key = f"signup:{ip}"

    if key not in _rate_limit_store:
        _rate_limit_store[key] = []

    _rate_limit_store[key].append((datetime.utcnow(), 1))


def reset_rate_limit_store() -> None:
    """Clear all rate limit state. Useful for testing."""
    _rate_limit_store.clear()

import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.app.models.otp import Otp

OTP_LENGTH = 6
OTP_VALIDITY = timedelta(minutes=10)
MAX_FAILED_ATTEMPTS = 3
LOCKOUT_DURATION = timedelta(minutes=5)


class OtpError(Exception):
    """Base error for OTP verification failures."""


class OtpExpiredError(OtpError):
    pass


class OtpLockedError(OtpError):
    pass


class OtpInvalidError(OtpError):
    pass


class OtpAlreadyUsedError(OtpError):
    pass


def generate_code() -> str:
    """6-digit OTP code, zero-padded (FR-2)."""
    return f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"


def create_otp(db: Session, user_id: uuid.UUID, *, now: datetime | None = None) -> Otp:
    now = now or datetime.utcnow()
    otp = Otp(
        user_id=user_id,
        code=generate_code(),
        expires_at=now + OTP_VALIDITY,
    )
    db.add(otp)
    db.commit()
    db.refresh(otp)
    return otp


def is_expired(otp: Otp, *, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    return now > otp.expires_at


def is_locked(otp: Otp, *, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    return otp.locked_until is not None and now < otp.locked_until


def verify_otp(db: Session, otp: Otp, code: str, *, now: datetime | None = None) -> Otp:
    """Verify `code` against `otp`, mutating + persisting attempt/lockout state.

    Raises OtpAlreadyUsedError / OtpLockedError / OtpExpiredError / OtpInvalidError
    on failure; returns the (now `used=True`) otp on success.
    """
    now = now or datetime.utcnow()

    if otp.used:
        raise OtpAlreadyUsedError("OTP already used")
    if is_locked(otp, now=now):
        raise OtpLockedError("Too many failed attempts; OTP locked")
    if is_expired(otp, now=now):
        raise OtpExpiredError("OTP expired")

    if otp.code != code:
        otp.attempts += 1
        if otp.attempts >= MAX_FAILED_ATTEMPTS:
            otp.locked_until = now + LOCKOUT_DURATION
        db.commit()
        raise OtpInvalidError("Incorrect OTP code")

    otp.used = True
    db.commit()
    return otp

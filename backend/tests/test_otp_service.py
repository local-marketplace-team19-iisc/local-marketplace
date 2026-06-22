import uuid
from datetime import datetime, timedelta

import pytest

from backend.app.models.otp import Otp
from backend.app.services import otp_service


class FakeSession:
    """Stand-in for a SQLAlchemy Session: no real DB needed for these unit tests."""

    def add(self, instance):
        pass

    def commit(self):
        pass

    def refresh(self, instance):
        pass


def make_otp(*, code="123456", now=None, **overrides) -> Otp:
    now = now or datetime.utcnow()
    defaults = dict(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        code=code,
        expires_at=now + otp_service.OTP_VALIDITY,
        used=False,
        attempts=0,
        locked_until=None,
        created_at=now,
    )
    defaults.update(overrides)
    return Otp(**defaults)


def test_generate_code_is_six_digits():
    code = otp_service.generate_code()
    assert len(code) == 6
    assert code.isdigit()


def test_happy_path_verifies_and_marks_used():
    db = FakeSession()
    now = datetime.utcnow()
    otp = make_otp(code="654321", now=now)

    result = otp_service.verify_otp(db, otp, "654321", now=now)

    assert result.used is True
    assert result.attempts == 0


def test_expired_otp_raises():
    db = FakeSession()
    now = datetime.utcnow()
    otp = make_otp(code="111111", now=now - otp_service.OTP_VALIDITY - timedelta(minutes=1))

    with pytest.raises(otp_service.OtpExpiredError):
        otp_service.verify_otp(db, otp, "111111", now=now)


def test_wrong_code_increments_attempts():
    db = FakeSession()
    now = datetime.utcnow()
    otp = make_otp(code="111111", now=now)

    with pytest.raises(otp_service.OtpInvalidError):
        otp_service.verify_otp(db, otp, "000000", now=now)

    assert otp.attempts == 1
    assert otp.locked_until is None


def test_third_failed_attempt_triggers_lockout():
    db = FakeSession()
    now = datetime.utcnow()
    otp = make_otp(code="111111", now=now)

    for _ in range(otp_service.MAX_FAILED_ATTEMPTS):
        with pytest.raises(otp_service.OtpInvalidError):
            otp_service.verify_otp(db, otp, "000000", now=now)

    assert otp.attempts == otp_service.MAX_FAILED_ATTEMPTS
    assert otp.locked_until == now + otp_service.LOCKOUT_DURATION


def test_locked_otp_rejects_even_correct_code():
    db = FakeSession()
    now = datetime.utcnow()
    otp = make_otp(code="111111", now=now, attempts=3, locked_until=now + timedelta(minutes=5))

    with pytest.raises(otp_service.OtpLockedError):
        otp_service.verify_otp(db, otp, "111111", now=now)


def test_lockout_expires_after_duration():
    db = FakeSession()
    now = datetime.utcnow()
    locked_until = now - timedelta(seconds=1)  # lockout window already passed
    otp = make_otp(code="111111", now=now, attempts=3, locked_until=locked_until)

    result = otp_service.verify_otp(db, otp, "111111", now=now)

    assert result.used is True


def test_already_used_otp_rejected():
    db = FakeSession()
    now = datetime.utcnow()
    otp = make_otp(code="111111", now=now, used=True)

    with pytest.raises(otp_service.OtpAlreadyUsedError):
        otp_service.verify_otp(db, otp, "111111", now=now)

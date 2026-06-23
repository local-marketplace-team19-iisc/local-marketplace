import pytest

from backend.app.services.rate_limit import (
    check_login_rate_limit,
    check_signup_rate_limit,
    clear_failed_login,
    record_failed_login,
    record_signup,
    reset_rate_limit_store,
)


class TestLoginRateLimit:
    """Tests for login attempt rate limiting."""

    def setup_method(self):
        """Reset rate limit store before each test."""
        reset_rate_limit_store()

    def test_first_login_attempt_allowed(self):
        allowed, reason = check_login_rate_limit("user@example.com")

        assert allowed is True
        assert reason == ""

    def test_login_allowed_up_to_max_attempts(self):
        email = "user@example.com"

        # Record failed attempts up to max (but check BEFORE hitting max)
        for i in range(4):  # Check at 1-4 attempts (all should be allowed)
            record_failed_login(email)
            allowed, _ = check_login_rate_limit(email)
            assert allowed is True

    def test_login_blocked_after_max_attempts_exceeded(self):
        email = "user@example.com"

        # Record max + 1 failed attempts
        for _ in range(6):  # 1 more than max
            record_failed_login(email)

        allowed, reason = check_login_rate_limit(email)

        assert allowed is False
        assert "Too many failed login attempts" in reason

    def test_clear_failed_login_resets_counter(self):
        email = "user@example.com"

        # Record max attempts
        for _ in range(5):
            record_failed_login(email)

        # Clear counter
        clear_failed_login(email)

        # Now another attempt should be allowed
        allowed, _ = check_login_rate_limit(email)
        assert allowed is True

    def test_different_emails_have_separate_limits(self):
        email1 = "user1@example.com"
        email2 = "user2@example.com"

        # Record many failed attempts for email1
        for _ in range(10):
            record_failed_login(email1)

        # email1 should be blocked
        allowed1, _ = check_login_rate_limit(email1)
        assert allowed1 is False

        # email2 should still be allowed
        allowed2, _ = check_login_rate_limit(email2)
        assert allowed2 is True


class TestSignupRateLimit:
    """Tests for signup attempt rate limiting."""

    def setup_method(self):
        """Reset rate limit store before each test."""
        reset_rate_limit_store()

    def test_first_signup_from_ip_allowed(self):
        allowed, reason = check_signup_rate_limit("192.168.1.1")

        assert allowed is True
        assert reason == ""

    def test_signup_allowed_up_to_max_per_hour(self):
        ip = "192.168.1.1"

        # Record signups up to max (but check BEFORE hitting max)
        for _ in range(9):  # Check at 1-9 attempts (all should be allowed)
            record_signup(ip)
            allowed, _ = check_signup_rate_limit(ip)
            assert allowed is True

    def test_signup_blocked_after_max_per_hour_exceeded(self):
        ip = "192.168.1.1"

        # Record max + 1 signups
        for _ in range(11):  # 1 more than max
            record_signup(ip)

        allowed, reason = check_signup_rate_limit(ip)

        assert allowed is False
        assert "Too many signup attempts" in reason

    def test_different_ips_have_separate_limits(self):
        ip1 = "192.168.1.1"
        ip2 = "192.168.1.2"

        # Record many signups from ip1
        for _ in range(15):
            record_signup(ip1)

        # ip1 should be blocked
        allowed1, _ = check_signup_rate_limit(ip1)
        assert allowed1 is False

        # ip2 should still be allowed
        allowed2, _ = check_signup_rate_limit(ip2)
        assert allowed2 is True

    def test_reset_clears_all_rate_limits(self):
        email = "user@example.com"
        ip = "192.168.1.1"

        # Record attempts for both
        for _ in range(10):
            record_failed_login(email)
            record_signup(ip)

        # Both should be blocked
        allowed_login, _ = check_login_rate_limit(email)
        allowed_signup, _ = check_signup_rate_limit(ip)
        assert allowed_login is False
        assert allowed_signup is False

        # Reset
        reset_rate_limit_store()

        # Both should now be allowed
        allowed_login, _ = check_login_rate_limit(email)
        allowed_signup, _ = check_signup_rate_limit(ip)
        assert allowed_login is True
        assert allowed_signup is True

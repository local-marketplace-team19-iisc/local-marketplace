
from backend.app.security.password import hash_password, validate_password_strength, verify_password


class TestPasswordHashing:
    """Tests for password hashing and verification."""

    def test_hash_password_returns_different_hash_each_time(self):
        password = "SecurePass123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2  # bcrypt includes salt, so hashes differ
        assert len(hash1) > 20
        assert len(hash2) > 20

    def test_verify_password_accepts_correct_password(self):
        password = "SecurePass123!"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_rejects_incorrect_password(self):
        password = "SecurePass123!"
        wrong_password = "WrongPass123!"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_rejects_empty_string(self):
        hashed = hash_password("SecurePass123!")

        assert verify_password("", hashed) is False


class TestPasswordValidation:
    """Tests for password strength validation."""

    def test_valid_password_passes(self):
        password = "SecurePass123!"
        is_valid, message = validate_password_strength(password)

        assert is_valid is True
        assert "meets strength requirements" in message.lower()

    def test_empty_password_fails(self):
        is_valid, message = validate_password_strength("")

        assert is_valid is False
        assert "required" in message.lower()

    def test_password_too_short_fails(self):
        password = "Short1!"
        is_valid, message = validate_password_strength(password)

        assert is_valid is False
        assert "8 characters" in message

    def test_password_without_uppercase_fails(self):
        password = "securepass123!"
        is_valid, message = validate_password_strength(password)

        assert is_valid is False
        assert "uppercase" in message.lower()

    def test_password_without_digit_fails(self):
        password = "SecurePass!"
        is_valid, message = validate_password_strength(password)

        assert is_valid is False
        assert "digit" in message.lower()

    def test_password_without_special_char_fails(self):
        password = "SecurePass123"
        is_valid, message = validate_password_strength(password)

        assert is_valid is False
        assert "special character" in message.lower()

    def test_password_with_all_requirements_passes(self):
        valid_passwords = [
            "SecurePass123!",
            "MyPassword123@",
            "Test1234$abc",
            "Complex%Pass123",
        ]

        for password in valid_passwords:
            is_valid, _ = validate_password_strength(password)
            assert is_valid is True, f"Password {password} should be valid"

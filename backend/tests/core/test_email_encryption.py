"""Tests for email encryption, hashing, and masking utilities."""

import pytest

from src.core.security import (
    decrypt_email,
    encrypt_email,
    hash_email,
    mask_email,
    normalize_email,
)


class TestEmailEncryption:
    """Tests for email encryption/decryption."""

    def test_encrypt_and_decrypt_email(self) -> None:
        """Encrypted email can be decrypted back to original."""
        email = "user@example.com"
        encrypted = encrypt_email(email)
        decrypted = decrypt_email(encrypted)

        assert decrypted == email.lower()  # Normalized to lowercase

    def test_encrypt_produces_different_output_each_time(self) -> None:
        """Fernet produces different ciphertext each time (due to IV)."""
        email = "test@example.com"
        encrypted1 = encrypt_email(email)
        encrypted2 = encrypt_email(email)

        # Different ciphertext due to random IV
        assert encrypted1 != encrypted2

        # But both decrypt to same value
        assert decrypt_email(encrypted1) == decrypt_email(encrypted2)

    def test_encrypt_normalizes_email(self) -> None:
        """Email is normalized (lowercase, stripped) before encryption."""
        original = "  USER@EXAMPLE.COM  "
        encrypted = encrypt_email(original)
        decrypted = decrypt_email(encrypted)

        assert decrypted == "user@example.com"

    def test_encrypted_email_is_base64_string(self) -> None:
        """Encrypted email is a base64-encoded string."""
        email = "test@example.com"
        encrypted = encrypt_email(email)

        # Fernet produces URL-safe base64
        assert isinstance(encrypted, str)
        assert len(encrypted) > len(email)  # Encrypted is longer

    def test_decrypt_invalid_data_raises_error(self) -> None:
        """Decrypting invalid data raises an error."""
        with pytest.raises(Exception):
            decrypt_email("not-valid-encrypted-data")


class TestEmailHashing:
    """Tests for email hashing (HMAC-SHA256 with pepper)."""

    def test_hash_email_produces_hex_string(self) -> None:
        """Hash is a 64-character hex string (HMAC-SHA256)."""
        email = "test@example.com"
        hashed = hash_email(email)

        assert isinstance(hashed, str)
        assert len(hashed) == 64
        assert all(c in "0123456789abcdef" for c in hashed)

    def test_hash_is_not_simple_sha256(self) -> None:
        """Hash uses HMAC with pepper, not simple SHA256 (rainbow table protection)."""
        import hashlib

        email = "test@example.com"
        normalized = email.lower().strip()

        # Simple SHA256 (vulnerable to rainbow tables)
        simple_sha256 = hashlib.sha256(normalized.encode()).hexdigest()

        # Our HMAC hash (protected by pepper)
        hmac_hash = hash_email(email)

        # They must be different (proves we're using pepper)
        assert hmac_hash != simple_sha256

    def test_hash_email_is_deterministic(self) -> None:
        """Same email always produces same hash."""
        email = "user@example.com"
        hash1 = hash_email(email)
        hash2 = hash_email(email)

        assert hash1 == hash2

    def test_hash_email_normalizes_input(self) -> None:
        """Email is normalized before hashing (case-insensitive lookup)."""
        hash_lower = hash_email("user@example.com")
        hash_upper = hash_email("USER@EXAMPLE.COM")
        hash_mixed = hash_email("  User@Example.COM  ")

        assert hash_lower == hash_upper == hash_mixed

    def test_different_emails_produce_different_hashes(self) -> None:
        """Different emails have different hashes."""
        hash1 = hash_email("user1@example.com")
        hash2 = hash_email("user2@example.com")

        assert hash1 != hash2


class TestEmailMasking:
    """Tests for email masking."""

    def test_mask_standard_email(self) -> None:
        """Standard email is masked correctly."""
        masked = mask_email("tristan@gmail.com")
        assert masked == "t***@g****.com"

    def test_mask_email_with_subdomain(self) -> None:
        """Email with subdomain is masked correctly."""
        masked = mask_email("user@mail.example.com")
        # The domain part before the TLD gets masked
        assert masked == "u***@m****.com"

    def test_mask_short_email(self) -> None:
        """Short email addresses are handled correctly."""
        masked = mask_email("a@b.co")
        assert masked == "a***@b****.co"

    def test_mask_long_local_part(self) -> None:
        """Long local part is masked to first char + ***."""
        masked = mask_email("verylongemail@domain.com")
        assert masked == "v***@d****.com"

    def test_mask_normalizes_email(self) -> None:
        """Email is normalized (lowercase) before masking."""
        masked = mask_email("USER@GMAIL.COM")
        assert masked == "u***@g****.com"

    def test_mask_with_whitespace(self) -> None:
        """Email with whitespace is trimmed."""
        masked = mask_email("  user@gmail.com  ")
        assert masked == "u***@g****.com"

    def test_mask_invalid_email_returns_placeholder(self) -> None:
        """Invalid email returns placeholder mask."""
        assert mask_email("") == "***@***.***"
        assert mask_email("not-an-email") == "***@***.***"
        assert mask_email(None) == "***@***.***"  # type: ignore

    def test_mask_preserves_tld(self) -> None:
        """TLD is preserved in masked email."""
        assert mask_email("user@example.org").endswith(".org")
        assert mask_email("user@example.co.uk").endswith(".uk")
        assert mask_email("user@example.io").endswith(".io")

    def test_mask_complex_email(self) -> None:
        """Complex email with dots in local part."""
        masked = mask_email("first.last@company.com")
        assert masked == "f***@c****.com"

    def test_mask_plus_addressing(self) -> None:
        """Email with plus addressing."""
        masked = mask_email("user+tag@gmail.com")
        assert masked == "u***@g****.com"


class TestEmailNormalization:
    """Tests for email normalization using email-validator."""

    def test_normalize_lowercase(self) -> None:
        """Email is lowercased during normalization."""
        assert normalize_email("USER@EXAMPLE.COM") == "user@example.com"

    def test_normalize_strips_whitespace(self) -> None:
        """Leading/trailing whitespace is stripped."""
        assert normalize_email("  user@example.com  ") == "user@example.com"

    def test_normalize_mixed_case(self) -> None:
        """Mixed case is normalized to lowercase."""
        assert normalize_email("User.Name@Gmail.COM") == "user.name@gmail.com"

    def test_normalize_preserves_plus_addressing(self) -> None:
        """Plus addressing is preserved."""
        assert normalize_email("user+tag@example.com") == "user+tag@example.com"

    def test_normalize_invalid_email_raises(self) -> None:
        """Invalid email raises EmailNotValidError."""
        from email_validator import EmailNotValidError

        with pytest.raises(EmailNotValidError):
            normalize_email("not-an-email")

    def test_normalize_empty_raises(self) -> None:
        """Empty string raises error."""
        from email_validator import EmailNotValidError

        with pytest.raises(EmailNotValidError):
            normalize_email("")

    def test_hash_consistency_after_normalization(self) -> None:
        """Different case/whitespace variants produce same hash."""
        variants = [
            "user@example.com",
            "USER@EXAMPLE.COM",
            "  user@example.com  ",
            "User@Example.Com",
        ]
        hashes = [hash_email(v) for v in variants]
        assert len(set(hashes)) == 1  # All should be identical

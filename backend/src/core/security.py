import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt

from src.core.config import get_settings
from src.core.exceptions import InvalidTokenError, TokenExpiredError
from src.core.logging import get_logger

settings = get_settings()
log = get_logger(__name__)


# =============================================================================
# Password Hashing
# =============================================================================


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Note: bcrypt has a 72-byte limit. Passwords are truncated to 72 bytes
    before hashing, which is handled automatically by bcrypt.
    """
    # Encode password to bytes, truncate to 72 bytes (bcrypt limit)
    password_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    password_bytes = plain_password.encode("utf-8")[:72]
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# =============================================================================
# JWT Token Management
# =============================================================================


def create_access_token(
    subject: str | UUID,
    scopes: list[str] | None = None,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a JWT access token with OAuth2 scopes.

    Args:
        subject: The subject of the token (typically user_id)
        scopes: List of OAuth2 scopes granted to this token
        expires_delta: Custom expiration time
        extra_claims: Additional claims to include in the token

    Returns:
        Encoded JWT token string
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    expire = datetime.now(timezone.utc) + expires_delta

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
        "scopes": scopes or [],
    }

    if extra_claims:
        to_encode.update(extra_claims)

    encoded = jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)
    log.debug(
        "access_token_created",
        subject=str(subject),
        expires_in_minutes=settings.jwt_access_token_expire_minutes,
    )
    return encoded


def create_refresh_token(
    subject: str | UUID,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT refresh token.

    Args:
        subject: The subject of the token (typically user_id)
        expires_delta: Custom expiration time

    Returns:
        Encoded JWT refresh token string
    """
    if expires_delta is None:
        expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)

    expire = datetime.now(timezone.utc) + expires_delta

    jti = str(uuid4())

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "jti": jti,
    }

    encoded = jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)
    log.debug(
        "refresh_token_created",
        subject=str(subject),
        expires_in_days=settings.jwt_refresh_token_expire_days,
    )
    return encoded


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: The JWT token string

    Returns:
        Decoded token payload

    Raises:
        TokenExpiredError: If the token has expired
        InvalidTokenError: If the token is invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        log.warning("token_expired")
        raise TokenExpiredError() from e
    except JWTError as e:
        log.warning("token_invalid")
        raise InvalidTokenError() from e


def get_token_subject(token: str) -> str:
    """Extract the subject (user_id) from a token.

    Args:
        token: The JWT token string

    Returns:
        The subject claim from the token

    Raises:
        InvalidTokenError: If subject is missing or invalid
    """
    payload = decode_token(token)
    subject = payload.get("sub")
    if not subject:
        raise InvalidTokenError(detail="Token missing subject claim")
    return subject


def verify_token_type(token: str, expected_type: str) -> dict[str, Any]:
    """Verify that a token is of the expected type.

    Args:
        token: The JWT token string
        expected_type: Expected token type ("access" or "refresh")

    Returns:
        Decoded token payload

    Raises:
        InvalidTokenError: If token type doesn't match
    """
    payload = decode_token(token)
    token_type = payload.get("type")
    if token_type != expected_type:
        raise InvalidTokenError(detail=f"Expected {expected_type} token, got {token_type}")
    return payload


def hash_token(token: str) -> str:
    """Create a SHA-256 hash of a token for server-side storage.

    Args:
        token: The raw JWT token string

    Returns:
        SHA-256 hex digest (64 characters)
    """
    return hashlib.sha256(token.encode()).hexdigest()


# =============================================================================
# Fernet Encryption (for API keys storage)
# =============================================================================


def get_fernet() -> Fernet:
    """Get Fernet instance for encryption/decryption.

    The encryption key should be a valid Fernet key (32 url-safe base64-encoded bytes).
    If the configured key is not valid, it will be used to derive a valid key.
    """
    key = settings.encryption_key
    # If key is not a valid Fernet key, use it as a passphrase to derive one
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, InvalidToken):
        log.warning("fernet_key_derivation_fallback")
        import base64
        import hashlib

        derived = hashlib.sha256(key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(derived)
        return Fernet(fernet_key)


def encrypt_value(value: str) -> str:
    """Encrypt a string value using Fernet.

    Args:
        value: Plain text value to encrypt

    Returns:
        Encrypted value as a string
    """
    fernet = get_fernet()
    encrypted = fernet.encrypt(value.encode())
    return encrypted.decode()


def decrypt_value(encrypted_value: str) -> str:
    """Decrypt a Fernet-encrypted value.

    Args:
        encrypted_value: Encrypted string

    Returns:
        Decrypted plain text value

    Raises:
        InvalidToken: If decryption fails
    """
    fernet = get_fernet()
    decrypted = fernet.decrypt(encrypted_value.encode())
    return decrypted.decode()


# =============================================================================
# Utility Functions
# =============================================================================


def utc_timestamp_ms() -> int:
    """Return current UTC timestamp in milliseconds."""
    return int(time.time() * 1000)


# =============================================================================
# Email Encryption (PII Protection)
# =============================================================================


def _get_email_fernet() -> Fernet:
    """Get Fernet instance for email encryption/decryption.

    Uses a separate key from API key encryption for defense in depth.
    """
    key = settings.email_encryption_key
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, InvalidToken):
        import base64
        import hashlib

        derived = hashlib.sha256(key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(derived)
        return Fernet(fernet_key)


def normalize_email(email: str) -> str:
    """Normalize an email address using email-validator.

    Handles case normalization, invisible characters, and validates format.
    Uses email-validator library for robust canonicalization.

    Note: Per RFC 5321, local parts are technically case-sensitive, but in
    practice virtually all email providers treat them as case-insensitive.
    For authentication, we lowercase the entire email for consistent lookup.

    Args:
        email: Email address to normalize

    Returns:
        Normalized lowercase email string

    Raises:
        EmailNotValidError: If email format is invalid
    """
    from email_validator import validate_email

    # Strip leading/trailing whitespace before validation
    stripped = email.strip()
    result = validate_email(stripped, check_deliverability=False)
    # Lowercase entire email for case-insensitive authentication
    # (email-validator lowercases domain but preserves local part case)
    return result.normalized.lower()


def encrypt_email(email: str) -> str:
    """Encrypt an email address using AES-256-GCM (Fernet).

    Email is normalized before encryption using email-validator.

    Args:
        email: Plain text email address

    Returns:
        Encrypted email as a base64-encoded string
    """
    fernet = _get_email_fernet()
    normalized = normalize_email(email)
    encrypted = fernet.encrypt(normalized.encode())
    return encrypted.decode()


def decrypt_email(encrypted_email: str) -> str:
    """Decrypt a Fernet-encrypted email.

    Args:
        encrypted_email: Encrypted email string

    Returns:
        Decrypted plain text email

    Raises:
        InvalidToken: If decryption fails
    """
    fernet = _get_email_fernet()
    decrypted = fernet.decrypt(encrypted_email.encode())
    return decrypted.decode()


def hash_email(email: str) -> str:
    """Create a keyed HMAC-SHA256 hash of an email for lookup.

    Uses HMAC with a secret pepper to prevent rainbow table attacks.
    Email is normalized using email-validator before hashing.

    Args:
        email: Email address to hash

    Returns:
        HMAC-SHA256 hash as a 64-character hex string
    """
    import hashlib
    import hmac

    normalized = normalize_email(email)
    pepper = settings.email_hash_pepper.encode()
    return hmac.new(pepper, normalized.encode(), hashlib.sha256).hexdigest()


def mask_email(email: str) -> str:
    """Mask an email for safe display.

    Format: first char of local part + *** + @ + first char of domain + **** + TLD
    Example: "tristan.doe@gmail.com" -> "t***@g****.com"

    Args:
        email: Plain text email address

    Returns:
        Masked email string
    """
    if not email or "@" not in email:
        return "***@***.***"

    # Use email-validator for robust normalization
    try:
        normalized = normalize_email(email)
    except Exception:
        # Fallback for invalid emails
        normalized = email.lower().strip()

    local, domain = normalized.rsplit("@", 1)

    # Handle empty local part
    if not local:
        masked_local = "***"
    else:
        masked_local = f"{local[0]}***"

    # Handle domain with TLD
    if "." in domain:
        domain_name, tld = domain.rsplit(".", 1)
        if not domain_name:
            masked_domain = f"****.{tld}"
        else:
            masked_domain = f"{domain_name[0]}****.{tld}"
    else:
        masked_domain = f"{domain[0] if domain else '*'}****"

    return f"{masked_local}@{masked_domain}"

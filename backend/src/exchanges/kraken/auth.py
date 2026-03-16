"""Kraken Futures API authentication and signature generation.

Kraken Futures uses HMAC-SHA512 signature for authenticated requests.
The signature is computed from: SHA256(post_data + nonce + endpoint_path)
then HMAC-SHA512(base64_decode(secret), sha256_hash), base64 encoded.

Critical: The signing path differs from the URL path for endpoints under
/derivatives/. The /derivatives prefix must be stripped for signing.
"""

import base64
import hashlib
import hmac
import time


def get_nonce() -> str:
    """Get current UTC timestamp in milliseconds as string (used as nonce)."""
    return str(int(time.time() * 1000))


def create_signature(
    secret_key: str,
    endpoint_path: str,
    post_data: str,
    nonce: str,
) -> str:
    """Create HMAC-SHA512 signature for Kraken Futures API.

    Algorithm:
    1. message = post_data + nonce + endpoint_path
    2. sha256_hash = SHA256(message)
    3. hmac_digest = HMAC-SHA512(base64_decode(secret), sha256_hash)
    4. signature = base64_encode(hmac_digest)

    Args:
        secret_key: API secret key (base64-encoded)
        endpoint_path: The signing path (NOT the URL path for /derivatives/ endpoints)
        post_data: Query string without leading '?' (empty string for no params)
        nonce: Timestamp in milliseconds

    Returns:
        Base64-encoded signature string
    """
    # Step 1: Build message
    message = post_data + nonce + endpoint_path

    # Step 2: SHA256 hash of message
    sha256_hash = hashlib.sha256(message.encode("utf-8")).digest()

    # Step 3: HMAC-SHA512 with base64-decoded secret
    secret_decoded = base64.b64decode(secret_key)
    hmac_digest = hmac.new(secret_decoded, sha256_hash, hashlib.sha512).digest()

    # Step 4: Base64 encode
    return base64.b64encode(hmac_digest).decode("utf-8")


def create_auth_headers(
    public_key: str,
    secret_key: str,
    signing_path: str,
    post_data: str = "",
) -> dict[str, str]:
    """Create authentication headers for Kraken Futures API request.

    Args:
        public_key: API public key
        secret_key: API secret key (base64-encoded)
        signing_path: The path used for signature computation
        post_data: Query string without leading '?' (empty for no params)

    Returns:
        Dictionary of authentication headers (APIKey, Nonce, Authent)
    """
    nonce = get_nonce()
    signature = create_signature(secret_key, signing_path, post_data, nonce)

    return {
        "APIKey": public_key,
        "Nonce": nonce,
        "Authent": signature,
    }

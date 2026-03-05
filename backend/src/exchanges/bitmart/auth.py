"""Bitmart API authentication and signature generation.

Bitmart uses HMAC-SHA256 signature for authenticated requests.
The signature is computed from: timestamp + '#' + memo + '#' + queryString/body
"""

import hashlib
import hmac
import time
from urllib.parse import urlencode


def get_timestamp() -> str:
    """Get current UTC timestamp in milliseconds as string."""
    return str(int(time.time() * 1000))


def create_signature(
    secret_key: str,
    timestamp: str,
    memo: str,
    query_string: str = "",
) -> str:
    """Create HMAC-SHA256 signature for Bitmart API.

    The signature is computed as:
    HexDigest(HMAC-SHA256(secretKey, timestamp + '#' + memo + '#' + queryString))

    Note: Bitmart uses hex digest, not base64 (unlike Bitget).

    Args:
        secret_key: API secret key
        timestamp: Request timestamp in milliseconds
        memo: API memo (required by Bitmart)
        query_string: Query string for GET or JSON body for POST

    Returns:
        Hex-encoded signature string
    """
    # Build pre-hash string: timestamp#memo#queryString
    pre_hash = f"{timestamp}#{memo}#{query_string}"

    # Compute HMAC-SHA256
    mac = hmac.new(
        secret_key.encode("utf-8"),
        pre_hash.encode("utf-8"),
        digestmod=hashlib.sha256,
    )

    # Return hex-encoded signature (Bitmart uses hex, not base64)
    return mac.hexdigest()


def build_query_string(params: dict | None) -> str:
    """Build query string from parameters.

    Args:
        params: Dictionary of query parameters

    Returns:
        URL-encoded query string (without leading '?')
    """
    if not params:
        return ""

    # URL-encode parameters
    return urlencode(params)


def create_auth_headers(
    public_key: str,
    secret_key: str,
    memo: str,
    timestamp: str,
    query_string: str = "",
) -> dict[str, str]:
    """Create authentication headers for Bitmart API request.

    Args:
        public_key: API public key (X-BM-KEY)
        secret_key: API secret key (for signature)
        memo: API memo (required by Bitmart)
        timestamp: Request timestamp in milliseconds
        query_string: Query string for GET or JSON body for POST

    Returns:
        Dictionary of authentication headers
    """
    signature = create_signature(secret_key, timestamp, memo, query_string)

    return {
        "X-BM-KEY": public_key,
        "X-BM-SIGN": signature,
        "X-BM-TIMESTAMP": timestamp,
        "X-BM-BROKER-ID": "EdgeTrack",
    }

"""Bitget API authentication and signature generation.

Bitget uses HMAC-SHA256 signature for authenticated requests.
The signature is computed from: timestamp + method + requestPath + body
"""

import base64
import hmac
import time
from urllib.parse import urlencode


def get_timestamp() -> str:
    """Get current UTC timestamp in milliseconds as string."""
    return str(int(time.time() * 1000))


def create_signature(
    secret_key: str,
    timestamp: str,
    method: str,
    request_path: str,
    body: str = "",
) -> str:
    """Create HMAC-SHA256 signature for Bitget API.

    The signature is computed as:
    Base64(HMAC-SHA256(secretKey, timestamp + method + requestPath + body))

    Args:
        secret_key: API secret key
        timestamp: Request timestamp in milliseconds
        method: HTTP method (uppercase: GET, POST)
        request_path: Full request path including query string
        body: Request body (empty string for GET requests)

    Returns:
        Base64-encoded signature string
    """
    # Build pre-hash string
    pre_hash = timestamp + method.upper() + request_path + body

    # Compute HMAC-SHA256
    mac = hmac.new(
        secret_key.encode("utf-8"),
        pre_hash.encode("utf-8"),
        digestmod="sha256",
    )

    # Return base64-encoded signature
    return base64.b64encode(mac.digest()).decode("utf-8")


def build_query_string(params: dict | None) -> str:
    """Build sorted query string from parameters.

    Bitget requires query parameters to be sorted alphabetically.

    Args:
        params: Dictionary of query parameters

    Returns:
        URL-encoded query string (including leading '?' if params exist)
    """
    if not params:
        return ""

    # Sort parameters alphabetically by key
    sorted_params = sorted(params.items(), key=lambda x: x[0])

    # URL-encode
    query_string = urlencode(sorted_params)

    return f"?{query_string}" if query_string else ""


def create_auth_headers(
    public_key: str,
    secret_key: str,
    passphrase: str,
    method: str,
    request_path: str,
    body: str = "",
) -> dict[str, str]:
    """Create authentication headers for Bitget API request.

    Args:
        public_key: API public key (ACCESS-KEY)
        secret_key: API secret key (for signature)
        passphrase: API passphrase (ACCESS-PASSPHRASE)
        method: HTTP method
        request_path: Full request path including query string
        body: Request body

    Returns:
        Dictionary of authentication headers
    """
    timestamp = get_timestamp()
    signature = create_signature(secret_key, timestamp, method, request_path, body)

    return {
        "ACCESS-KEY": public_key,
        "ACCESS-SIGN": signature,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": passphrase,
        "locale": "en-US",
    }

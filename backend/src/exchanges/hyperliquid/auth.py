"""Hyperliquid authentication (trivial).

Hyperliquid info endpoints are public and require no API key signing.
Only a wallet address is needed for user-specific queries.
"""

import re


def validate_wallet_address(address: str) -> bool:
    """Validate Ethereum-style wallet address format (0x + 40 hex chars).

    Args:
        address: Wallet address to validate

    Returns:
        True if address is a valid hex address
    """
    return bool(re.match(r"^0x[0-9a-fA-F]{40}$", address))

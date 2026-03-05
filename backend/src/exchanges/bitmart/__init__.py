"""Bitmart exchange connector.

This module provides the BitmartConnector for interacting with
Bitmart's Futures API.

Example:
    from src.exchanges.bitmart import BitmartConnector
    from src.exchanges.schemas import Credentials

    credentials = Credentials(
        public_key="...",
        secret_key="...",
        memo="...",
    )
    connector = BitmartConnector(credentials)
    result = await connector.validate_credentials()
"""

from src.exchanges.bitmart.connector import BitmartConnector

__all__ = ["BitmartConnector"]

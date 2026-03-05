"""Tests for Hyperliquid auth module."""

import pytest

from src.exchanges.hyperliquid.auth import validate_wallet_address


class TestValidateWalletAddress:
    """Tests for wallet address validation."""

    def test_valid_address_lowercase(self):
        assert validate_wallet_address("0x1234567890abcdef1234567890abcdef12345678")

    def test_valid_address_uppercase(self):
        assert validate_wallet_address("0xABCDEF1234567890ABCDEF1234567890ABCDEF12")

    def test_valid_address_mixed_case(self):
        assert validate_wallet_address("0xAbCdEf1234567890aBcDeF1234567890AbCdEf12")

    def test_invalid_no_prefix(self):
        assert not validate_wallet_address("1234567890abcdef1234567890abcdef12345678")

    def test_invalid_too_short(self):
        assert not validate_wallet_address("0x1234567890abcdef")

    def test_invalid_too_long(self):
        assert not validate_wallet_address("0x1234567890abcdef1234567890abcdef1234567890")

    def test_invalid_non_hex(self):
        assert not validate_wallet_address("0xGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG")

    def test_invalid_empty(self):
        assert not validate_wallet_address("")

    def test_invalid_just_prefix(self):
        assert not validate_wallet_address("0x")

    def test_zero_address(self):
        assert validate_wallet_address("0x0000000000000000000000000000000000000000")

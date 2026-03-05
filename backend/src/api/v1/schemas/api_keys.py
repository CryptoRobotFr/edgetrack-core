"""ApiKey schemas for request/response validation."""

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.exchanges.constants import ExchangeName


class ApiKeyCreateRequest(BaseModel):
    """Request body for creating an API key."""

    name: str = Field(..., min_length=1, max_length=100)
    exchange_name: ExchangeName
    public_key: str = Field(..., min_length=1, max_length=255)
    secret_key: str = Field(..., min_length=1, max_length=1000)
    passphrase: str | None = Field(None, description="Required for Bitget")
    memo: str | None = Field(None, description="Required for Bitmart")

    @model_validator(mode="after")
    def validate_exchange_fields(self) -> "ApiKeyCreateRequest":
        """Validate exchange-specific required fields."""
        if self.exchange_name == ExchangeName.BITGET and not self.passphrase:
            raise ValueError("passphrase is required for Bitget")
        if self.exchange_name == ExchangeName.BITMART and not self.memo:
            raise ValueError("memo is required for Bitmart")
        return self


class TestConnectionRequest(BaseModel):
    """Request body for testing an API key connection."""

    api_key_id: UUID


class TestConnectionResponse(BaseModel):
    """Response from testing an API key connection."""

    valid: bool
    error_message: str | None = None


class ApiKeyResponse(BaseModel):
    """Response containing API key information (without secrets)."""

    id: UUID
    name: str
    exchange_name: str
    public_key: str
    accounts_count: int = Field(..., description="Number of accounts using this API key")
    created_at: int
    updated_at: int

"""Account schemas for request/response validation."""

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.models.enums import AccountType, ProductType


class AccountCreateRequest(BaseModel):
    """Request body for creating an account."""

    api_key_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    account_type: AccountType
    product_type: ProductType | None = Field(
        None, description="Required for futures accounts"
    )

    @model_validator(mode="after")
    def validate_product_type(self) -> "AccountCreateRequest":
        """Validate product_type based on account_type."""
        if self.account_type == AccountType.FUTURES and not self.product_type:
            raise ValueError("product_type is required for futures accounts")
        if self.account_type == AccountType.SPOT and self.product_type:
            raise ValueError("product_type must be null for spot accounts")
        return self


class AccountResponse(BaseModel):
    """Response containing account information."""

    id: UUID
    name: str
    account_type: str
    product_type: str | None
    exchange_name: str
    exchange_avatar_url: str | None
    api_key_name: str
    is_demo: bool
    created_at: int
    updated_at: int


class AccountUpdateRequest(BaseModel):
    """Request body for updating an account."""

    name: str | None = Field(None, min_length=1, max_length=100)
    api_key_id: UUID | None = Field(
        None, description="New API key to associate (must belong to user, same exchange)"
    )


class AccountOverviewItem(BaseModel):
    """Enriched account data for the overview page."""

    id: UUID
    name: str
    account_type: str
    product_type: str | None
    exchange_name: str
    exchange_avatar_url: str | None
    api_key_id: UUID
    api_key_name: str
    is_connected: bool
    equity: float | None
    total_trades: int
    last_sync_date: int | None
    sync_in_progress: bool
    is_demo: bool
    created_at: int
    updated_at: int


class AccountsOverviewResponse(BaseModel):
    """Response for the accounts overview endpoint."""

    accounts: list[AccountOverviewItem]


class AccountDeleteResponse(BaseModel):
    """Response for account deletion with orphaned key info."""

    deleted: bool
    orphaned_api_key_id: UUID | None = None
    orphaned_api_key_name: str | None = None

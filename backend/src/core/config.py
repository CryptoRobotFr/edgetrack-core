from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    mode: str = "local"
    debug: bool = False

    # Database - both URLs available, active one selected based on mode
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/edgetrack"
    database_url_local: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/edgetrack"

    # Computed: active database URL based on mode
    active_database_url: str = ""

    # Database pool settings
    db_pool_size: int = 5
    db_pool_max_overflow: int = 10

    # Security
    secret_key: str = "change-me-in-production"
    encryption_key: str = "change-me-in-production"
    email_encryption_key: str = "change-me-in-production-32-bytes!"
    email_hash_pepper: str = "change-me-in-production-pepper"  # HMAC key for email hashing

    # JWT Settings
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440  # 24 hours
    jwt_refresh_token_expire_days: int = 7

    # Registration
    registration_enabled: bool = False

    # Server
    backend_port: int = 8000

    # CORS - allowed origins for frontend
    cors_origins: list[str] = ["http://localhost:3000"]

    # Logging
    log_level: str = "INFO"

    # Exchange enablement (comma-separated, empty = all enabled)
    enabled_exchanges: str = ""

    @model_validator(mode="after")
    def set_active_database_url(self) -> "Settings":
        """Select database URL based on mode (local uses localhost, else docker network)."""
        if self.mode == "local":
            self.active_database_url = self.database_url_local
        else:
            self.active_database_url = self.database_url
        return self

    @model_validator(mode="after")
    def validate_secrets_not_default(self) -> "Settings":
        """Refuse to start if cryptographic secrets are still set to default values.

        In local mode, only logs a warning. In other modes (production/staging),
        raises an error to prevent deployment with insecure defaults.
        """
        import logging as _logging

        defaults = {
            "secret_key": "change-me-in-production",
            "encryption_key": "change-me-in-production",
            "email_encryption_key": "change-me-in-production-32-bytes!",
            "email_hash_pepper": "change-me-in-production-pepper",
        }
        insecure = [
            name for name, default in defaults.items()
            if getattr(self, name) == default
        ]
        if insecure:
            msg = (
                f"SECURITY: The following secrets still use default values: "
                f"{', '.join(insecure)}. "
                f"Set the corresponding environment variables to secure random values."
            )
            if self.mode != "local":
                raise ValueError(msg)
            _logging.getLogger(__name__).warning(msg)
        return self

    @property
    def enabled_exchange_list(self) -> list[str] | None:
        """Parse enabled exchanges. None = all enabled."""
        if not self.enabled_exchanges:
            return None
        return [e.strip().lower() for e in self.enabled_exchanges.split(",") if e.strip()]


_settings_instance: Settings | None = None


def set_settings(settings: Settings) -> None:
    """Override the global settings instance (called by SaaS before create_app)."""
    global _settings_instance
    _settings_instance = settings


def get_settings() -> Settings:
    """Get the settings instance."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


def reset_settings() -> None:
    """Reset the settings instance (useful for testing)."""
    global _settings_instance
    _settings_instance = None

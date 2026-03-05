"""CoinGecko coin metadata model.

Persists cryptocurrency metadata (images, market cap, ATH/ATL) to avoid
hitting CoinGecko API rate limits on every server restart.
"""

from sqlalchemy import BigInteger, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class CoinMetadata(TimestampMixin, Base):
    """Cached cryptocurrency metadata from CoinGecko.

    Table name: coin_metadatas (auto-generated).
    Keyed by uppercase symbol (e.g., 'BTC').
    Refreshed from CoinGecko API every 24 hours.
    """

    __tablename__ = "coin_metadata"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    coingecko_id: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    market_cap_rank: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    market_cap: Mapped[str | None] = mapped_column(Numeric(30, 2), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ath: Mapped[str | None] = mapped_column(Numeric(30, 10), nullable=True)
    ath_date_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    atl: Mapped[str | None] = mapped_column(Numeric(30, 10), nullable=True)
    atl_date_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

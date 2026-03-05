import time
from typing import Any

from sqlalchemy import BigInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


def utc_timestamp_ms() -> int:
    """Return current UTC timestamp in milliseconds."""
    return int(time.time() * 1000)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    id: Any

    @declared_attr.directive
    def __tablename__(cls) -> str:
        """Generate table name from class name (snake_case, plural)."""
        name = cls.__name__
        # Convert CamelCase to snake_case
        result = [name[0].lower()]
        for char in name[1:]:
            if char.isupper():
                result.append("_")
                result.append(char.lower())
            else:
                result.append(char)
        # Add 's' for plural (simple rule)
        table_name = "".join(result)
        if not table_name.endswith("s"):
            table_name += "s"
        return table_name


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps (UTC milliseconds)."""

    created_at: Mapped[int] = mapped_column(
        BigInteger,
        default=utc_timestamp_ms,
        nullable=False,
    )
    updated_at: Mapped[int] = mapped_column(
        BigInteger,
        default=utc_timestamp_ms,
        onupdate=utc_timestamp_ms,
        nullable=False,
    )

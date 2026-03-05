"""Standardized exceptions for all exchange connectors.

All exchange-specific error codes are mapped to these standardized exceptions.
This provides a consistent error handling interface regardless of which
exchange is being used.
"""

from src.core.exceptions import EdgeTrackException


class ExchangeError(EdgeTrackException):
    """Base exception for all exchange-related errors.

    All exchange exceptions inherit from this class.
    """

    status_code = 502
    error_type = "exchange_error"
    title = "Exchange Error"

    def __init__(
        self,
        detail: str,
        *,
        exchange: str | None = None,
        api_code: str | None = None,
    ) -> None:
        extra = {}
        if exchange:
            extra["exchange"] = exchange
        if api_code:
            extra["api_code"] = api_code
        super().__init__(detail=detail, extra=extra if extra else None)
        self.exchange = exchange
        self.api_code = api_code


class ExchangeAuthenticationError(ExchangeError):
    """Raised when API key authentication fails.

    Causes:
    - Invalid API key
    - Invalid secret key
    - Invalid passphrase/memo
    - Expired API key
    - Invalid signature

    This error should NOT trigger a retry.
    """

    status_code = 401
    error_type = "exchange_authentication_error"
    title = "Exchange Authentication Failed"


class ExchangePermissionError(ExchangeError):
    """Raised when API key lacks required permissions.

    Causes:
    - API key doesn't have read permission
    - API key doesn't have futures trading enabled
    - IP not whitelisted
    - Account suspended

    This error should NOT trigger a retry.
    """

    status_code = 403
    error_type = "exchange_permission_error"
    title = "Exchange Permission Denied"


class ExchangeRateLimitError(ExchangeError):
    """Raised when exchange rate limit is exceeded.

    This error SHOULD trigger a retry with exponential backoff.
    """

    status_code = 429
    error_type = "exchange_rate_limit_error"
    title = "Exchange Rate Limit Exceeded"

    def __init__(
        self,
        detail: str = "Rate limit exceeded, please try again later",
        *,
        exchange: str | None = None,
        api_code: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(detail=detail, exchange=exchange, api_code=api_code)
        self.retry_after = retry_after
        if retry_after:
            self.extra["retry_after"] = retry_after


class ExchangeInvalidSymbolError(ExchangeError):
    """Raised when the trading symbol/pair is invalid.

    Causes:
    - Symbol doesn't exist
    - Symbol delisted
    - Symbol not available for the product type

    This error should NOT trigger a retry.
    """

    status_code = 400
    error_type = "exchange_invalid_symbol_error"
    title = "Invalid Trading Symbol"

    def __init__(
        self,
        detail: str,
        *,
        exchange: str | None = None,
        api_code: str | None = None,
        symbol: str | None = None,
    ) -> None:
        super().__init__(detail=detail, exchange=exchange, api_code=api_code)
        self.symbol = symbol
        if symbol:
            self.extra["symbol"] = symbol


class ExchangeInvalidParameterError(ExchangeError):
    """Raised when request parameters are invalid.

    Causes:
    - Invalid time range
    - Invalid interval
    - Missing required parameter
    - Parameter out of bounds

    This error should NOT trigger a retry.
    """

    status_code = 400
    error_type = "exchange_invalid_parameter_error"
    title = "Invalid Request Parameter"


class ExchangeUnavailableError(ExchangeError):
    """Raised when exchange is temporarily unavailable.

    Causes:
    - Exchange maintenance
    - Exchange overloaded
    - Network issues
    - Temporary server errors

    This error SHOULD trigger a retry with exponential backoff.
    """

    status_code = 503
    error_type = "exchange_unavailable_error"
    title = "Exchange Temporarily Unavailable"


# Exceptions that should trigger retry
RETRYABLE_EXCEPTIONS = (
    ExchangeRateLimitError,
    ExchangeUnavailableError,
)

# Exceptions that should NOT trigger retry
NON_RETRYABLE_EXCEPTIONS = (
    ExchangeAuthenticationError,
    ExchangePermissionError,
    ExchangeInvalidSymbolError,
    ExchangeInvalidParameterError,
)

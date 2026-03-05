from typing import Any


class EdgeTrackException(Exception):
    """Base exception for all EdgeTrack errors.

    All custom exceptions should inherit from this class.
    Provides RFC 7807 compliant error structure.
    """

    status_code: int = 500
    error_type: str = "internal_error"
    title: str = "Internal Server Error"

    def __init__(
        self,
        detail: str | None = None,
        *,
        status_code: int | None = None,
        error_type: str | None = None,
        title: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.detail = detail or "An unexpected error occurred"
        if status_code is not None:
            self.status_code = status_code
        if error_type is not None:
            self.error_type = error_type
        if title is not None:
            self.title = title
        self.extra = extra or {}
        super().__init__(self.detail)

    def to_rfc7807(self, correlation_id: str | None = None) -> dict[str, Any]:
        """Convert exception to RFC 7807 problem details format."""
        response = {
            "type": self.error_type,
            "title": self.title,
            "status": self.status_code,
            "detail": self.detail,
        }
        if correlation_id:
            response["correlation_id"] = correlation_id
        if self.extra:
            response.update(self.extra)
        return response


# Authentication & Authorization Exceptions


class AuthenticationError(EdgeTrackException):
    """Raised when authentication fails."""

    status_code = 401
    error_type = "authentication_error"
    title = "Authentication Failed"

    def __init__(self, detail: str = "Authentication failed", **kwargs: Any) -> None:
        super().__init__(detail=detail, **kwargs)


class InvalidCredentialsError(AuthenticationError):
    """Raised when login credentials are invalid."""

    error_type = "invalid_credentials"
    title = "Invalid Credentials"

    def __init__(self, detail: str = "Invalid email or password") -> None:
        super().__init__(detail=detail)


class TokenExpiredError(AuthenticationError):
    """Raised when JWT token has expired."""

    error_type = "token_expired"
    title = "Token Expired"

    def __init__(self, detail: str = "Token has expired") -> None:
        super().__init__(detail=detail)


class InvalidTokenError(AuthenticationError):
    """Raised when JWT token is invalid."""

    error_type = "invalid_token"
    title = "Invalid Token"

    def __init__(self, detail: str = "Token is invalid") -> None:
        super().__init__(detail=detail)


class AuthorizationError(EdgeTrackException):
    """Raised when user lacks permission for an action."""

    status_code = 403
    error_type = "authorization_error"
    title = "Access Denied"

    def __init__(self, detail: str = "You do not have permission to perform this action", **kwargs: Any) -> None:
        super().__init__(detail=detail, **kwargs)


class InactiveUserError(AuthorizationError):
    """Raised when an inactive user tries to access resources."""

    error_type = "inactive_user"
    title = "Account Inactive"

    def __init__(self, detail: str = "User account is inactive") -> None:
        super().__init__(detail=detail)


class RegistrationDisabledError(AuthorizationError):
    """Raised when registration is disabled and no valid invitation token is provided."""

    error_type = "registration_disabled"
    title = "Registration Disabled"

    def __init__(self, detail: str = "Registration is currently disabled") -> None:
        super().__init__(detail=detail)


# Resource Exceptions


class NotFoundError(EdgeTrackException):
    """Raised when a requested resource is not found."""

    status_code = 404
    error_type = "not_found"
    title = "Resource Not Found"

    def __init__(self, resource: str = "Resource", resource_id: str | None = None) -> None:
        detail = f"{resource} not found"
        if resource_id:
            detail = f"{resource} with id '{resource_id}' not found"
        super().__init__(detail=detail, extra={"resource": resource})


class ConflictError(EdgeTrackException):
    """Raised when there's a conflict with existing data."""

    status_code = 409
    error_type = "conflict"
    title = "Resource Conflict"

    def __init__(self, detail: str = "Resource already exists") -> None:
        super().__init__(detail=detail)


class EmailAlreadyExistsError(ConflictError):
    """Raised when trying to register with an existing email."""

    error_type = "email_exists"
    title = "Email Already Registered"

    def __init__(self, detail: str = "A user with this email already exists") -> None:
        super().__init__(detail=detail)


# Validation Exceptions


class ValidationError(EdgeTrackException):
    """Raised when input validation fails."""

    status_code = 422
    error_type = "validation_error"
    title = "Validation Error"

    def __init__(self, detail: str = "Invalid input data", errors: list[dict[str, Any]] | None = None) -> None:
        super().__init__(detail=detail, extra={"errors": errors} if errors else None)


# Exchange & External Service Exceptions


class ExchangeError(EdgeTrackException):
    """Base exception for exchange-related errors."""

    status_code = 502
    error_type = "exchange_error"
    title = "Exchange Error"


class ExchangeAPIError(ExchangeError):
    """Raised when exchange API returns an error."""

    error_type = "exchange_api_error"
    title = "Exchange API Error"

    def __init__(self, exchange: str, detail: str, api_code: str | None = None) -> None:
        extra = {"exchange": exchange}
        if api_code:
            extra["api_code"] = api_code
        super().__init__(detail=detail, extra=extra)


class ExchangeConnectionError(ExchangeError):
    """Raised when unable to connect to exchange."""

    error_type = "exchange_connection_error"
    title = "Exchange Connection Failed"

    def __init__(self, exchange: str, detail: str = "Failed to connect to exchange") -> None:
        super().__init__(detail=detail, extra={"exchange": exchange})


class RateLimitExceededError(EdgeTrackException):
    """Raised when rate limit is exceeded."""

    status_code = 429
    error_type = "rate_limit_exceeded"
    title = "Rate Limit Exceeded"

    def __init__(self, detail: str = "Too many requests, please try again later", retry_after: int | None = None) -> None:
        extra = {"retry_after": retry_after} if retry_after else None
        super().__init__(detail=detail, extra=extra)


# Database Exceptions


class DatabaseError(EdgeTrackException):
    """Raised when a database operation fails."""

    status_code = 500
    error_type = "database_error"
    title = "Database Error"

    def __init__(self, detail: str = "A database error occurred") -> None:
        super().__init__(detail=detail)

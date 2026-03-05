"""Email service interface for sending emails.

Default: ConsoleEmailService logs email content to stdout (open-source / dev).
SaaS override: Implement EmailService with real provider (SendGrid, etc.).
"""

from abc import ABC, abstractmethod

from src.core.logging import get_logger

log = get_logger(__name__)


class EmailService(ABC):
    """Interface for sending emails. Override in SaaS with real provider."""

    @abstractmethod
    async def send(self, to: str, subject: str, html_body: str) -> None:
        """Send an email.

        Args:
            to: Recipient email address
            subject: Email subject
            html_body: HTML email body
        """
        ...


class ConsoleEmailService(EmailService):
    """Default: logs email content to stdout (open-source / dev)."""

    async def send(self, to: str, subject: str, html_body: str) -> None:
        log.info("email_sent_console", to=to, subject=subject)

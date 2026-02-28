"""Low-level email sending via SMTP.

If smtp_host is not configured the send is skipped and a warning is logged,
making local development and testing safe without a real mail server.
"""

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


def _send_email_sync(to: str, subject: str, body: str) -> None:
    """Blocking SMTP send, intended to be run in a thread executor."""
    if not settings.smtp_host:
        logger.warning(
            "SMTP not configured (smtp_host is empty); skipping email to %s: %s",
            to,
            subject,
        )
        return

    msg = MIMEMultipart()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.ehlo()
        server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_from, [to], msg.as_string())

    logger.info("Email sent to %s: %s", to, subject)


async def send_email(to: str, subject: str, body: str) -> None:
    """Send an email asynchronously.

    Runs the blocking SMTP call in a thread executor so it does not block
    the event loop.  Errors are caught and logged rather than propagated so
    that a transient mail-server issue never breaks a game action.
    """
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _send_email_sync, to, subject, body)
    except Exception as exc:
        logger.error("Failed to send email to %s (%s): %s", to, subject, exc)

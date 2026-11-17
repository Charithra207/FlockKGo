"""
mailer.py — send transactional email (password reset, verification).

Uses Resend (RESEND_API_KEY) if set, else SMTP (SMTP_HOST...), else just logs
the message so development works without any email account.
Returns True if an email was actually handed to a provider.
"""

import smtplib
from email.message import EmailMessage

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


def email_configured() -> bool:
    s = get_settings()
    return bool(s.resend_api_key or s.smtp_host)


def send_email(to: str, subject: str, text: str) -> bool:
    s = get_settings()
    try:
        if s.resend_api_key:
            r = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {s.resend_api_key}"},
                json={"from": s.mail_from, "to": [to], "subject": subject, "text": text},
                timeout=15,
            )
            r.raise_for_status()
            return True
        if s.smtp_host:
            msg = EmailMessage()
            msg["From"], msg["To"], msg["Subject"] = s.mail_from, to, subject
            msg.set_content(text)
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
                smtp.starttls()
                if s.smtp_user:
                    smtp.login(s.smtp_user, s.smtp_password or "")
                smtp.send_message(msg)
            return True
    except Exception as exc:  # never let email break the request
        log.warning("email_send_failed", error=str(exc)[:200])
        return False
    log.info("email_not_configured", subject=subject)
    return False

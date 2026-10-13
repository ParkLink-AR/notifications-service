"""Transactional email through Brevo's REST API -- the same provider auth-service uses for
its account emails. Without BREVO_API_KEY it only logs (local runs, tests)."""

import httpx
from loguru import logger

from app.config import settings

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def send_email(to_email: str, subject: str, html_body: str, reply_to: str | None = None) -> bool:
    """Sends one email. Returns whether Brevo accepted it -- a failure is logged, never raised:
    an email is a heads-up, and must not make the event that triggered it be retried."""
    if not settings.BREVO_API_KEY:
        logger.info(f"[mail] BREVO_API_KEY not set -- would send to {to_email}: {subject}")
        return False
    payload: dict = {
        "sender": {"name": settings.EMAIL_FROM_NAME, "email": settings.EMAIL_FROM},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_body,
    }
    if reply_to:
        payload["replyTo"] = {"email": reply_to}
    try:
        response = httpx.post(
            BREVO_API_URL,
            json=payload,
            headers={"api-key": settings.BREVO_API_KEY, "accept": "application/json"},
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        logger.warning(f"[mail] network error sending to {to_email}: {exc}")
        return False
    if response.status_code >= 400:
        logger.warning(f"[mail] Brevo answered {response.status_code}: {response.text}")
        return False
    return True

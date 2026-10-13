"""A new support ticket, or a user writing on one, emails ParkLink's support inbox -- once,
and without touching any app user's inbox."""
import pytest

from app.config import settings
from app.handlers.support_staff_alert import build_support_staff_email
from app.messaging import consumer as consumer_module
from app.messaging.events import SupportTicketStaffEvent
from app.models import Notification
from tests.conftest import TestingSessionLocal


@pytest.fixture
def emails(monkeypatch):
    sent: list = []
    monkeypatch.setattr(
        consumer_module.email, "send_email", lambda to, subject, html: sent.append((to, subject, html)) or True
    )
    return sent


def _event(event_id: str, event_type: str, **extra) -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "ticket_id": "ticket-1",
        "booking_id": "book-1",
        "ticket_subject": "No me devolvieron el pago",
        "author_user_id": "11111111-1111-1111-1111-111111111111",
        "author_role": "driver",
        "body": "Cancelé hace 3 días <y> no vi el reembolso",
        **extra,
    }


@pytest.mark.asyncio
async def test_new_ticket_emails_the_support_inbox(db, emails):
    await consumer_module._handle_support_staff_alert(
        _event("evt-1", "support.ticket_opened"), session_factory=TestingSessionLocal
    )

    assert len(emails) == 1
    to, subject, html = emails[0]
    assert to == settings.SUPPORT_INBOX_EMAIL == "contacto@parklink.com.ar"
    assert subject == "Nuevo ticket de soporte: No me devolvieron el pago"
    assert "abierto por un conductor" in html
    assert "&lt;y&gt;" in html, "the user's text is escaped"
    assert db.query(Notification).count() == 0, "no app user gets an inbox entry"


@pytest.mark.asyncio
async def test_user_message_emails_once_even_if_redelivered(db, emails):
    body = _event("evt-2", "support.ticket_user_message", author_role="owner")
    await consumer_module._handle_support_staff_alert(body, session_factory=TestingSessionLocal)
    await consumer_module._handle_support_staff_alert(body, session_factory=TestingSessionLocal)

    assert len(emails) == 1
    assert emails[0][1] == "Nueva respuesta en el ticket: No me devolvieron el pago"
    assert "Un propietario escribió" in emails[0][2]


def test_link_to_the_panel_only_when_configured(monkeypatch):
    event = SupportTicketStaffEvent.model_validate(_event("evt-3", "support.ticket_opened"))
    monkeypatch.setattr(settings, "ADMIN_PANEL_URL", "")
    assert "Abrir en el panel" not in build_support_staff_email(event)[1]
    monkeypatch.setattr(settings, "ADMIN_PANEL_URL", "https://admin.parklink.com.ar/")
    assert 'href="https://admin.parklink.com.ar/support/ticket-1"' in build_support_staff_email(event)[1]


def test_both_events_are_bound_and_dispatched():
    for key in ("support.ticket_opened", "support.ticket_user_message"):
        assert key in consumer_module.BINDING_KEYS
        assert consumer_module.HANDLERS[key] is consumer_module._handle_support_staff_alert

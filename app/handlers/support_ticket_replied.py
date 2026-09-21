from __future__ import annotations

from loguru import logger

from app.handlers.outbound import OutboundPush
from app.messaging.events import SupportTicketRepliedEvent
from app.services import templates


def build_support_ticket_replied_pushes(event: SupportTicketRepliedEvent) -> list[OutboundPush]:
    """Turns one `support.ticket_replied` event into a single push to the ticket's creator."""
    if not event.recipient_user_id:
        logger.warning(
            f"[support.ticket_replied] event {event.event_id} carries no recipient; nothing to send"
        )
        return []

    msg = templates.support_ticket_replied(event.ticket_subject, event.body)
    data = {"type": "support.ticket_replied", "ticketId": event.ticket_id, "bookingId": event.booking_id}
    return [OutboundPush(event.recipient_user_id, msg.title, msg.body, data)]

from __future__ import annotations

from loguru import logger

from app.handlers.outbound import OutboundPush
from app.messaging.events import BookingMessageSentEvent
from app.services import templates


def build_booking_message_sent_pushes(event: BookingMessageSentEvent) -> list[OutboundPush]:
    """Turns one `booking.message_sent` event into a single push to whichever side of
    the booking did NOT send it."""
    if not event.recipient_user_id:
        logger.warning(
            f"[booking.message_sent] event {event.event_id} carries no recipient; nothing to send"
        )
        return []
    if event.recipient_user_id == event.sender_user_id:
        logger.info(
            f"[booking.message_sent] sender and recipient are the same user for booking "
            f"{event.booking_id}; skipping"
        )
        return []

    title = event.parking_spot_title or templates.DEFAULT_TITLE
    msg = templates.booking_message_received(title, event.body)
    data = {"type": "booking.message_sent", "bookingId": event.booking_id}
    return [OutboundPush(event.recipient_user_id, msg.title, msg.body, data)]

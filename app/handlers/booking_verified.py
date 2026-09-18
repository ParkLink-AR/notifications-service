from __future__ import annotations

from app.handlers.outbound import OutboundPush
from app.messaging.events import BookingVerifiedEvent
from app.services import templates


def build_booking_verified_pushes(event: BookingVerifiedEvent) -> list[OutboundPush]:
    """Turns one `booking.verified` event into the notifications to send.

    Only the driver is notified -- the owner is the one who just entered the code,
    so a push to them would be redundant (same reasoning as the auto-confirmed
    branch of booking.confirmed)."""
    title = event.parking_spot_title or templates.DEFAULT_TITLE
    data = {"type": "booking.verified", "bookingId": event.booking_id}

    msg = templates.booking_verified_for_driver(title)
    return [OutboundPush(event.driver_user_id, msg.title, msg.body, data)]

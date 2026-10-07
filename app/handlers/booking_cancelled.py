from __future__ import annotations

from app.handlers.outbound import OutboundPush
from app.messaging.events import BookingCancelledEvent
from app.services import templates

CANCELLED_BY_OWNER_ACCOUNT = "owner_account"
CANCELLED_BY_DRIVER_ACCOUNT = "driver_account"


def build_booking_cancelled_pushes(event: BookingCancelledEvent) -> list[OutboundPush]:
    """Turns one `booking.cancelled` event into the notifications to send.

    Only the side whose account is still around is told: the driver when the owner's
    account was closed (they also get the money back), the owner when the driver's was."""
    title = event.parking_spot_title or templates.DEFAULT_TITLE
    data = {"type": "booking.cancelled", "bookingId": event.booking_id}

    if event.cancelled_by == CANCELLED_BY_OWNER_ACCOUNT:
        message = templates.booking_cancelled_by_owner_account_for_driver(title, event.start, event.end)
        return [OutboundPush(event.driver_user_id, message.title, message.body, data)]
    if event.cancelled_by == CANCELLED_BY_DRIVER_ACCOUNT and event.owner_user_id:
        message = templates.booking_cancelled_by_driver_account_for_owner(title, event.start, event.end)
        return [OutboundPush(event.owner_user_id, message.title, message.body, data)]
    return []

from __future__ import annotations

from app.handlers.outbound import OutboundPush
from app.handlers.payloads import booking_payload
from app.messaging.events import BookingCancelledEvent
from app.services import templates

CANCELLED_BY_OWNER_REJECTED = "owner_rejected"
CANCELLED_BY_OWNER_EXPIRED = "owner_expired"
CANCELLED_BY_DRIVER = "driver"
CANCELLED_BY_OWNER_ACCOUNT = "owner_account"
CANCELLED_BY_DRIVER_ACCOUNT = "driver_account"


def build_booking_cancelled_pushes(event: BookingCancelledEvent) -> list[OutboundPush]:
    """Turns one `booking.cancelled` event into the notifications to send.

    Only the side that didn't call it off is told: the driver when the owner rejected the
    request, never answered it, or the owner's account was closed (they also get the money
    back); the owner when the driver cancelled or the driver's account was closed."""
    title = event.parking_spot_title or templates.DEFAULT_TITLE
    data = {"type": "booking.cancelled", "bookingId": event.booking_id}
    payload = booking_payload(event)

    def to_driver(kind: str, message: templates.PushMessage) -> list[OutboundPush]:
        return [
            OutboundPush(
                event.driver_user_id, message.title, message.body, data,
                kind=kind, role="driver", payload=payload,
            )
        ]

    def to_owner(kind: str, message: templates.PushMessage) -> list[OutboundPush]:
        if not event.owner_user_id:
            return []
        return [
            OutboundPush(
                event.owner_user_id, message.title, message.body, data,
                kind=kind, role="owner", payload=payload,
            )
        ]

    if event.cancelled_by == CANCELLED_BY_OWNER_REJECTED:
        return to_driver("driver_rejected", templates.booking_rejected_for_driver(title, event.start, event.end))
    if event.cancelled_by == CANCELLED_BY_OWNER_EXPIRED:
        return to_driver(
            "driver_request_expired", templates.booking_request_expired_for_driver(title, event.start, event.end)
        )
    if event.cancelled_by == CANCELLED_BY_OWNER_ACCOUNT:
        return to_driver(
            "driver_spot_unavailable",
            templates.booking_cancelled_by_owner_account_for_driver(title, event.start, event.end),
        )
    if event.cancelled_by == CANCELLED_BY_DRIVER:
        return to_owner(
            "owner_booking_cancelled", templates.booking_cancelled_by_driver_for_owner(title, event.start, event.end)
        )
    if event.cancelled_by == CANCELLED_BY_DRIVER_ACCOUNT:
        return to_owner(
            "owner_booking_cancelled",
            templates.booking_cancelled_by_driver_account_for_owner(title, event.start, event.end),
        )
    return []

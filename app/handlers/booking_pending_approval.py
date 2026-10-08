from __future__ import annotations

from loguru import logger

from app.handlers.outbound import OutboundPush
from app.handlers.payloads import booking_payload
from app.messaging.events import BookingPendingApprovalEvent
from app.services import templates


def build_booking_pending_approval_pushes(
    event: BookingPendingApprovalEvent,
) -> list[OutboundPush]:
    """Turns one `booking.pending_approval` event into a single push to the owner:
    a paid booking is waiting for them to accept or reject it."""
    if not event.owner_user_id:
        logger.warning(
            f"[booking.pending_approval] event {event.event_id} carries no owner; nothing to send"
        )
        return []
    if event.owner_user_id == event.driver_user_id:
        logger.info(
            f"[booking.pending_approval] owner is the driver for booking {event.booking_id}; skipping"
        )
        return []

    title = event.parking_spot_title or templates.DEFAULT_TITLE
    msg = templates.booking_pending_approval_for_owner(
        title, event.start, event.end, event.owner_response_deadline
    )
    data = {"type": "booking.pending_approval", "bookingId": event.booking_id}
    payload = booking_payload(event)
    payload["owner_response_deadline"] = (
        event.owner_response_deadline.isoformat() if event.owner_response_deadline else None
    )
    return [
        OutboundPush(
            event.owner_user_id, msg.title, msg.body, data,
            kind="owner_request", role="owner", payload=payload,
        )
    ]

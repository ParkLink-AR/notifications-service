from __future__ import annotations

from app.handlers.outbound import OutboundPush
from app.handlers.payloads import booking_payload
from app.messaging.events import BookingCompletedEvent
from app.services import templates


def build_booking_completed_pushes(event: BookingCompletedEvent) -> list[OutboundPush]:
    """Turns one `booking.completed` event into a review request for each side: the driver
    reviews the spot and its owner, the owner reviews the driver."""
    title = event.parking_spot_title or templates.DEFAULT_TITLE
    payload = booking_payload(event)

    driver_msg = templates.booking_completed_for_driver(title)
    pushes = [
        OutboundPush(
            event.driver_user_id, driver_msg.title, driver_msg.body,
            {"type": "booking.completed", "bookingId": event.booking_id, "role": "driver"},
            kind="driver_review_prompt", role="driver", payload=payload,
        )
    ]
    if event.owner_user_id and event.owner_user_id != event.driver_user_id:
        owner_msg = templates.booking_completed_for_owner(title)
        pushes.append(
            OutboundPush(
                event.owner_user_id, owner_msg.title, owner_msg.body,
                {"type": "booking.completed", "bookingId": event.booking_id, "role": "owner"},
                kind="owner_review_prompt", role="owner",
                payload={**payload, "driver_user_id": event.driver_user_id},
            )
        )
    return pushes

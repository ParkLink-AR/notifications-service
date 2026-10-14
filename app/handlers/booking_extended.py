from __future__ import annotations

from app.handlers.outbound import OutboundPush
from app.handlers.payloads import booking_payload
from app.messaging.events import BookingExtendedEvent
from app.services import templates


def build_booking_extended_pushes(event: BookingExtendedEvent) -> list[OutboundPush]:
    """`booking.extended`: the driver gets the confirmation, the owner learns until when the
    car stays. Both open the extension, which links back to the booking it continues."""
    title = event.parking_spot_title or templates.DEFAULT_TITLE
    data = {"type": "booking.extended", "bookingId": event.booking_id}
    payload = {**booking_payload(event), "parent_booking_id": event.parent_booking_id}
    to_driver = templates.booking_extended_for_driver(title, event.end)
    pushes = [
        OutboundPush(
            event.driver_user_id, to_driver.title, to_driver.body, data,
            kind="driver_booking_extended", role="driver", payload=payload,
        )
    ]
    if event.owner_user_id:
        to_owner = templates.booking_extended_for_owner(title, event.end)
        pushes.append(
            OutboundPush(
                event.owner_user_id, to_owner.title, to_owner.body, data,
                kind="owner_booking_extended", role="owner", payload=payload,
            )
        )
    return pushes

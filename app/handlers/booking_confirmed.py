from __future__ import annotations

from app.handlers.outbound import OutboundPush
from app.handlers.payloads import booking_payload
from app.messaging.events import BookingConfirmedEvent
from app.services import templates


def build_booking_confirmed_pushes(event: BookingConfirmedEvent) -> list[OutboundPush]:
    """Turns one `booking.confirmed` event into the notifications to send.

    Only the driver is notified ("tu reserva fue confirmada") -- the owner is the
    one who just tapped "aceptar", so a push to them would be redundant."""
    title = event.parking_spot_title or templates.DEFAULT_TITLE
    data = {"type": "booking.confirmed", "bookingId": event.booking_id}

    driver_msg = templates.booking_confirmed_for_driver(title, event.start, event.end)
    return [
        OutboundPush(
            event.driver_user_id, driver_msg.title, driver_msg.body, data,
            kind="driver_confirmed", role="driver", payload=booking_payload(event),
        )
    ]

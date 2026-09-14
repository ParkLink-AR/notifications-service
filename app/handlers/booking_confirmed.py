from __future__ import annotations

from loguru import logger

from app.handlers.outbound import OutboundPush
from app.messaging.events import BookingConfirmedEvent
from app.services import templates


def build_booking_confirmed_pushes(event: BookingConfirmedEvent) -> list[OutboundPush]:
    """Turns one `booking.confirmed` event into the notifications to send.

    The driver is always notified ("tu reserva fue confirmada"). The owner is
    notified only when the booking auto-confirmed on an instant-booking spot
    (`auto_confirmed`): in the normal flow the owner is the one who just tapped
    "aceptar", so a push to them would be redundant."""
    title = event.parking_spot_title or templates.DEFAULT_TITLE
    data = {"type": "booking.confirmed", "bookingId": event.booking_id}

    driver_msg = templates.booking_confirmed_for_driver(title, event.start, event.end)
    pushes = [OutboundPush(event.driver_user_id, driver_msg.title, driver_msg.body, data)]

    if event.auto_confirmed and event.owner_user_id and event.owner_user_id != event.driver_user_id:
        owner_msg = templates.booking_confirmed_for_owner(title, event.start, event.end)
        pushes.append(OutboundPush(event.owner_user_id, owner_msg.title, owner_msg.body, data))
    else:
        logger.info(f"[booking.confirmed] no owner push for booking {event.booking_id}")

    return pushes

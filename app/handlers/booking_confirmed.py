from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from app.messaging.events import BookingConfirmedEvent
from app.services import templates
from app.services.recipients import resolve_spot


@dataclass(frozen=True)
class OutboundPush:
    user_id: str
    title: str
    body: str
    data: dict[str, str]


async def build_booking_confirmed_pushes(event: BookingConfirmedEvent) -> list[OutboundPush]:
    """Turns one booking.confirmed event into the notifications to send: one to
    the driver, and (when there is a distinct owner) one to the owner."""
    spot = await resolve_spot(event.parking_spot_id)
    data = {"type": "booking.confirmed", "bookingId": event.booking_id}

    driver_msg = templates.booking_confirmed_for_driver(spot.title, event.start, event.end)
    pushes = [OutboundPush(event.driver_user_id, driver_msg.title, driver_msg.body, data)]

    if spot.owner_id and spot.owner_id != event.driver_user_id:
        owner_msg = templates.booking_confirmed_for_owner(spot.title, event.start, event.end)
        pushes.append(OutboundPush(spot.owner_id, owner_msg.title, owner_msg.body, data))
    else:
        logger.info(
            f"[booking.confirmed] no distinct owner to notify for spot {event.parking_spot_id}"
        )

    return pushes

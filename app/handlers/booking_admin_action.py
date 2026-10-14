from __future__ import annotations

from loguru import logger

from app.handlers.outbound import OutboundPush
from app.messaging.events import BookingAdminActionEvent
from app.services import templates


def build_booking_admin_action_pushes(event: BookingAdminActionEvent) -> list[OutboundPush]:
    """ParkLink cancelled or refunded a booking from the admin panel: both sides are told
    (the driver, with what goes back to them; the owner, that the slot is free or that
    their payout for it shrinks)."""
    title = event.parking_spot_title
    data = {"type": "booking.admin_action", "bookingId": event.booking_id, "action": event.action}
    payload = {
        "booking_id": event.booking_id,
        "parking_spot_id": event.parking_spot_id,
        "spot_title": title,
        "start": event.start.isoformat(),
        "end": event.end.isoformat(),
        "refunded_amount": event.refunded_amount,
    }
    if event.action == "cancelled":
        to_driver = templates.booking_admin_cancelled_for_driver(title, event.start, event.end, event.refunded_amount)
        to_owner = templates.booking_admin_cancelled_for_owner(title, event.start, event.end)
        kinds = ("driver_admin_cancelled", "owner_admin_cancelled")
    elif event.action == "refunded":
        to_driver = templates.booking_admin_refunded_for_driver(title, event.refunded_amount)
        to_owner = templates.booking_admin_refunded_for_owner(title, event.refunded_amount)
        kinds = ("driver_admin_refund", "owner_admin_refund")
    else:
        logger.warning(f"[booking.admin_action] event {event.event_id} has unknown action '{event.action}'")
        return []

    pushes = [
        OutboundPush(event.driver_user_id, to_driver.title, to_driver.body, {**data, "role": "driver"},
                     kind=kinds[0], role="driver", payload=payload),
    ]
    if event.owner_user_id:
        pushes.append(
            OutboundPush(event.owner_user_id, to_owner.title, to_owner.body, {**data, "role": "owner"},
                         kind=kinds[1], role="owner", payload=payload)
        )
    return pushes

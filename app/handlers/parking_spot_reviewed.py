from __future__ import annotations

from loguru import logger

from app.handlers.outbound import OutboundPush
from app.messaging.events import ParkingSpotReviewedEvent
from app.services import templates


def build_parking_spot_reviewed_pushes(event: ParkingSpotReviewedEvent) -> list[OutboundPush]:
    """Turns one `parking_spot.reviewed` event into a push (and inbox entry) to the spot's
    owner: approved (it's published) or rejected (with the admin's reason)."""
    if event.decision == "approved":
        msg = templates.parking_spot_approved(event.parking_spot_title)
        kind = "owner_spot_approved"
    elif event.decision == "rejected":
        msg = templates.parking_spot_rejected(event.parking_spot_title, event.notes)
        kind = "owner_spot_rejected"
    else:
        logger.warning(f"[parking_spot.reviewed] event {event.event_id} has unknown decision '{event.decision}'")
        return []

    data = {"type": "parking_spot.reviewed", "parkingSpotId": event.parking_spot_id, "decision": event.decision}
    payload = {
        "parking_spot_id": event.parking_spot_id,
        "spot_title": event.parking_spot_title,
        "decision": event.decision,
        "notes": event.notes or "",
    }
    return [OutboundPush(event.owner_user_id, msg.title, msg.body, data, kind=kind, role="owner", payload=payload)]

from __future__ import annotations

from loguru import logger

from app.handlers.outbound import OutboundPush
from app.messaging.events import PayoutPaidEvent
from app.services import templates


def build_payout_paid_pushes(event: PayoutPaidEvent) -> list[OutboundPush]:
    """Turns one `payout.paid` event into a single push to the payout's recipient."""
    if not event.recipient_user_id:
        logger.warning(
            f"[payout.paid] event {event.event_id} carries no recipient; nothing to send"
        )
        return []

    msg = templates.payout_paid(event.parking_spot_title, event.net_amount)
    data = {"type": "payout.paid", "payoutId": event.payout_id, "bookingId": event.booking_id}
    return [OutboundPush(event.recipient_user_id, msg.title, msg.body, data)]

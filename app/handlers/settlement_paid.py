from __future__ import annotations

from loguru import logger

from app.handlers.outbound import OutboundPush
from app.messaging.events import SettlementPaidEvent
from app.services import templates


def build_settlement_paid_pushes(event: SettlementPaidEvent) -> list[OutboundPush]:
    """Turns one `settlement.paid` event into a single push to the settlement's recipient."""
    if not event.recipient_user_id:
        logger.warning(
            f"[settlement.paid] event {event.event_id} carries no recipient; nothing to send"
        )
        return []

    msg = templates.settlement_paid(event.net_amount, event.booking_count)
    data = {"type": "settlement.paid", "settlementId": event.settlement_id}
    return [OutboundPush(event.recipient_user_id, msg.title, msg.body, data)]

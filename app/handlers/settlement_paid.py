from __future__ import annotations

from loguru import logger

from app.handlers.outbound import OutboundPush
from app.messaging.events import SettlementDraftedEvent, SettlementPaidEvent
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
    payload = {
        "settlement_id": event.settlement_id,
        "net_amount": event.net_amount,
        "booking_count": event.booking_count,
    }
    return [
        OutboundPush(
            event.recipient_user_id, msg.title, msg.body, data,
            kind="owner_settlement_paid", role="owner", payload=payload,
        )
    ]


def build_settlement_drafted_pushes(event: SettlementDraftedEvent) -> list[OutboundPush]:
    """Turns one `settlement.drafted` event into a push to the owner: their settlement is
    being prepared, the transfer comes next."""
    if not event.recipient_user_id:
        logger.warning(f"[settlement.drafted] event {event.event_id} carries no recipient; nothing to send")
        return []
    msg = templates.settlement_drafted(event.net_amount, event.booking_count)
    payload = {
        "settlement_id": event.settlement_id,
        "net_amount": event.net_amount,
        "booking_count": event.booking_count,
    }
    return [
        OutboundPush(
            event.recipient_user_id, msg.title, msg.body,
            {"type": "settlement.drafted", "settlementId": event.settlement_id},
            kind="owner_settlement_drafted", role="owner", payload=payload,
        )
    ]

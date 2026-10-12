from __future__ import annotations

from app.handlers.outbound import OutboundPush
from app.handlers.payloads import preview
from app.messaging.events import (
    RefundCompletedEvent,
    ReviewReceivedEvent,
    SupportTicketClosedEvent,
)
from app.services import templates


def build_review_received_pushes(event: ReviewReceivedEvent) -> list[OutboundPush]:
    """Someone reviewed the recipient (as an owner or as a driver)."""
    if not event.recipient_user_id or event.recipient_user_id == event.reviewer_user_id:
        return []
    msg = templates.review_received(event.parking_spot_title, event.rating, event.recipient_role)
    role = event.recipient_role or None
    payload = {
        "booking_id": event.booking_id,
        "parking_spot_id": event.parking_spot_id,
        "spot_title": event.parking_spot_title,
        "rating": event.rating,
    }
    return [OutboundPush(
        event.recipient_user_id, msg.title, msg.body,
        {"type": "review.received", "bookingId": event.booking_id, "role": event.recipient_role},
        kind="review_received", role=role, payload=payload,
    )]


def build_support_ticket_closed_pushes(event: SupportTicketClosedEvent) -> list[OutboundPush]:
    """ParkLink staff closed the recipient's support ticket."""
    if not event.recipient_user_id:
        return []
    msg = templates.support_ticket_closed(event.ticket_subject)
    payload = {"ticket_id": event.ticket_id, "booking_id": event.booking_id, "subject": preview(event.ticket_subject)}
    return [OutboundPush(
        event.recipient_user_id, msg.title, msg.body,
        {"type": "support.ticket_closed", "ticketId": event.ticket_id, "bookingId": event.booking_id},
        kind="ticket_closed", role=event.recipient_role or None, payload=payload,
    )]


def build_refund_completed_pushes(event: RefundCompletedEvent) -> list[OutboundPush]:
    """A refund that had failed finally reached the driver."""
    msg = templates.refund_completed(event.amount, event.method)
    payload = {
        "booking_id": event.booking_id,
        "parking_spot_id": event.parking_spot_id or "",
        "amount": event.amount,
        "method": event.method,
    }
    return [OutboundPush(
        event.driver_user_id, msg.title, msg.body,
        {"type": "refund.completed", "bookingId": event.booking_id},
        kind="driver_refund_completed", role="driver", payload=payload,
    )]

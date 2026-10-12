from __future__ import annotations

from app.handlers.outbound import OutboundPush
from app.handlers.payloads import booking_payload
from app.messaging.events import (
    BookingApprovalReminderEvent,
    BookingEndingSoonEvent,
    BookingStartingSoonEvent,
    BookingVerificationReviewedEvent,
)
from app.services import templates


def build_booking_verification_reviewed_pushes(event: BookingVerificationReviewedEvent) -> list[OutboundPush]:
    """An admin decided on a booking that ended without its arrival code verified: the owner
    is told whether they get paid for it; the driver, when they were refunded."""
    title = event.parking_spot_title or templates.DEFAULT_TITLE
    payload = booking_payload(event)
    pushes: list[OutboundPush] = []
    refunded = event.decision == "refunded"
    if event.owner_user_id:
        msg = templates.payout_denied_for_owner(title) if refunded else templates.payout_approved_for_owner(title)
        pushes.append(OutboundPush(
            event.owner_user_id, msg.title, msg.body,
            {"type": "booking.verification_reviewed", "bookingId": event.booking_id, "role": "owner"},
            kind="owner_payout_denied" if refunded else "owner_payout_approved", role="owner", payload=payload,
        ))
    if refunded:
        msg = templates.unverified_refunded_for_driver(title)
        pushes.append(OutboundPush(
            event.driver_user_id, msg.title, msg.body,
            {"type": "booking.verification_reviewed", "bookingId": event.booking_id, "role": "driver"},
            kind="driver_unverified_refunded", role="driver", payload=payload,
        ))
    return pushes


def build_booking_approval_reminder_pushes(event: BookingApprovalReminderEvent) -> list[OutboundPush]:
    """A booking request is about to expire unanswered: one more nudge to the owner."""
    if not event.owner_user_id:
        return []
    title = event.parking_spot_title or templates.DEFAULT_TITLE
    msg = templates.booking_request_reminder_for_owner(title, event.owner_response_deadline)
    payload = booking_payload(event)
    payload["owner_response_deadline"] = (
        event.owner_response_deadline.isoformat() if event.owner_response_deadline else None
    )
    return [OutboundPush(
        event.owner_user_id, msg.title, msg.body,
        {"type": "booking.approval_reminder", "bookingId": event.booking_id},
        kind="owner_request_reminder", role="owner", payload=payload,
    )]


def build_booking_starting_soon_pushes(event: BookingStartingSoonEvent) -> list[OutboundPush]:
    """A booking starts within the hour: the driver, to be on their way with their code;
    the owner, that someone's arriving."""
    title = event.parking_spot_title or templates.DEFAULT_TITLE
    payload = booking_payload(event)
    driver_msg = templates.booking_starting_soon_for_driver(title, event.start)
    pushes = [OutboundPush(
        event.driver_user_id, driver_msg.title, driver_msg.body,
        {"type": "booking.starting_soon", "bookingId": event.booking_id, "role": "driver"},
        kind="driver_starting_soon", role="driver", payload=payload,
    )]
    if event.owner_user_id and event.owner_user_id != event.driver_user_id:
        owner_msg = templates.booking_starting_soon_for_owner(title, event.start)
        pushes.append(OutboundPush(
            event.owner_user_id, owner_msg.title, owner_msg.body,
            {"type": "booking.starting_soon", "bookingId": event.booking_id, "role": "owner"},
            kind="owner_starting_soon", role="owner", payload=payload,
        ))
    return pushes


def build_booking_ending_soon_pushes(event: BookingEndingSoonEvent) -> list[OutboundPush]:
    """A stay ends within the hour: the driver, to pick up their vehicle."""
    title = event.parking_spot_title or templates.DEFAULT_TITLE
    msg = templates.stay_ending_for_driver(title, event.end)
    return [OutboundPush(
        event.driver_user_id, msg.title, msg.body,
        {"type": "booking.ending_soon", "bookingId": event.booking_id},
        kind="driver_stay_ending", role="driver", payload=booking_payload(event),
    )]

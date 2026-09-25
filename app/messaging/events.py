from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _BookingEvent(BaseModel):
    """Shared shape of every `booking.*` domain event published by booking-service
    on the RabbitMQ topic exchange `parklink.events`.

    The events are self-contained: booking-service embeds the spot title and both
    party ids (it already fetches the spot in these flows), so notifications-service
    does not call any other service to build a push. `parking_spot_title` may be an
    empty string if booking-service could not resolve it -- templates fall back to a
    generic label."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    event_type: str
    occurred_at: datetime | None = None
    booking_id: str
    parking_spot_id: str
    parking_spot_title: str = ""
    owner_user_id: str | None = None
    driver_user_id: str
    start: datetime
    end: datetime
    amount: int | None = None
    payment_id: str | None = None


class BookingConfirmedEvent(_BookingEvent):
    """`booking.confirmed` -- the owner approved a PENDING_OWNER_APPROVAL booking."""

    event_type: str = "booking.confirmed"


class BookingPendingApprovalEvent(_BookingEvent):
    """`booking.pending_approval` -- the driver paid and the booking is now
    PENDING_OWNER_APPROVAL, waiting for the owner to accept or reject it before
    `owner_response_deadline` (after which booking-service auto-cancels + refunds)."""

    event_type: str = "booking.pending_approval"
    owner_response_deadline: datetime | None = None


class BookingVerifiedEvent(_BookingEvent):
    """`booking.verified` -- the owner entered the driver's in-person verification
    code correctly and the booking moved from CONFIRMED to IN_PROGRESS. No extra
    fields beyond the shared base: the driver just needs to know their arrival was
    confirmed."""

    event_type: str = "booking.verified"


class BookingMessageSentEvent(BaseModel):
    """`booking.message_sent` -- either side of a booking (driver or owner) sent the
    other a message. Deliberately not a `_BookingEvent` subclass: a chat message has
    no time_range/amount/payment_id, and its "who gets notified" field is whichever
    party did NOT send it, not always the driver."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    event_type: str = "booking.message_sent"
    occurred_at: datetime | None = None
    booking_id: str
    parking_spot_id: str
    parking_spot_title: str = ""
    sender_user_id: str
    recipient_user_id: str
    body: str


class SupportTicketRepliedEvent(BaseModel):
    """`support.ticket_replied` -- ParkLink staff replied to a support ticket from
    admin-dashboard. Only fired for staff replies: a user replying to their own ticket
    has no one to push to (staff work off admin-dashboard, not notifications)."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    event_type: str = "support.ticket_replied"
    occurred_at: datetime | None = None
    ticket_id: str
    booking_id: str
    ticket_subject: str = ""
    recipient_user_id: str
    body: str


class PayoutPaidEvent(BaseModel):
    """`payout.paid` -- ParkLink staff manually marked an owner's payout as
    transferred from admin-dashboard. Self-contained like every other event:
    booking-service embeds the spot title and the amount, so no follow-up lookup
    is needed to build the push."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    event_type: str = "payout.paid"
    occurred_at: datetime | None = None
    payout_id: str
    booking_id: str
    recipient_user_id: str
    net_amount: int
    parking_spot_title: str = ""

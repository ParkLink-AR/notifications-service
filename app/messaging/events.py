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


class BookingCancelledEvent(_BookingEvent):
    """`booking.cancelled` -- a paid booking that hadn't started was cancelled, with a full
    refund to the driver. `cancelled_by` says who or what called it off: "owner_rejected"
    (the owner rejected the request), "owner_expired" (the owner never answered it in
    time), "driver" (the driver cancelled it), or "owner_account" / "driver_account" (that
    side's account was closed or suspended)."""

    event_type: str = "booking.cancelled"
    cancelled_by: str


class BookingCompletedEvent(_BookingEvent):
    """`booking.completed` -- the stay's time window is over: both sides are asked to
    review each other. `owner_user_id` is missing when booking-service couldn't look up
    the spot -- then only the driver is asked."""

    event_type: str = "booking.completed"


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
    # "driver" | "owner": which side of the booking the recipient is on. Empty from an
    # older booking-service.
    recipient_role: str = ""
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
    # "driver" | "owner": which side of the ticket's booking opened it. Empty when
    # booking-service couldn't tell.
    recipient_role: str = ""
    body: str


class SettlementPaidEvent(BaseModel):
    """`settlement.paid` -- an admin confirmed a settlement's bank transfer from
    admin-dashboard. A settlement freezes an owner's entire pending balance across
    potentially several bookings and pays it out in one transfer, replacing the old
    per-booking `payout.paid` event. Self-contained like every other event:
    booking-service embeds the total amount and how many bookings it covers, so no
    follow-up lookup is needed to build the push. There is no single
    `parking_spot_title` here since a settlement can span multiple different spots."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    event_type: str = "settlement.paid"
    occurred_at: datetime | None = None
    settlement_id: str
    recipient_user_id: str
    net_amount: int
    booking_count: int


class ParkingSpotReviewedEvent(BaseModel):
    """`parking_spot.reviewed` -- published by parking-service when a ParkLink admin
    approves or rejects a new parking spot (it stays hidden from searches until approved).
    `decision` is "approved" or "rejected"; `notes` is the admin's reason, if any (always
    shown to the owner on a rejection)."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    event_type: str = "parking_spot.reviewed"
    occurred_at: datetime | None = None
    parking_spot_id: str
    parking_spot_title: str = ""
    owner_user_id: str
    decision: str
    notes: str | None = None


class BookingVerificationReviewedEvent(_BookingEvent):
    """`booking.verification_reviewed` -- an admin decided on a booking that completed
    without its arrival code verified: `decision` "approved" (the owner gets paid for it) or
    "refunded" (the driver got their money back and the owner isn't paid)."""

    event_type: str = "booking.verification_reviewed"
    decision: str


class BookingApprovalReminderEvent(_BookingEvent):
    """`booking.approval_reminder` -- a booking request is about to expire unanswered."""

    event_type: str = "booking.approval_reminder"
    owner_response_deadline: datetime | None = None


class BookingStartingSoonEvent(_BookingEvent):
    """`booking.starting_soon` -- a confirmed booking starts within the hour."""

    event_type: str = "booking.starting_soon"


class BookingEndingSoonEvent(_BookingEvent):
    """`booking.ending_soon` -- a stay under way ends within the hour."""

    event_type: str = "booking.ending_soon"


class ReviewReceivedEvent(BaseModel):
    """`review.received` -- one side of a booking reviewed the other (the owner or the
    driver). `recipient_role` is the reviewed person's side."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    event_type: str = "review.received"
    occurred_at: datetime | None = None
    booking_id: str
    parking_spot_id: str = ""
    parking_spot_title: str = ""
    reviewer_user_id: str = ""
    recipient_user_id: str
    recipient_role: str = ""
    rating: int


class SupportTicketClosedEvent(BaseModel):
    """`support.ticket_closed` -- ParkLink staff marked a support ticket RESOLVED or CLOSED."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    event_type: str = "support.ticket_closed"
    occurred_at: datetime | None = None
    ticket_id: str
    booking_id: str = ""
    ticket_subject: str = ""
    recipient_user_id: str
    recipient_role: str = ""
    status: str = ""


class RefundCompletedEvent(BaseModel):
    """`refund.completed` -- published by payment-service when a refund that had failed
    finally reached the driver: Mercado Pago accepted a retry (`method` "mercadopago") or an
    admin returned the money some other way ("manual"). `amount` is in centavos."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    event_type: str = "refund.completed"
    occurred_at: datetime | None = None
    booking_id: str
    parking_spot_id: str | None = None
    driver_user_id: str
    amount: int
    method: str = "mercadopago"


class SettlementDraftedEvent(SettlementPaidEvent):
    """`settlement.drafted` -- an admin prepared a settlement: the owner's pending balance is
    frozen into it and the bank transfer comes next (announced by `settlement.paid`)."""

    event_type: str = "settlement.drafted"


class SupportTicketStaffEvent(BaseModel):
    """`support.ticket_opened` / `support.ticket_user_message` -- a user opened a support
    ticket, or wrote on one: ParkLink staff get an email at the support inbox."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    event_type: str
    occurred_at: datetime | None = None
    ticket_id: str
    booking_id: str = ""
    ticket_subject: str = ""
    author_user_id: str = ""
    # "driver" or "owner"; empty when booking-service couldn't tell.
    author_role: str = ""
    body: str = ""

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

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BookingConfirmedEvent(BaseModel):
    """`booking.confirmed`, published by booking-service on the RabbitMQ topic
    exchange `parklink.events` when a PENDING_PAYMENT booking transitions to
    CONFIRMED. `owner_user_id` and the spot title are NOT in the event --
    booking-service doesn't have them; notifications-service resolves them from
    parking-service (see app/services/recipients.py)."""

    model_config = ConfigDict(extra="ignore")

    event_id: str
    event_type: str = "booking.confirmed"
    occurred_at: datetime | None = None
    booking_id: str
    parking_spot_id: str
    driver_user_id: str
    start: datetime
    end: datetime
    amount: int | None = None
    payment_id: str | None = None

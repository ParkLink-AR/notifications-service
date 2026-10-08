import uuid

from sqlalchemy import JSON, Column, DateTime, Index, String, Text
from sqlalchemy.sql import func

from ..database import Base
from .guid import GUID


class Notification(Base):
    """One row per notification a user can see in the app's notifications tab -- the
    source of truth for that list and its unread badge. Written by the event consumer
    when a domain event concerns the user (the push is just a heads-up about it).

    `kind` says what happened (driver_confirmed, owner_request...) and `data` carries what
    the app needs to render and open it (spot title, booking times, ids...) -- the app
    renders the text itself, in the user's language. `title`/`body` are the Spanish push
    texts, kept as a fallback."""

    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(GUID(), nullable=False)
    # Which side of the booking the notification is for: "driver" | "owner", or NULL for
    # one that isn't about either side.
    role = Column(String(8), nullable=True)
    kind = Column(String(40), nullable=False)
    booking_id = Column(String(64), nullable=True, index=True)
    data = Column(JSON, nullable=False, default=dict)
    title = Column(String(255), nullable=False, default="")
    body = Column(Text, nullable=False, default="")
    event_id = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    # For a booking request (owner_request): when it stopped waiting for an answer -- the
    # owner accepted or rejected it, it expired, or it was cancelled. The app only offers
    # accept/reject while this is NULL.
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_notifications_user_created", "user_id", "created_at"),)

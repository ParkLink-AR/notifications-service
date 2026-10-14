import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from ..database import Base


class Broadcast(Base):
    """An announcement ParkLink staff sent from the admin panel to every user in an
    audience (all, drivers, owners) -- each one got it as a notification in the app and a
    push. Kept as the panel's history of what was sent."""

    __tablename__ = "broadcasts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(120), nullable=False)
    body = Column(Text, nullable=False)
    # "all" | "drivers" | "owners"
    audience = Column(String(16), nullable=False)
    recipients = Column(Integer, nullable=False, default=0)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func

from ..database import Base


class ProcessedEvent(Base):
    """One row per successfully-handled event. RabbitMQ delivers at-least-once,
    so the consumer checks this table before acting and skips duplicates."""

    __tablename__ = "processed_events"

    event_id = Column(String(128), primary_key=True)
    event_type = Column(String(64), nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

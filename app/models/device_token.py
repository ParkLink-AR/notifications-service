from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func

from ..database import Base
from .guid import GUID


class DeviceToken(Base):
    """One row per (app install, device). The FCM registration token is its
    identity -- React Native Firebase returns the same token shape on Android
    and iOS, so a single table covers both. A user can have several rows
    (phone + tablet + reinstall)."""

    __tablename__ = "device_tokens"

    token = Column(String(4096), primary_key=True)
    user_id = Column(GUID(), nullable=False, index=True)
    platform = Column(String(16), nullable=False)  # "android" | "ios"
    # Optional: same value as auth-service's refresh_tokens.device_id, so a
    # device can be correlated across the two services if ever needed.
    device_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

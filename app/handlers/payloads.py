from __future__ import annotations

from app.messaging.events import _BookingEvent

# Longest message/reply preview kept on an inbox entry -- same cut as the push preview.
PREVIEW_MAX_LEN = 120


def booking_payload(event: _BookingEvent) -> dict:
    """What every booking notification in the inbox carries: enough for the app to show
    the spot and the booking's dates, and to open the booking."""
    return {
        "booking_id": event.booking_id,
        "parking_spot_id": event.parking_spot_id,
        "spot_title": event.parking_spot_title,
        "start": event.start.isoformat(),
        "end": event.end.isoformat(),
        "amount": event.amount,
    }


def preview(text: str) -> str:
    return text if len(text) <= PREVIEW_MAX_LEN else text[: PREVIEW_MAX_LEN - 1] + "…"

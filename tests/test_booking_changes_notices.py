"""What each side hears when a booking changes after it was made: the owner calling off one
they had accepted, the driver cancelling in its last hour, and an extension."""
from datetime import UTC, datetime

import pytest

from app.messaging import consumer as consumer_module
from app.models import Notification
from tests.conftest import TestingSessionLocal

DRIVER = "11111111-1111-1111-1111-111111111111"
OWNER = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def sent(monkeypatch):
    pushes: list = []
    monkeypatch.setattr(consumer_module.push, "send_pushes", lambda _db, batch: pushes.extend(batch) or len(batch))

    async def no_announce(_users):
        return None

    monkeypatch.setattr(consumer_module.live, "announce", no_announce)
    return pushes


def _event(event_id: str, event_type: str, **extra) -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "booking_id": "book-1",
        "parking_spot_id": "spot-1",
        "parking_spot_title": "Cochera Palermo",
        "owner_user_id": OWNER,
        "driver_user_id": DRIVER,
        "start": datetime(2026, 10, 14, 15, 0, tzinfo=UTC).isoformat(),
        "end": datetime(2026, 10, 14, 17, 0, tzinfo=UTC).isoformat(),
        "amount": 1000000,
        **extra,
    }


@pytest.mark.asyncio
async def test_owner_cancellation_tells_the_driver_why(db, sent):
    await consumer_module._handle_booking_cancelled(
        _event("evt-oc", "booking.cancelled", cancelled_by="owner_cancelled", note="Se rompió el portón"),
        session_factory=TestingSessionLocal,
    )

    assert [p.user_id for p in sent] == [DRIVER]
    assert sent[0].kind == "driver_owner_cancelled"
    assert "Se rompió el portón" in sent[0].body
    entry = db.query(Notification).one()
    assert entry.data["notes"] == "Se rompió el portón"


@pytest.mark.asyncio
async def test_late_driver_cancellation_tells_the_owner_they_still_get_half(db, sent):
    await consumer_module._handle_booking_cancelled(
        _event("evt-late", "booking.cancelled", cancelled_by="driver", refunded_amount=500000),
        session_factory=TestingSessionLocal,
    )

    assert [p.user_id for p in sent] == [OWNER]
    assert "la mitad" in sent[0].body
    assert db.query(Notification).one().data["refunded_amount"] == 500000


@pytest.mark.asyncio
async def test_extension_tells_both_sides_until_when(db, sent):
    await consumer_module._handle_booking_extended(
        _event("evt-ext", "booking.extended", parent_booking_id="book-0"), session_factory=TestingSessionLocal
    )

    kinds = {p.user_id: p.kind for p in sent}
    assert kinds == {DRIVER: "driver_booking_extended", OWNER: "owner_booking_extended"}
    assert all("14:00" in p.body for p in sent)  # 17:00 UTC is 14:00 in Buenos Aires
    assert all(n.data["parent_booking_id"] == "book-0" for n in db.query(Notification).all())

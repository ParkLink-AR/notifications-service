from app.messaging import consumer as consumer_module
from app.models import ProcessedEvent
from tests.conftest import TestingSessionLocal

EVENT_BODY = {
    "event_id": "evt-dup",
    "event_type": "booking.confirmed",
    "booking_id": "book-1",
    "parking_spot_id": "spot-1",
    "parking_spot_title": "T",
    "owner_user_id": "22222222-2222-2222-2222-222222222222",
    "driver_user_id": "11111111-1111-1111-1111-111111111111",
    "start": "2026-09-04T21:00:00+00:00",
    "end": "2026-09-04T23:00:00+00:00",
}


async def test_duplicate_event_is_handled_once(db, monkeypatch):
    sends: list = []

    monkeypatch.setattr(
        consumer_module.push,
        "send_pushes",
        lambda _db, pushes: sends.append(pushes) or len(pushes),
    )

    await consumer_module._handle_booking_confirmed(EVENT_BODY, session_factory=TestingSessionLocal)
    await consumer_module._handle_booking_confirmed(EVENT_BODY, session_factory=TestingSessionLocal)

    assert len(sends) == 1
    assert db.query(ProcessedEvent).count() == 1
    assert db.get(ProcessedEvent, "evt-dup").event_type == "booking.confirmed"

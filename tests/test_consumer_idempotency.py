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


PAYOUT_PAID_EVENT_BODY = {
    "event_id": "evt-payout-dup",
    "event_type": "payout.paid",
    "payout_id": "payout-1",
    "booking_id": "book-1",
    "recipient_user_id": "22222222-2222-2222-2222-222222222222",
    "net_amount": 12345,
    "parking_spot_title": "Cochera Palermo",
}


def test_payout_paid_routing_key_is_bound_and_dispatched():
    assert "payout.paid" in consumer_module.BINDING_KEYS
    assert consumer_module.HANDLERS["payout.paid"] is consumer_module._handle_payout_paid


async def test_duplicate_payout_paid_event_is_handled_once(db, monkeypatch):
    sends: list = []

    monkeypatch.setattr(
        consumer_module.push,
        "send_pushes",
        lambda _db, pushes: sends.append(pushes) or len(pushes),
    )

    await consumer_module._handle_payout_paid(PAYOUT_PAID_EVENT_BODY, session_factory=TestingSessionLocal)
    await consumer_module._handle_payout_paid(PAYOUT_PAID_EVENT_BODY, session_factory=TestingSessionLocal)

    assert len(sends) == 1
    assert db.query(ProcessedEvent).count() == 1
    assert db.get(ProcessedEvent, "evt-payout-dup").event_type == "payout.paid"

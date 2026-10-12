"""The notifications added after the audit: each lands in the right inbox(es) with a push
that opens the right screen."""
from datetime import datetime, timezone

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


def _booking(event_id: str, event_type: str, **extra) -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "booking_id": "book-1",
        "parking_spot_id": "spot-1",
        "parking_spot_title": "Cochera Palermo",
        "owner_user_id": OWNER,
        "driver_user_id": DRIVER,
        "start": datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc).isoformat(),  # 12:00 ART
        "end": datetime(2026, 10, 14, 17, 0, tzinfo=timezone.utc).isoformat(),    # 14:00 ART
        "amount": 864000,
        **extra,
    }


def _inbox(db, user_id: str) -> list[Notification]:
    return [n for n in db.query(Notification).all() if str(n.user_id) == user_id]


def _kinds(db) -> set[tuple[str, str]]:
    return {(str(n.user_id), n.kind) for n in db.query(Notification).all()}


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        ("approved", {(OWNER, "owner_payout_approved")}),
        ("refunded", {(OWNER, "owner_payout_denied"), (DRIVER, "driver_unverified_refunded")}),
    ],
)
async def test_unverified_booking_decision(db, sent, decision, expected):
    await consumer_module._handle_booking_verification_reviewed(
        _booking(f"evt-{decision}", "booking.verification_reviewed", decision=decision),
        session_factory=TestingSessionLocal,
    )
    assert _kinds(db) == expected
    assert all(p.data["type"] == "booking.verification_reviewed" for p in sent)


async def test_approval_reminder_nudges_the_owner(db, sent):
    deadline = datetime(2026, 10, 14, 18, 30, tzinfo=timezone.utc).isoformat()  # 15:30 ART
    await consumer_module._handle_booking_approval_reminder(
        _booking("evt-rem", "booking.approval_reminder", owner_response_deadline=deadline),
        session_factory=TestingSessionLocal,
    )
    [entry] = _inbox(db, OWNER)
    assert entry.kind == "owner_request_reminder"
    assert "antes de las 15:30" in sent[0].body


async def test_starting_soon_tells_both_sides(db, sent):
    await consumer_module._handle_booking_starting_soon(
        _booking("evt-start", "booking.starting_soon"), session_factory=TestingSessionLocal
    )
    assert _kinds(db) == {(DRIVER, "driver_starting_soon"), (OWNER, "owner_starting_soon")}
    assert any("a las 12:00" in p.body for p in sent)


async def test_ending_soon_tells_the_driver(db, sent):
    await consumer_module._handle_booking_ending_soon(
        _booking("evt-end", "booking.ending_soon"), session_factory=TestingSessionLocal
    )
    assert _kinds(db) == {(DRIVER, "driver_stay_ending")}
    assert "termina a las 14:00" in sent[0].body


async def test_review_received_tells_the_reviewed_person(db, sent):
    await consumer_module._handle_review_received(
        {
            "event_id": "evt-review", "booking_id": "book-1", "parking_spot_id": "spot-1",
            "parking_spot_title": "Cochera Palermo", "reviewer_user_id": DRIVER,
            "recipient_user_id": OWNER, "recipient_role": "owner", "rating": 4,
        },
        session_factory=TestingSessionLocal,
    )
    [entry] = _inbox(db, OWNER)
    assert (entry.kind, entry.role, entry.data["rating"]) == ("review_received", "owner", 4)
    assert sent[0].body.startswith("★★★★ — el conductor te calificó")


async def test_ticket_closed_tells_its_creator(db, sent):
    await consumer_module._handle_support_ticket_closed(
        {
            "event_id": "evt-ticket", "ticket_id": "t1", "booking_id": "book-1",
            "ticket_subject": "No me pagaron", "recipient_user_id": OWNER, "recipient_role": "owner",
            "status": "RESOLVED",
        },
        session_factory=TestingSessionLocal,
    )
    [entry] = _inbox(db, OWNER)
    assert entry.kind == "ticket_closed"
    assert sent[0].data == {"type": "support.ticket_closed", "ticketId": "t1", "bookingId": "book-1"}


async def test_refund_completed_tells_the_driver(db, sent):
    await consumer_module._handle_refund_completed(
        {"event_id": "evt-refund", "booking_id": "book-1", "driver_user_id": DRIVER, "amount": 864000, "method": "manual"},
        session_factory=TestingSessionLocal,
    )
    [entry] = _inbox(db, DRIVER)
    assert entry.kind == "driver_refund_completed"
    assert "Te devolvimos $8.640,00 por otro medio" in sent[0].body


def test_every_new_event_is_bound_and_dispatched():
    for key in [
        "booking.verification_reviewed", "booking.approval_reminder", "booking.starting_soon",
        "booking.ending_soon", "review.received", "support.ticket_closed", "refund.completed",
        "settlement.drafted",
    ]:
        assert key in consumer_module.BINDING_KEYS
        assert key in consumer_module.HANDLERS


async def test_settlement_drafted_tells_the_owner(db, sent):
    await consumer_module._handle_settlement_drafted(
        {
            "event_id": "evt-draft", "settlement_id": "set-1", "recipient_user_id": OWNER,
            "net_amount": 1500000, "booking_count": 2,
        },
        session_factory=TestingSessionLocal,
    )
    [entry] = _inbox(db, OWNER)
    assert (entry.kind, entry.role) == ("owner_settlement_drafted", "owner")
    assert sent[0].title == "🧾 Estamos preparando tu liquidación"
    assert "$15.000,00 por 2 reservas" in sent[0].body
    assert sent[0].data == {"type": "settlement.drafted", "settlementId": "set-1"}

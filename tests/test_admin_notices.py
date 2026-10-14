"""What users hear about from ParkLink staff's actions: a booking cancelled or refunded from
the admin panel, a spot suspended or restored, and announcements."""
from datetime import UTC, datetime

import pytest

from app.api import broadcasts as broadcasts_module
from app.messaging import consumer as consumer_module
from app.models import Broadcast, Notification
from tests.conftest import TestingSessionLocal

DRIVER = "11111111-1111-1111-1111-111111111111"
OWNER = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def sent(monkeypatch):
    pushes: list = []
    monkeypatch.setattr(consumer_module.push, "send_pushes", lambda _db, batch: pushes.extend(batch) or len(batch))
    monkeypatch.setattr(broadcasts_module.push, "send_pushes", lambda _db, batch: pushes.extend(batch) or len(batch))

    async def no_announce(_users):
        return None

    monkeypatch.setattr(consumer_module.live, "announce", no_announce)
    monkeypatch.setattr(broadcasts_module.live, "announce", no_announce)
    return pushes


def _admin_action(event_id: str, action: str, refunded: int) -> dict:
    return {
        "event_id": event_id,
        "event_type": "booking.admin_action",
        "booking_id": "book-1",
        "parking_spot_id": "spot-1",
        "parking_spot_title": "Cochera Palermo",
        "owner_user_id": OWNER,
        "driver_user_id": DRIVER,
        "start": datetime(2026, 10, 14, 15, 0, tzinfo=UTC).isoformat(),
        "end": datetime(2026, 10, 14, 17, 0, tzinfo=UTC).isoformat(),
        "amount": 1000000,
        "action": action,
        "refunded_amount": refunded,
    }


@pytest.mark.asyncio
async def test_admin_cancellation_tells_both_sides_with_the_refund(db, sent):
    await consumer_module._handle_booking_admin_action(
        _admin_action("evt-1", "cancelled", 1000000), session_factory=TestingSessionLocal
    )

    by_user = {p.user_id: p for p in sent}
    assert by_user[DRIVER].kind == "driver_admin_cancelled"
    assert "$10.000,00" in by_user[DRIVER].body
    assert by_user[OWNER].kind == "owner_admin_cancelled"
    assert db.query(Notification).count() == 2


@pytest.mark.asyncio
async def test_admin_refund_tells_both_sides(db, sent):
    await consumer_module._handle_booking_admin_action(
        _admin_action("evt-2", "refunded", 250000), session_factory=TestingSessionLocal
    )

    kinds = {p.user_id: p.kind for p in sent}
    assert kinds == {DRIVER: "driver_admin_refund", OWNER: "owner_admin_refund"}
    assert "$2.500,00" in next(p.body for p in sent if p.user_id == DRIVER)


@pytest.mark.asyncio
@pytest.mark.parametrize("decision,kind", [("suspended", "owner_spot_suspended"), ("restored", "owner_spot_restored")])
async def test_spot_moderation_tells_the_owner(db, sent, decision, kind):
    await consumer_module._handle_parking_spot_reviewed(
        {
            "event_id": f"evt-{decision}",
            "event_type": "parking_spot.reviewed",
            "parking_spot_id": "spot-1",
            "parking_spot_title": "Cochera Palermo",
            "owner_user_id": OWNER,
            "decision": decision,
            "notes": "Fotos que no corresponden",
        },
        session_factory=TestingSessionLocal,
    )

    assert [p.kind for p in sent] == [kind]
    if decision == "suspended":
        assert "Fotos que no corresponden" in sent[0].body


def test_broadcast_reaches_everyone_in_the_audience(client, db, sent, monkeypatch):
    monkeypatch.setattr(broadcasts_module, "audience_user_ids", lambda audience: [DRIVER, OWNER] if audience == "all" else [])

    response = client.post(
        "/admin/broadcasts",
        json={"title": "Mantenimiento", "body": "El domingo a las 3 la app no va a estar disponible.", "audience": "all"},
        headers={"x-user-id": "admin-1"},
    )

    assert response.status_code == 201
    assert response.json()["recipients"] == 2
    entries = db.query(Notification).all()
    assert {str(e.user_id) for e in entries} == {DRIVER, OWNER}
    assert {e.kind for e in entries} == {"announcement"}
    assert len(sent) == 2
    history = client.get("/admin/broadcasts").json()
    assert [b["title"] for b in history] == ["Mantenimiento"]
    assert db.query(Broadcast).count() == 1


def test_broadcast_validates_the_audience(client):
    response = client.post("/admin/broadcasts", json={"title": "x", "body": "y", "audience": "everyone"})
    assert response.status_code == 422

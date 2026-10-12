from datetime import datetime, timedelta, timezone

import pytest

from app.messaging import consumer as consumer_module
from app.models import Notification
from tests.conftest import TestingSessionLocal

DRIVER = "11111111-1111-1111-1111-111111111111"
OWNER = "22222222-2222-2222-2222-222222222222"
STRANGER = "33333333-3333-3333-3333-333333333333"


def _booking_event(event_id: str, event_type: str, **overrides) -> dict:
    body = {
        "event_id": event_id,
        "event_type": event_type,
        "booking_id": "book-1",
        "parking_spot_id": "spot-1",
        "parking_spot_title": "Cochera Palermo",
        "owner_user_id": OWNER,
        "driver_user_id": DRIVER,
        "start": "2026-09-04T21:00:00+00:00",
        "end": "2026-09-04T23:00:00+00:00",
        "amount": 892500,
    }
    body.update(overrides)
    return body


@pytest.fixture
def sent(monkeypatch):
    """Every push the consumer hands to FCM, and every live announcement."""
    record = {"pushes": [], "announced": []}
    monkeypatch.setattr(
        consumer_module.push, "send_pushes", lambda _db, pushes: record["pushes"].extend(pushes) or len(pushes)
    )

    async def fake_announce(user_ids):
        record["announced"].append(set(user_ids))

    monkeypatch.setattr(consumer_module.live, "announce", fake_announce)
    return record


def _inbox(db, user_id: str) -> list[Notification]:
    db.expire_all()
    return [n for n in db.query(Notification).all() if str(n.user_id) == user_id]


# -- consumer -> inbox ---------------------------------------------------------------


async def test_event_is_saved_in_the_recipients_inbox(db, sent):
    await consumer_module._handle_booking_confirmed(
        _booking_event("evt-1", "booking.confirmed"), session_factory=TestingSessionLocal
    )

    [entry] = _inbox(db, DRIVER)
    assert entry.kind == "driver_confirmed"
    assert entry.role == "driver"
    assert entry.booking_id == "book-1"
    assert entry.data["spot_title"] == "Cochera Palermo"
    assert entry.data["start"] == "2026-09-04T21:00:00+00:00"
    assert entry.read_at is None
    assert "Reserva confirmada" in entry.title
    assert _inbox(db, OWNER) == []
    assert sent["announced"] == [{DRIVER}]


async def test_redelivered_event_adds_no_second_entry(db, sent):
    body = _booking_event("evt-dup", "booking.confirmed")
    await consumer_module._handle_booking_confirmed(body, session_factory=TestingSessionLocal)
    await consumer_module._handle_booking_confirmed(body, session_factory=TestingSessionLocal)

    assert len(_inbox(db, DRIVER)) == 1
    assert len(sent["pushes"]) == 1


async def test_push_failure_keeps_the_inbox_entry(db, monkeypatch):
    def boom(_db, _pushes):
        raise ConnectionError("fcm down")

    monkeypatch.setattr(consumer_module.push, "send_pushes", boom)

    async def no_announce(_user_ids):
        return None

    monkeypatch.setattr(consumer_module.live, "announce", no_announce)

    await consumer_module._handle_booking_confirmed(
        _booking_event("evt-fcm", "booking.confirmed"), session_factory=TestingSessionLocal
    )

    assert len(_inbox(db, DRIVER)) == 1


async def test_answering_a_request_resolves_the_owners_notification(db, sent):
    await consumer_module._handle_booking_pending_approval(
        _booking_event("evt-req", "booking.pending_approval", owner_response_deadline="2026-09-04T12:00:00+00:00"),
        session_factory=TestingSessionLocal,
    )
    [request] = _inbox(db, OWNER)
    assert request.kind == "owner_request"
    assert request.data["owner_response_deadline"] == "2026-09-04T12:00:00+00:00"
    assert request.resolved_at is None

    await consumer_module._handle_booking_confirmed(
        _booking_event("evt-ok", "booking.confirmed"), session_factory=TestingSessionLocal
    )

    [request] = _inbox(db, OWNER)
    assert request.resolved_at is not None
    # The owner's open app is told too, so the accept/reject buttons go away.
    assert sent["announced"][-1] == {DRIVER, OWNER}


@pytest.mark.parametrize(
    ("cancelled_by", "recipient", "kind"),
    [
        ("owner_rejected", DRIVER, "driver_rejected"),
        ("owner_account", DRIVER, "driver_spot_unavailable"),
        ("driver", OWNER, "owner_booking_cancelled"),
        ("driver_account", OWNER, "owner_booking_cancelled"),
    ],
)
async def test_cancellation_tells_the_side_that_didnt_cancel(db, sent, cancelled_by, recipient, kind):
    await consumer_module._handle_booking_cancelled(
        _booking_event(f"evt-{cancelled_by}", "booking.cancelled", cancelled_by=cancelled_by),
        session_factory=TestingSessionLocal,
    )

    other = OWNER if recipient == DRIVER else DRIVER
    [entry] = _inbox(db, recipient)
    assert entry.kind == kind
    assert entry.role == ("driver" if recipient == DRIVER else "owner")
    assert _inbox(db, other) == []
    assert [p.user_id for p in sent["pushes"]] == [recipient]


async def test_an_expired_request_tells_both_sides(db, sent):
    await consumer_module._handle_booking_cancelled(
        _booking_event("evt-owner_expired", "booking.cancelled", cancelled_by="owner_expired"),
        session_factory=TestingSessionLocal,
    )

    [driver_entry] = _inbox(db, DRIVER)
    [owner_entry] = _inbox(db, OWNER)
    assert driver_entry.kind == "driver_request_expired"
    assert owner_entry.kind == "owner_request_expired"
    assert owner_entry.role == "owner"


async def test_cancelled_request_is_resolved_too(db, sent):
    await consumer_module._handle_booking_pending_approval(
        _booking_event("evt-req", "booking.pending_approval"), session_factory=TestingSessionLocal
    )
    await consumer_module._handle_booking_cancelled(
        _booking_event("evt-exp", "booking.cancelled", cancelled_by="owner_expired"),
        session_factory=TestingSessionLocal,
    )

    request = next(entry for entry in _inbox(db, OWNER) if entry.kind == "owner_request")
    assert request.resolved_at is not None


async def test_completed_stay_asks_both_sides_for_a_review(db, sent):
    await consumer_module._handle_booking_completed(
        _booking_event("evt-done", "booking.completed"), session_factory=TestingSessionLocal
    )

    [driver_entry] = _inbox(db, DRIVER)
    [owner_entry] = _inbox(db, OWNER)
    assert driver_entry.kind == "driver_review_prompt"
    assert owner_entry.kind == "owner_review_prompt"
    assert owner_entry.data["driver_user_id"] == DRIVER
    assert {p.data["role"] for p in sent["pushes"]} == {"driver", "owner"}


async def test_completed_stay_without_owner_asks_only_the_driver(db, sent):
    await consumer_module._handle_booking_completed(
        _booking_event("evt-done", "booking.completed", owner_user_id=None), session_factory=TestingSessionLocal
    )

    assert [n.kind for n in _inbox(db, DRIVER)] == ["driver_review_prompt"]
    assert _inbox(db, OWNER) == []


async def test_message_keeps_the_recipients_side(db, sent):
    await consumer_module._handle_booking_message_sent(
        {
            "event_id": "evt-msg",
            "booking_id": "book-1",
            "parking_spot_id": "spot-1",
            "parking_spot_title": "Cochera Palermo",
            "sender_user_id": DRIVER,
            "recipient_user_id": OWNER,
            "recipient_role": "owner",
            "body": "¿A qué hora llegás?",
        },
        session_factory=TestingSessionLocal,
    )

    [entry] = _inbox(db, OWNER)
    assert entry.kind == "message_received"
    assert entry.role == "owner"
    assert entry.data["preview"] == "¿A qué hora llegás?"


def test_completed_routing_key_is_bound_and_dispatched():
    assert "booking.completed" in consumer_module.BINDING_KEYS
    assert consumer_module.HANDLERS["booking.completed"] is consumer_module._handle_booking_completed


# -- REST API ----------------------------------------------------------------------


def _add(db, user_id: str, kind: str = "driver_confirmed", *, minutes_ago: int = 0, read: bool = False) -> Notification:
    now = datetime.now(timezone.utc)
    entry = Notification(
        user_id=user_id,
        role="driver",
        kind=kind,
        booking_id="book-1",
        data={"booking_id": "book-1"},
        title="t",
        body="b",
        created_at=now - timedelta(minutes=minutes_ago),
        read_at=now if read else None,
    )
    db.add(entry)
    db.commit()
    return entry


def test_list_returns_only_the_callers_notifications_newest_first(client, db):
    older = _add(db, DRIVER, minutes_ago=10)
    newer = _add(db, DRIVER, "driver_verified", minutes_ago=1, read=True)
    _add(db, STRANGER)

    response = client.get("/notifications", headers={"X-User-Id": DRIVER})

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [newer.id, older.id]
    assert body["unread_count"] == 1
    assert body["next_before"] is None
    assert body["items"][0]["kind"] == "driver_verified"
    assert body["items"][0]["read_at"] is not None
    assert body["items"][1]["data"] == {"booking_id": "book-1"}


def test_list_pages_with_before(client, db):
    ids = [_add(db, DRIVER, minutes_ago=m).id for m in (1, 2, 3)]

    first = client.get("/notifications?limit=2", headers={"X-User-Id": DRIVER}).json()
    assert [item["id"] for item in first["items"]] == ids[:2]
    assert first["next_before"] is not None

    second = client.get(
        "/notifications", params={"limit": 2, "before": first["next_before"]}, headers={"X-User-Id": DRIVER}
    ).json()
    assert [item["id"] for item in second["items"]] == ids[2:]
    assert second["next_before"] is None


def test_unread_count(client, db):
    _add(db, DRIVER)
    _add(db, DRIVER, read=True)
    _add(db, STRANGER)

    response = client.get("/notifications/unread-count", headers={"X-User-Id": DRIVER})

    assert response.json() == {"unread_count": 1}


def test_mark_all_read(client, db):
    _add(db, DRIVER)
    _add(db, DRIVER)
    stranger = _add(db, STRANGER)

    response = client.post("/notifications/read", json={}, headers={"X-User-Id": DRIVER})

    assert response.json() == {"unread_count": 0}
    db.expire_all()
    assert db.get(Notification, stranger.id).read_at is None


def test_mark_some_read_never_touches_someone_elses(client, db):
    mine = _add(db, DRIVER)
    other_mine = _add(db, DRIVER)
    stranger = _add(db, STRANGER)

    response = client.post(
        "/notifications/read", json={"ids": [mine.id, stranger.id]}, headers={"X-User-Id": DRIVER}
    )

    assert response.json() == {"unread_count": 1}
    db.expire_all()
    assert db.get(Notification, mine.id).read_at is not None
    assert db.get(Notification, other_mine.id).read_at is None
    assert db.get(Notification, stranger.id).read_at is None


def test_inbox_routes_require_the_gateways_user_header(client):
    assert client.get("/notifications").status_code == 400
    assert client.get("/notifications/unread-count").status_code == 400
    assert client.post("/notifications/read", json={}).status_code == 400


def test_internal_delete_drops_the_whole_inbox(client, db):
    _add(db, DRIVER)
    _add(db, STRANGER)

    response = client.delete(f"/internal/users/{DRIVER}/notifications")

    assert response.status_code == 204
    assert _inbox(db, DRIVER) == []
    assert len(_inbox(db, STRANGER)) == 1

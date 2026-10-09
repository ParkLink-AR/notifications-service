from app.handlers.parking_spot_reviewed import build_parking_spot_reviewed_pushes
from app.messaging import consumer as consumer_module
from app.messaging.events import ParkingSpotReviewedEvent
from app.models import Notification, ProcessedEvent
from tests.conftest import TestingSessionLocal

OWNER = "11111111-1111-1111-1111-111111111111"
SPOT = "22222222-2222-2222-2222-222222222222"


def _event(**overrides) -> ParkingSpotReviewedEvent:
    base = dict(
        event_id="evt-review-1",
        parking_spot_id=SPOT,
        parking_spot_title="Av. Corrientes 800",
        owner_user_id=OWNER,
        decision="approved",
        notes=None,
    )
    base.update(overrides)
    return ParkingSpotReviewedEvent(**base)


def test_tells_the_owner_their_spot_was_approved():
    pushes = build_parking_spot_reviewed_pushes(_event())

    assert [p.user_id for p in pushes] == [OWNER]
    assert pushes[0].title == "✅ ¡Tu cochera fue aprobada!"
    assert "«Av. Corrientes 800» ya está publicada" in pushes[0].body
    assert pushes[0].kind == "owner_spot_approved"
    assert pushes[0].role == "owner"
    assert pushes[0].data == {"type": "parking_spot.reviewed", "parkingSpotId": SPOT, "decision": "approved"}


def test_tells_the_owner_why_their_spot_was_rejected():
    pushes = build_parking_spot_reviewed_pushes(_event(decision="rejected", notes="Las fotos no muestran la cochera"))

    assert pushes[0].kind == "owner_spot_rejected"
    assert pushes[0].title == "Tu cochera no fue aprobada"
    assert "Motivo: Las fotos no muestran la cochera. Podés corregirla" in pushes[0].body
    assert pushes[0].payload["notes"] == "Las fotos no muestran la cochera"


def test_a_rejection_without_notes_has_no_reason():
    pushes = build_parking_spot_reviewed_pushes(_event(decision="rejected", notes="  "))

    assert "Motivo" not in pushes[0].body


def test_an_unknown_decision_sends_nothing():
    assert build_parking_spot_reviewed_pushes(_event(decision="maybe")) == []


def test_routing_key_is_bound_and_dispatched():
    assert "parking_spot.reviewed" in consumer_module.BINDING_KEYS
    assert consumer_module.HANDLERS["parking_spot.reviewed"] is consumer_module._handle_parking_spot_reviewed


async def test_a_review_lands_once_in_the_owners_inbox(db, monkeypatch):
    sends: list = []
    monkeypatch.setattr(consumer_module.push, "send_pushes", lambda _db, pushes: sends.append(pushes) or len(pushes))
    async def no_announce(_users):
        return None
    monkeypatch.setattr(consumer_module.live, "announce", no_announce)
    body = _event(event_id="evt-review-dup").model_dump(mode="json")

    await consumer_module._handle_parking_spot_reviewed(body, session_factory=TestingSessionLocal)
    await consumer_module._handle_parking_spot_reviewed(body, session_factory=TestingSessionLocal)

    assert len(sends) == 1
    entries = db.query(Notification).all()
    assert [(str(e.user_id), e.kind, e.role) for e in entries] == [(OWNER, "owner_spot_approved", "owner")]
    assert entries[0].data["parking_spot_id"] == SPOT
    assert db.get(ProcessedEvent, "evt-review-dup").event_type == "parking_spot.reviewed"

from datetime import datetime, timezone

from app.handlers.booking_pending_approval import build_booking_pending_approval_pushes
from app.messaging.events import BookingPendingApprovalEvent

DRIVER = "11111111-1111-1111-1111-111111111111"
OWNER = "22222222-2222-2222-2222-222222222222"


def _event(**overrides) -> BookingPendingApprovalEvent:
    base = dict(
        event_id="evt-1",
        event_type="booking.pending_approval",
        booking_id="book-1",
        parking_spot_id="spot-1",
        parking_spot_title="Cochera Palermo",
        owner_user_id=OWNER,
        driver_user_id=DRIVER,
        start=datetime(2026, 9, 4, 21, 0, tzinfo=timezone.utc),  # 18:00 ART
        end=datetime(2026, 9, 4, 23, 0, tzinfo=timezone.utc),    # 20:00 ART
        owner_response_deadline=datetime(2026, 9, 5, 21, 0, tzinfo=timezone.utc),  # 18:00 ART
    )
    base.update(overrides)
    return BookingPendingApprovalEvent(**base)


def test_notifies_the_owner_with_the_deadline():
    pushes = build_booking_pending_approval_pushes(_event())

    assert [p.user_id for p in pushes] == [OWNER]
    assert "reserva para confirmar" in pushes[0].title
    assert "Cochera Palermo" in pushes[0].body
    assert "de 18:00 a 20:00" in pushes[0].body
    assert "antes del 5 de septiembre de 2026 a las 18:00" in pushes[0].body
    assert pushes[0].data == {"type": "booking.pending_approval", "bookingId": "book-1"}


def test_no_deadline_clause_when_deadline_absent():
    pushes = build_booking_pending_approval_pushes(_event(owner_response_deadline=None))

    assert len(pushes) == 1
    assert "antes de" not in pushes[0].body


def test_empty_when_no_owner():
    assert build_booking_pending_approval_pushes(_event(owner_user_id=None)) == []


def test_empty_when_owner_is_the_driver():
    assert build_booking_pending_approval_pushes(_event(owner_user_id=DRIVER)) == []


def test_falls_back_to_generic_title_when_not_embedded():
    pushes = build_booking_pending_approval_pushes(_event(parking_spot_title=""))

    assert "tu cochera" in pushes[0].body

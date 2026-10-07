from datetime import datetime, timezone

from app.handlers.booking_cancelled import build_booking_cancelled_pushes
from app.messaging.events import BookingCancelledEvent

DRIVER = "11111111-1111-1111-1111-111111111111"
OWNER = "22222222-2222-2222-2222-222222222222"


def _event(**overrides) -> BookingCancelledEvent:
    base = dict(
        event_id="evt-1",
        event_type="booking.cancelled",
        booking_id="book-1",
        parking_spot_id="spot-1",
        parking_spot_title="Cochera Palermo",
        owner_user_id=OWNER,
        driver_user_id=DRIVER,
        start=datetime(2026, 9, 4, 21, 0, tzinfo=timezone.utc),  # 18:00 ART
        end=datetime(2026, 9, 4, 23, 0, tzinfo=timezone.utc),    # 20:00 ART
        cancelled_by="owner_account",
    )
    base.update(overrides)
    return BookingCancelledEvent(**base)


def test_owner_account_closed_tells_the_driver_they_get_the_money_back():
    pushes = build_booking_cancelled_pushes(_event())

    assert [p.user_id for p in pushes] == [DRIVER]
    assert "Cochera Palermo" in pushes[0].body
    assert "de 18:00 a 20:00" in pushes[0].body
    assert "devolvemos el total" in pushes[0].body
    assert pushes[0].data == {"type": "booking.cancelled", "bookingId": "book-1"}


def test_driver_account_closed_tells_the_owner():
    pushes = build_booking_cancelled_pushes(_event(cancelled_by="driver_account"))

    assert [p.user_id for p in pushes] == [OWNER]
    assert "conductor" in pushes[0].body


def test_unknown_side_sends_nothing():
    assert build_booking_cancelled_pushes(_event(cancelled_by="who-knows")) == []


def test_falls_back_to_generic_title_when_not_embedded():
    pushes = build_booking_cancelled_pushes(_event(parking_spot_title=""))

    assert "tu cochera" in pushes[0].body

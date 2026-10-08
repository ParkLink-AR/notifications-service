from datetime import datetime, timezone

from app.handlers.booking_confirmed import build_booking_confirmed_pushes
from app.messaging.events import BookingConfirmedEvent

DRIVER = "11111111-1111-1111-1111-111111111111"
OWNER = "22222222-2222-2222-2222-222222222222"


def _event(**overrides) -> BookingConfirmedEvent:
    base = dict(
        event_id="evt-1",
        event_type="booking.confirmed",
        booking_id="book-1",
        parking_spot_id="spot-1",
        parking_spot_title="Cochera Palermo",
        owner_user_id=OWNER,
        driver_user_id=DRIVER,
        start=datetime(2026, 9, 4, 21, 0, tzinfo=timezone.utc),  # 18:00 ART
        end=datetime(2026, 9, 4, 23, 0, tzinfo=timezone.utc),    # 20:00 ART
    )
    base.update(overrides)
    return BookingConfirmedEvent(**base)


def test_notifies_only_the_driver():
    pushes = build_booking_confirmed_pushes(_event())

    assert [p.user_id for p in pushes] == [DRIVER]
    assert "Reserva confirmada" in pushes[0].title
    assert "Cochera Palermo" in pushes[0].body
    assert "de 18:00 a 20:00" in pushes[0].body
    assert pushes[0].data == {"type": "booking.confirmed", "bookingId": "book-1"}


def test_falls_back_to_generic_title_when_not_embedded():
    pushes = build_booking_confirmed_pushes(_event(parking_spot_title=""))

    assert "tu cochera" in pushes[0].body


def test_dates_use_the_long_format_with_the_year():
    pushes = build_booking_confirmed_pushes(_event())

    assert "el 4 de septiembre de 2026, de 18:00 a 20:00" in pushes[0].body


def test_multi_day_stay_names_both_days():
    pushes = build_booking_confirmed_pushes(
        _event(end=datetime(2026, 9, 6, 21, 0, tzinfo=timezone.utc))  # 6/9 18:00 ART
    )

    assert "del 4 de septiembre de 2026 a las 18:00 al 6 de septiembre de 2026 a las 18:00" in pushes[0].body

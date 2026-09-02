from datetime import datetime, timezone

from app.handlers import booking_confirmed as handler
from app.messaging.events import BookingConfirmedEvent
from app.services.recipients import SpotInfo

DRIVER = "11111111-1111-1111-1111-111111111111"
OWNER = "22222222-2222-2222-2222-222222222222"


def _event(**overrides) -> BookingConfirmedEvent:
    base = dict(
        event_id="evt-1",
        event_type="booking.confirmed",
        booking_id="book-1",
        parking_spot_id="spot-1",
        driver_user_id=DRIVER,
        start=datetime(2026, 9, 4, 21, 0, tzinfo=timezone.utc),  # 18:00 ART
        end=datetime(2026, 9, 4, 23, 0, tzinfo=timezone.utc),    # 20:00 ART
    )
    base.update(overrides)
    return BookingConfirmedEvent(**base)


async def test_builds_driver_and_owner_pushes(monkeypatch):
    async def fake_resolve(_spot_id):
        return SpotInfo(owner_id=OWNER, title="Cochera Palermo")

    monkeypatch.setattr(handler, "resolve_spot", fake_resolve)

    pushes = await handler.build_booking_confirmed_pushes(_event())

    assert [p.user_id for p in pushes] == [DRIVER, OWNER]
    assert pushes[0].title == "Reserva confirmada"
    assert "Cochera Palermo" in pushes[0].body
    assert "de 18:00 a 20:00" in pushes[0].body
    assert pushes[0].data == {"type": "booking.confirmed", "bookingId": "book-1"}
    assert pushes[1].title == "Nueva reserva"
    assert "Reservaron tu cochera Cochera Palermo" in pushes[1].body


async def test_no_owner_push_when_owner_is_the_driver(monkeypatch):
    async def fake_resolve(_spot_id):
        return SpotInfo(owner_id=DRIVER, title="Mi Cochera")

    monkeypatch.setattr(handler, "resolve_spot", fake_resolve)

    pushes = await handler.build_booking_confirmed_pushes(_event())

    assert len(pushes) == 1
    assert pushes[0].user_id == DRIVER


async def test_falls_back_to_generic_title_when_spot_missing(monkeypatch):
    async def fake_resolve(_spot_id):
        return SpotInfo(owner_id=None, title="tu cochera")

    monkeypatch.setattr(handler, "resolve_spot", fake_resolve)

    pushes = await handler.build_booking_confirmed_pushes(_event())

    assert len(pushes) == 1
    assert "tu cochera" in pushes[0].body

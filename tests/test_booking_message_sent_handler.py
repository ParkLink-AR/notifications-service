from app.handlers.booking_message_sent import build_booking_message_sent_pushes
from app.messaging.events import BookingMessageSentEvent

DRIVER = "11111111-1111-1111-1111-111111111111"
OWNER = "22222222-2222-2222-2222-222222222222"


def _event(**overrides) -> BookingMessageSentEvent:
    base = dict(
        event_id="evt-1",
        event_type="booking.message_sent",
        booking_id="book-1",
        parking_spot_id="spot-1",
        parking_spot_title="Cochera Palermo",
        sender_user_id=DRIVER,
        recipient_user_id=OWNER,
        body="¿A qué hora llegás?",
    )
    base.update(overrides)
    return BookingMessageSentEvent(**base)


def test_notifies_the_recipient_with_a_preview():
    pushes = build_booking_message_sent_pushes(_event())

    assert [p.user_id for p in pushes] == [OWNER]
    assert "Cochera Palermo" in pushes[0].title
    assert pushes[0].body == "¿A qué hora llegás?"
    assert pushes[0].data == {"type": "booking.message_sent", "bookingId": "book-1"}


def test_long_message_is_truncated_with_ellipsis():
    long_body = "a" * 200
    pushes = build_booking_message_sent_pushes(_event(body=long_body))

    assert len(pushes[0].body) == 120
    assert pushes[0].body.endswith("…")


def test_empty_when_no_recipient():
    assert build_booking_message_sent_pushes(_event(recipient_user_id="")) == []


def test_empty_when_sender_is_recipient():
    assert build_booking_message_sent_pushes(_event(recipient_user_id=DRIVER)) == []


def test_falls_back_to_generic_title_when_not_embedded():
    pushes = build_booking_message_sent_pushes(_event(parking_spot_title=""))

    assert "tu cochera" in pushes[0].title

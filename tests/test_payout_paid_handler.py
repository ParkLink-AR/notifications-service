from app.handlers.payout_paid import build_payout_paid_pushes
from app.messaging.events import PayoutPaidEvent

OWNER = "11111111-1111-1111-1111-111111111111"


def _event(**overrides) -> PayoutPaidEvent:
    base = dict(
        event_id="evt-1",
        event_type="payout.paid",
        payout_id="payout-1",
        booking_id="book-1",
        recipient_user_id=OWNER,
        net_amount=12345,
        parking_spot_title="Cochera Palermo",
    )
    base.update(overrides)
    return PayoutPaidEvent(**base)


def test_notifies_the_owner_with_amount_and_spot_title():
    pushes = build_payout_paid_pushes(_event())

    assert [p.user_id for p in pushes] == [OWNER]
    assert pushes[0].title == "💸 ¡Tu pago fue depositado!"
    assert pushes[0].body == "Depositamos $123,45 por Cochera Palermo en tu cuenta."
    assert pushes[0].data == {"type": "payout.paid", "payoutId": "payout-1", "bookingId": "book-1"}


def test_empty_when_no_recipient():
    assert build_payout_paid_pushes(_event(recipient_user_id="")) == []


def test_falls_back_to_generic_title_when_spot_title_missing():
    pushes = build_payout_paid_pushes(_event(parking_spot_title=""))

    assert "tu cochera" in pushes[0].body


def test_formats_round_thousands_correctly():
    pushes = build_payout_paid_pushes(_event(net_amount=1000000))

    assert "$10.000,00" in pushes[0].body

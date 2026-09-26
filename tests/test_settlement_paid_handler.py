from app.handlers.settlement_paid import build_settlement_paid_pushes
from app.messaging.events import SettlementPaidEvent

OWNER = "11111111-1111-1111-1111-111111111111"


def _event(**overrides) -> SettlementPaidEvent:
    base = dict(
        event_id="evt-1",
        event_type="settlement.paid",
        settlement_id="settlement-1",
        recipient_user_id=OWNER,
        net_amount=12345,
        booking_count=4,
    )
    base.update(overrides)
    return SettlementPaidEvent(**base)


def test_notifies_the_owner_with_amount_and_booking_count():
    pushes = build_settlement_paid_pushes(_event())

    assert [p.user_id for p in pushes] == [OWNER]
    assert pushes[0].title == "💸 ¡Tu pago fue depositado!"
    assert pushes[0].body == "Depositamos $123,45 correspondientes a 4 reservas."
    assert pushes[0].data == {"type": "settlement.paid", "settlementId": "settlement-1"}


def test_empty_when_no_recipient():
    assert build_settlement_paid_pushes(_event(recipient_user_id="")) == []


def test_uses_singular_when_booking_count_is_one():
    pushes = build_settlement_paid_pushes(_event(booking_count=1))

    assert "1 reserva." in pushes[0].body
    assert "reservas" not in pushes[0].body


def test_formats_round_thousands_correctly():
    pushes = build_settlement_paid_pushes(_event(net_amount=1000000))

    assert "$10.000,00" in pushes[0].body

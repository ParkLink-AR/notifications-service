from app.handlers.outbound import OutboundPush
from app.models import DeviceToken
from app.services import push

USER_A = "11111111-1111-1111-1111-111111111111"
USER_MISSING = "99999999-9999-9999-9999-999999999999"


def test_log_only_send_counts_every_registered_device(db):
    db.add(DeviceToken(token="a", user_id=USER_A, platform="android"))
    db.add(DeviceToken(token="b", user_id=USER_A, platform="ios"))
    db.commit()

    sent = push.send_pushes(db, [OutboundPush(USER_A, "t", "b", {"type": "x"})])

    assert sent == 2  # firebase not initialised -> log-only, still reports the fan-out


def test_send_returns_zero_when_recipient_has_no_devices(db):
    assert push.send_pushes(db, [OutboundPush(USER_MISSING, "t", "b", {})]) == 0


def test_prune_tokens_removes_rows(db):
    db.add(DeviceToken(token="dead-1", user_id=USER_A, platform="android"))
    db.add(DeviceToken(token="keep-1", user_id=USER_A, platform="android"))
    db.commit()

    removed = push.prune_tokens(db, ["dead-1"])

    assert removed == 1
    assert {r.token for r in db.query(DeviceToken).all()} == {"keep-1"}


def test_is_permanent_classifies_fcm_errors():
    class Unregistered(Exception):
        pass

    Unregistered.__name__ = "UnregisteredError"
    assert push._is_permanent(Unregistered()) is True

    class Transient(Exception):
        code = "unavailable"

    assert push._is_permanent(Transient()) is False
    assert push._is_permanent(None) is False


def test_push_data_carries_the_inbox_role():
    data = push._push_data(OutboundPush(USER_A, "t", "b", {"type": "booking.message_sent"}, kind="message_received", role="owner"))

    assert data == {"type": "booking.message_sent", "role": "owner"}


def test_push_data_keeps_an_explicit_role_and_skips_roleless():
    explicit = OutboundPush(USER_A, "t", "b", {"type": "x", "role": "driver"}, role="owner")
    roleless = OutboundPush(USER_A, "t", "b", {"type": "announcement"}, kind="announcement")

    assert push._push_data(explicit)["role"] == "driver"
    assert "role" not in push._push_data(roleless)

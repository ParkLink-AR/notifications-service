from app.models import DeviceToken

USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"


def test_register_requires_user_id_header(client):
    resp = client.put("/notifications/tokens", json={"token": "t1", "platform": "android"})
    assert resp.status_code == 400


def test_register_rejects_unknown_platform(client):
    resp = client.put(
        "/notifications/tokens",
        json={"token": "t1", "platform": "windows"},
        headers={"X-User-Id": USER_A},
    )
    assert resp.status_code == 400


def test_register_creates_row(client, db):
    resp = client.put(
        "/notifications/tokens",
        json={"token": "tok-1", "platform": "android", "device_id": "dev-1"},
        headers={"X-User-Id": USER_A},
    )
    assert resp.status_code == 200
    rows = db.query(DeviceToken).all()
    assert len(rows) == 1
    assert rows[0].token == "tok-1"
    assert str(rows[0].user_id) == USER_A
    assert rows[0].platform == "android"
    assert rows[0].device_id == "dev-1"


def test_register_is_upsert_by_token(client, db):
    client.put(
        "/notifications/tokens",
        json={"token": "tok-1", "platform": "android"},
        headers={"X-User-Id": USER_A},
    )
    client.put(
        "/notifications/tokens",
        json={"token": "tok-1", "platform": "ios"},
        headers={"X-User-Id": USER_B},
    )
    rows = db.query(DeviceToken).all()
    assert len(rows) == 1
    assert str(rows[0].user_id) == USER_B
    assert rows[0].platform == "ios"


def test_delete_token(client, db):
    client.put(
        "/notifications/tokens",
        json={"token": "tok-x", "platform": "android"},
        headers={"X-User-Id": USER_A},
    )
    resp = client.delete("/notifications/tokens/tok-x", headers={"X-User-Id": USER_A})
    assert resp.status_code == 204
    assert db.query(DeviceToken).count() == 0


def test_delete_unknown_token_is_noop(client):
    resp = client.delete("/notifications/tokens/nope", headers={"X-User-Id": USER_A})
    assert resp.status_code == 204

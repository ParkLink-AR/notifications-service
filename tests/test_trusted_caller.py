from app.config import settings


def test_rejects_direct_calls_when_secrets_are_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "GATEWAY_INTERNAL_SECRET", "gw-secret")
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_KEY", "internal-key")

    response = client.get("/livez")
    assert response.status_code == 200

    spoofed = client.put("/notifications/tokens", headers={"X-User-Id": "someone"}, json={})
    assert spoofed.status_code == 401
    assert spoofed.json()["code"] == "UNTRUSTED_CALLER"


def test_accepts_gateway_and_internal_callers(client, monkeypatch):
    monkeypatch.setattr(settings, "GATEWAY_INTERNAL_SECRET", "gw-secret")
    monkeypatch.setattr(settings, "INTERNAL_SERVICE_KEY", "internal-key")

    via_gateway = client.put("/notifications/tokens", headers={"X-Gateway-Secret": "gw-secret"}, json={})
    assert via_gateway.headers.get("content-type", "").startswith("application")
    assert "UNTRUSTED_CALLER" not in via_gateway.text

    internal = client.put("/notifications/tokens", headers={"X-Internal-Key": "internal-key"}, json={})
    assert "UNTRUSTED_CALLER" not in internal.text

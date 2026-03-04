from app.core import redis as redis_module


def test_health_ok(client, monkeypatch):
    async def fake_ping():
        return True

    monkeypatch.setattr(redis_module.redis_client, "ping", fake_ping)

    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["redis_connected"] is True


def test_health_redis_down(client, monkeypatch):
    async def fake_ping():
        raise RuntimeError("redis down")

    monkeypatch.setattr(redis_module.redis_client, "ping", fake_ping)

    response = client.get("/health")
    assert response.status_code == 503
    assert "Health check failed" in response.json()["detail"]

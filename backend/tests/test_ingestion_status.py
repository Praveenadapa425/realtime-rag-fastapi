from app.core import redis as redis_module


def test_ingestion_status_not_found(client, monkeypatch):
    async def fake_hgetall(key):
        return {}

    monkeypatch.setattr(redis_module.redis_client, "hgetall", fake_hgetall)

    response = client.get("/ingest/status/non-existent-task")
    assert response.status_code == 404


def test_ingestion_status_ok(client, monkeypatch):
    async def fake_hgetall(key):
        return {
            "task_id": "task-123",
            "filename": "sample.txt",
            "status": "indexed",
            "message": "Document indexed and searchable",
            "retries": "0",
            "updated_at": "2026-03-04T00:00:00+00:00",
        }

    monkeypatch.setattr(redis_module.redis_client, "hgetall", fake_hgetall)

    response = client.get("/ingest/status/task-123")
    assert response.status_code == 200

    payload = response.json()
    assert payload["task_id"] == "task-123"
    assert payload["status"] == "indexed"
    assert payload["filename"] == "sample.txt"

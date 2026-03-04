from app.core import redis as redis_module


def test_ingest_txt_file_success(client, monkeypatch):
    async def fake_rpush(queue, message):
        return 1

    monkeypatch.setattr(redis_module.redis_client, "rpush", fake_rpush)

    files = {"file": ("sample.txt", b"hello rag", "text/plain")}
    response = client.post("/ingest", files=files)

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Document ingestion initiated"
    assert payload["filename"] == "sample.txt"


def test_ingest_invalid_extension(client, monkeypatch):
    async def fake_rpush(queue, message):
        return 1

    monkeypatch.setattr(redis_module.redis_client, "rpush", fake_rpush)

    files = {"file": ("sample.exe", b"payload", "application/octet-stream")}
    response = client.post("/ingest", files=files)

    assert response.status_code == 400
    assert "File type not allowed" in response.json()["detail"]

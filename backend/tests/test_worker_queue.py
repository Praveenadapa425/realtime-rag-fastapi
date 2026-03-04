import json
import pytest

from worker import worker as worker_module


class FakeRedis:
    def __init__(self):
        self.processed = set()
        self.pushed = []

    async def sismember(self, key, value):
        return value in self.processed

    async def sadd(self, key, value):
        self.processed.add(value)
        return 1

    async def rpush(self, key, value):
        self.pushed.append((key, value))
        return len(self.pushed)


@pytest.mark.asyncio
async def test_process_queue_item_marks_success_as_processed(monkeypatch):
    redis_client = FakeRedis()

    async def fake_process_document(path, filename):
        return True

    monkeypatch.setattr(worker_module, "process_document", fake_process_document)

    data = {
        "path": "uploads/a.txt",
        "filename": "a.txt",
        "content_hash": "hash1",
        "retries": 0,
    }

    handled = await worker_module.process_queue_item(redis_client, data)

    assert handled is True
    assert "a.txt:hash1" in redis_client.processed
    assert redis_client.pushed == []


@pytest.mark.asyncio
async def test_process_queue_item_requeues_on_retryable_failure(monkeypatch):
    redis_client = FakeRedis()

    async def fake_process_document(path, filename):
        return False

    monkeypatch.setattr(worker_module, "process_document", fake_process_document)

    data = {
        "path": "uploads/b.txt",
        "filename": "b.txt",
        "content_hash": "hash2",
        "retries": 1,
    }

    handled = await worker_module.process_queue_item(redis_client, data)

    assert handled is False
    assert len(redis_client.pushed) == 1
    queue, payload = redis_client.pushed[0]
    assert queue == worker_module.INGESTION_QUEUE_KEY
    assert json.loads(payload)["retries"] == 2


@pytest.mark.asyncio
async def test_process_queue_item_moves_to_dead_letter_after_max_retries(monkeypatch):
    redis_client = FakeRedis()

    async def fake_process_document(path, filename):
        return False

    monkeypatch.setattr(worker_module, "process_document", fake_process_document)

    data = {
        "path": "uploads/c.txt",
        "filename": "c.txt",
        "content_hash": "hash3",
        "retries": worker_module.MAX_RETRIES,
    }

    handled = await worker_module.process_queue_item(redis_client, data)

    assert handled is True
    assert len(redis_client.pushed) == 1
    queue, payload = redis_client.pushed[0]
    assert queue == worker_module.DEAD_LETTER_QUEUE_KEY
    assert json.loads(payload)["filename"] == "c.txt"


@pytest.mark.asyncio
async def test_process_queue_item_skips_idempotent_duplicates(monkeypatch):
    redis_client = FakeRedis()
    redis_client.processed.add("d.txt:hash4")

    async def fake_process_document(path, filename):
        raise AssertionError("process_document should not be called for duplicate")

    monkeypatch.setattr(worker_module, "process_document", fake_process_document)

    data = {
        "path": "uploads/d.txt",
        "filename": "d.txt",
        "content_hash": "hash4",
        "retries": 0,
    }

    handled = await worker_module.process_queue_item(redis_client, data)

    assert handled is True
    assert redis_client.pushed == []

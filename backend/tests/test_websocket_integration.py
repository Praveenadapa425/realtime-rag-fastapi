from app.rag.generator import StreamToken


class DummyResult:
    def to_dict(self):
        return {
            "chunk": "RAG is retrieval augmented generation",
            "source": "sample.txt",
            "chunk_id": 0,
            "similarity_score": 0.99,
            "metadata": {"source": "sample.txt", "chunk": 0},
        }


def test_websocket_streams_tokens_and_complete(client, monkeypatch):
    async def fake_retrieve_context(query):
        return [DummyResult()], "context"

    async def fake_generate_streaming_response(query, context, retrieved_chunks):
        yield StreamToken("Hello", "token")
        yield StreamToken(" ", "token")
        yield StreamToken("World", "token", citations=[{"source": "sample.txt", "chunk_id": 0}])
        yield StreamToken("", "complete")

    monkeypatch.setattr("app.rag.retriever.retrieve_context", fake_retrieve_context)
    monkeypatch.setattr("app.rag.generator.generate_streaming_response", fake_generate_streaming_response)

    with client.websocket_connect("/query") as ws:
        ws.send_text("What is RAG?")

        msg1 = ws.receive_json()
        assert msg1["type"] == "token"
        assert "payload" in msg1

        ws.close()

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


def test_websocket_streams_citations_and_complete_order(client, monkeypatch):
    async def fake_retrieve_context(query):
        return [DummyResult()], "context"

    async def fake_generate_streaming_response(query, context, retrieved_chunks):
        yield StreamToken("Hello", "token")
        yield StreamToken(
            {
                "source": "sample.txt",
                "chunk_id": 0,
                "similarity": 0.99,
                "sentence": "Hello world.",
                "method": "sentence_overlap",
            },
            "citation",
        )
        yield StreamToken("World", "token")
        yield StreamToken("", "complete")

    monkeypatch.setattr("app.rag.retriever.retrieve_context", fake_retrieve_context)
    monkeypatch.setattr("app.rag.generator.generate_streaming_response", fake_generate_streaming_response)

    with client.websocket_connect("/query") as ws:
        ws.send_text("What is RAG?")

        received_types = []
        citation_payload = None
        while True:
            message = ws.receive_json()
            received_types.append(message["type"])

            if message["type"] == "citation":
                citation_payload = message["payload"]

            if message["type"] in {"complete", "error"}:
                break

        assert "token" in received_types
        assert "citation" in received_types
        assert received_types[-1] == "complete"
        assert received_types.index("citation") < received_types.index("complete")
        assert citation_payload["source"] == "sample.txt"


def test_websocket_stream_failure_sends_single_terminal_error(client, monkeypatch):
    async def fake_retrieve_context(query):
        return [DummyResult()], "context"

    async def fake_generate_streaming_response(query, context, retrieved_chunks):
        yield StreamToken("Hello", "token")
        raise RuntimeError("simulated failure")

    monkeypatch.setattr("app.rag.retriever.retrieve_context", fake_retrieve_context)
    monkeypatch.setattr("app.rag.generator.generate_streaming_response", fake_generate_streaming_response)

    with client.websocket_connect("/query") as ws:
        ws.send_text("Trigger stream error")

        terminal_events = []
        while True:
            message = ws.receive_json()
            if message["type"] in {"complete", "error"}:
                terminal_events.append(message)
                break

        assert len(terminal_events) == 1
        assert terminal_events[0]["type"] == "error"
        assert terminal_events[0]["payload"]["code"] in {"GENERATION_ERROR", "RAG_PIPELINE_ERROR"}

        ws.close()

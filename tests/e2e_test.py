import asyncio
import websockets
import json

async def run_test():
    uri = "ws://localhost:8000/query"
    async with websockets.connect(uri) as ws:
        query = "What is RAG?"
        await ws.send(query)
        print(f"Sent query: {query}")
        try:
            while True:
                msg = await ws.recv()
                print(f"Received: {msg}")
                data = json.loads(msg)
                if data.get("type") == "complete":
                    print("Stream complete")
                    break
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed")

if __name__ == "__main__":
    asyncio.run(run_test())

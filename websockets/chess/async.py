import asyncio
import websockets
import json
from collections import Counter


class Codes:
    update = "(:UPDATE:)"
    group = "(:GRP:)"
    message = "(:MSG:)"


class ChessServer:
    def __init__(self, host="localhost", port=1234):
        self.host = host
        self.port = port
        self.clients = {}  # Maps websockets to client details

    async def start(self):
        async with websockets.serve(self.handle_connection, self.host, self.port):
            print(f"Server started on port {self.port}")
            await asyncio.Future()  # Run forever

    async def handle_connection(self, websocket):
        try:
            print(f"Client connected: {websocket.remote_address}")
            self.clients[websocket] = {}

            async for message in websocket:
                await self.handle_text_message(websocket, message)
        except websockets.ConnectionClosed:
            pass
        finally:
            await self.handle_disconnected(websocket)

    async def handle_text_message(self, websocket, message: str):
        if message.startswith(Codes.group):
            print(":GRP: message received")
            self.clients[websocket]["group"] = message.split(Codes.group)[1]
            return
        if message.startswith(Codes.update):
            print(":UPDATE: message received")
            available_groups = self.get_available_groups()
            await websocket.send(Codes.update + json.dumps(available_groups))
            return
        if message.startswith(Codes.message):
            print(":MSG: message received")
            for client_websocket, client_info in self.clients.items():
                if (
                    client_info.get("group") == self.clients[websocket].get("group")
                    and client_websocket != websocket
                ):
                    print(
                        f"Sending message to group: {self.clients[websocket]['group']}"
                    )
                    await client_websocket.send(message)
        print(f"Received message: {message}")

    def get_available_groups(self):
        group_names = [
            info.get("group") for info in self.clients.values() if info.get("group")
        ]
        group_counter = dict(Counter(group_names))
        available = [group for group, count in group_counter.items() if count == 1]
        return available

    async def handle_disconnected(self, websocket):
        if websocket in self.clients:
            self.clients.pop(websocket)
            print("Client disconnected")


if __name__ == "__main__":
    server = ChessServer()
    asyncio.run(server.start())

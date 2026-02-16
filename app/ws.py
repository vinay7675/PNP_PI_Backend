from fastapi import WebSocket
from typing import List

class WSManager:
    def __init__(self):
        self.clients: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.clients.append(ws)

    def disconnect(self, ws: WebSocket):
        self.clients.remove(ws)

    async def broadcast(self, message: dict):
        for ws in self.clients:
            try:
                await ws.send_json(message)
            except:
                pass

ws_manager = WSManager()

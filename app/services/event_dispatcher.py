from typing import Set
from fastapi import WebSocket


class EventDispatcher:
    def __init__(self):
        self._clients: Set[WebSocket] = set()

    async def register(self, ws: WebSocket):
        await ws.accept()
        self._clients.add(ws)

    async def unregister(self, ws: WebSocket):
        if ws in self._clients:
            self._clients.remove(ws)

    async def broadcast_json(self, data):
        for ws in list(self._clients):
            try:
                await ws.send_json(data)
            except Exception:
                await self.unregister(ws)


dispatcher = EventDispatcher()

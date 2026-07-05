"""WebSocket connection manager: admin channel, per-order channels, menu channel."""
from typing import Dict, Set

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.admin: Set[WebSocket] = set()
        self.orders: Dict[int, Set[WebSocket]] = {}
        self.menu: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket, pool: Set[WebSocket]) -> None:
        await ws.accept()
        pool.add(ws)

    def disconnect(self, ws: WebSocket, pool: Set[WebSocket]) -> None:
        pool.discard(ws)

    async def _broadcast(self, pool: Set[WebSocket], data: dict) -> None:
        dead = []
        for ws in list(pool):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            pool.discard(ws)

    async def broadcast_admin(self, data: dict) -> None:
        await self._broadcast(self.admin, data)

    async def broadcast_menu(self, data: dict) -> None:
        await self._broadcast(self.menu, data)

    async def send_order(self, order_id: int, data: dict) -> None:
        await self._broadcast(self.orders.get(order_id, set()), data)


manager = ConnectionManager()

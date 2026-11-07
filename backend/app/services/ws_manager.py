"""WebSocket connection manager: admin channel, per-customer channels, menu channel."""
from typing import Dict, Set

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.admin: Set[WebSocket] = set()
        self.customers: Dict[int, Set[WebSocket]] = {}  # customer id -> their open tabs/devices
        self.menu: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket, pool: Set[WebSocket]) -> None:
        await ws.accept()
        pool.add(ws)

    def disconnect(self, ws: WebSocket, pool: Set[WebSocket]) -> None:
        pool.discard(ws)

    async def join_customer(self, ws: WebSocket, customer_id: int) -> None:
        await ws.accept()  # accept first so the pool can't be dropped while we await
        self.customers.setdefault(customer_id, set()).add(ws)

    def leave_customer(self, ws: WebSocket, customer_id: int) -> None:
        pool = self.customers.get(customer_id, set())
        pool.discard(ws)
        if not pool:
            self.customers.pop(customer_id, None)  # don't keep empty sets forever

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

    async def send_customer(self, customer_id: int, data: dict) -> None:
        await self._broadcast(self.customers.get(customer_id, set()), data)


manager = ConnectionManager()

"""Live channels: /ws/admin (owner), /ws/me (one customer's orders), /ws/menu (everyone)."""
import asyncio
import time
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.shared import auth
from app.shared.ws_manager import manager

router = APIRouter()


async def _listen(ws: WebSocket, expires: Optional[float] = None) -> None:
    """Hold the socket open until the client leaves — or, for a logged-in channel, until its
    token expires: then close with 4401, as a REST call would get 401 (the app logs out)."""
    try:
        while True:
            timeout = None if expires is None else max(0.0, expires - time.time())
            await asyncio.wait_for(ws.receive_text(), timeout)
    except asyncio.TimeoutError:
        await ws.close(code=4401)
    except WebSocketDisconnect:
        pass


@router.websocket("/ws/admin")
async def ws_admin(ws: WebSocket) -> None:
    session = auth.ws_session(ws.query_params.get("token", ""), admin=True)
    if session is None:
        await ws.close(code=4401)
        return
    await manager.connect(ws, manager.admin)
    try:
        await _listen(ws, session["exp"])
    finally:  # any exit (not just a clean disconnect) leaves the pool
        manager.disconnect(ws, manager.admin)


@router.websocket("/ws/me")
async def ws_me(ws: WebSocket) -> None:
    """The logged-in customer's channel: status changes for all of their orders."""
    session = auth.ws_session(ws.query_params.get("token", ""))
    if session is None:
        await ws.close(code=4401)
        return
    cid = session["cid"]
    await manager.join_customer(ws, cid)
    try:
        await _listen(ws, session["exp"])
    finally:
        manager.leave_customer(ws, cid)


@router.websocket("/ws/menu")
async def ws_menu(ws: WebSocket) -> None:
    await manager.connect(ws, manager.menu)
    try:
        await _listen(ws)
    finally:
        manager.disconnect(ws, manager.menu)

"""Live channels: /ws/admin (owner), /ws/me (one customer's orders), /ws/menu (everyone)."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...core import auth
from ...services.ws_manager import manager

router = APIRouter()


@router.websocket("/ws/admin")
async def ws_admin(ws: WebSocket) -> None:
    if not auth.token_is_admin(ws.query_params.get("token", "")):
        await ws.close(code=4401)
        return
    await manager.connect(ws, manager.admin)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws, manager.admin)


@router.websocket("/ws/me")
async def ws_me(ws: WebSocket) -> None:
    """The logged-in customer's channel: status changes for all of their orders."""
    cid = auth.token_customer_id(ws.query_params.get("token", ""))
    if cid is None:
        await ws.close(code=4401)
        return
    await manager.join_customer(ws, cid)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.leave_customer(ws, cid)


@router.websocket("/ws/menu")
async def ws_menu(ws: WebSocket) -> None:
    await manager.connect(ws, manager.menu)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws, manager.menu)

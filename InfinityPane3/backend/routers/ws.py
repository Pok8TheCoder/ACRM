"""WebSocket router — real-time canvas collaboration endpoint."""

from __future__ import annotations
import json
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from collab.room import manager

router = APIRouter()


@router.websocket("/ws/{institution_id}")
async def canvas_ws(
    ws: WebSocket,
    institution_id: str,
    user_id: str = Query("anonymous"),
    user_name: str = Query("Anonymous"),
):
    """
    WebSocket endpoint for real-time canvas collaboration.
    
    Room ID = institution_id (one shared canvas per institution, multiple users).
    On connect: sends FULL_STATE + current user list.
    On message: validates op and broadcasts to all other users in the room.
    On disconnect: releases locks and announces departure.
    """
    room = manager.get_or_create(institution_id)
    await room.connect(user_id, user_name, ws)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                op = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # Stamp server-side timestamp
            op["timestamp"] = time.time()
            op["user_id"] = user_id  # enforce server-side user identity

            await room.handle_op(op, sender_id=user_id)

    except WebSocketDisconnect:
        await room.disconnect(user_id)
        manager.cleanup_empty()

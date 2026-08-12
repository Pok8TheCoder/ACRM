"""
Collaboration room manager.
Tracks connected users and canvas state for each active room.
Broadcasts operations to all users in a room (Last-Write-Wins + soft locks).
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Optional

from fastapi import WebSocket


COLORS = [
    "#6366f1", "#ec4899", "#f59e0b", "#10b981",
    "#3b82f6", "#8b5cf6", "#ef4444", "#06b6d4",
]


@dataclass
class ConnectedUser:
    user_id: str
    user_name: str
    color: str
    ws: WebSocket
    cursor: dict = field(default_factory=lambda: {"x": 0, "y": 0})
    locked_node: Optional[str] = None
    joined_at: float = field(default_factory=time.time)


class CanvasRoom:
    """
    One room = one institution's canvas session.
    Holds the live canvas state and all connected websockets.
    """

    def __init__(self, room_id: str):
        self.room_id = room_id
        self.users: dict[str, ConnectedUser] = {}
        # Last known full canvas state (dict, matches CanvasState schema)
        self.canvas_state: dict = {
            "nodes": [],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        }
        self._color_index = 0

    def _next_color(self) -> str:
        color = COLORS[self._color_index % len(COLORS)]
        self._color_index += 1
        return color

    async def connect(self, user_id: str, user_name: str, ws: WebSocket):
        await ws.accept()
        color = self._next_color()
        user = ConnectedUser(user_id=user_id, user_name=user_name, color=color, ws=ws)
        self.users[user_id] = user

        # Send full canvas state + current user list to the newcomer
        await ws.send_json({
            "type": "FULL_STATE",
            "user_id": "server",
            "user_name": "server",
            "user_color": "#ffffff",
            "timestamp": time.time(),
            "state": self.canvas_state,
            "users": self._users_list(exclude=user_id),
            "you": {"user_id": user_id, "user_name": user_name, "color": color},
        })

        # Announce join to others
        await self.broadcast({
            "type": "USER_JOINED",
            "user_id": user_id,
            "user_name": user_name,
            "user_color": color,
            "timestamp": time.time(),
        }, exclude=user_id)

    async def disconnect(self, user_id: str):
        user = self.users.pop(user_id, None)
        if user and user.locked_node:
            # Release any lock this user held
            await self.broadcast({
                "type": "UNLOCK_NODE",
                "user_id": user_id,
                "user_name": user.user_name,
                "user_color": user.color,
                "node_id": user.locked_node,
                "timestamp": time.time(),
            })
        await self.broadcast({
            "type": "USER_LEFT",
            "user_id": user_id,
            "user_name": user.user_name if user else user_id,
            "user_color": user.color if user else "#ffffff",
            "timestamp": time.time(),
        })

    async def handle_op(self, op: dict, sender_id: str):
        """Apply an operation to room state and broadcast to all others."""
        op_type = op.get("type")
        user = self.users.get(sender_id)
        if not user:
            return

        # Apply state mutations (Last-Write-Wins)
        if op_type == "MOVE_NODE":
            node_id = op.get("node_id")
            for node in self.canvas_state.get("nodes", []):
                if node.get("id") == node_id:
                    node["position"] = {"x": op["x"], "y": op["y"]}
                    break

        elif op_type == "RESIZE_NODE":
            node_id = op.get("node_id")
            for node in self.canvas_state.get("nodes", []):
                if node.get("id") == node_id:
                    node["width"] = op.get("width", node.get("width"))
                    node["height"] = op.get("height", node.get("height"))
                    break

        elif op_type == "ADD_NODE":
            self.canvas_state.setdefault("nodes", []).append(op["node"])

        elif op_type == "DELETE_NODE":
            node_id = op.get("node_id")
            self.canvas_state["nodes"] = [
                n for n in self.canvas_state.get("nodes", []) if n.get("id") != node_id
            ]

        elif op_type == "ADD_EDGE":
            self.canvas_state.setdefault("edges", []).append(op["edge"])

        elif op_type == "DELETE_EDGE":
            edge_id = op.get("edge_id")
            self.canvas_state["edges"] = [
                e for e in self.canvas_state.get("edges", []) if e.get("id") != edge_id
            ]

        elif op_type == "ASSIGN_CELL":
            node_id = op.get("node_id")
            cell_key = op.get("cell_key")
            for node in self.canvas_state.get("nodes", []):
                if node.get("id") == node_id:
                    node.setdefault("data", {}).setdefault("cells", {})[cell_key] = op.get("assignment")
                    if op.get("slot_span", 1) > 1:
                        node["data"].setdefault("lab_spans", {})[cell_key] = op["slot_span"]
                    break

        elif op_type == "CLEAR_CELL":
            node_id = op.get("node_id")
            cell_key = op.get("cell_key")
            for node in self.canvas_state.get("nodes", []):
                if node.get("id") == node_id:
                    node.setdefault("data", {}).setdefault("cells", {}).pop(cell_key, None)
                    node["data"].get("lab_spans", {}).pop(cell_key, None)
                    break

        elif op_type == "LOCK_NODE":
            user.locked_node = op.get("node_id")

        elif op_type == "UNLOCK_NODE":
            user.locked_node = None

        elif op_type == "CURSOR_MOVE":
            user.cursor = {"x": op.get("x", 0), "y": op.get("y", 0)}

        elif op_type == "FULL_STATE":
            # Client pushing a full save
            self.canvas_state = op.get("state", self.canvas_state)

        elif op_type == "PING":
            await user.ws.send_json({"type": "PONG", "timestamp": time.time()})
            return

        # Broadcast to all other users
        await self.broadcast(op, exclude=sender_id)

    async def broadcast(self, message: dict, exclude: Optional[str] = None):
        """Send a message to all connected users (optionally excluding one)."""
        dead = []
        payload = json.dumps(message)
        for uid, user in self.users.items():
            if uid == exclude:
                continue
            try:
                await user.ws.send_text(payload)
            except Exception:
                dead.append(uid)
        for uid in dead:
            self.users.pop(uid, None)

    def _users_list(self, exclude: Optional[str] = None) -> list[dict]:
        return [
            {
                "user_id": u.user_id,
                "user_name": u.user_name,
                "color": u.color,
                "cursor": u.cursor,
            }
            for uid, u in self.users.items()
            if uid != exclude
        ]

    @property
    def user_count(self) -> int:
        return len(self.users)


class RoomManager:
    """Global registry of all active canvas rooms."""

    def __init__(self):
        self._rooms: dict[str, CanvasRoom] = {}

    def get_or_create(self, room_id: str) -> CanvasRoom:
        if room_id not in self._rooms:
            self._rooms[room_id] = CanvasRoom(room_id)
        return self._rooms[room_id]

    def load_state(self, room_id: str, state: dict):
        """Pre-load canvas state into a room (called on first load from DB)."""
        room = self.get_or_create(room_id)
        room.canvas_state = state

    def get_state(self, room_id: str) -> dict:
        room = self._rooms.get(room_id)
        return room.canvas_state if room else {}

    def cleanup_empty(self):
        self._rooms = {rid: room for rid, room in self._rooms.items() if room.user_count > 0}


# Singleton
manager = RoomManager()

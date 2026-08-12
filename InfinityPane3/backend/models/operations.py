"""WebSocket operation models for real-time collaboration."""

from __future__ import annotations
from typing import Optional, Literal, Any
from pydantic import BaseModel


OpType = Literal[
    "MOVE_NODE",
    "RESIZE_NODE",
    "ADD_NODE",
    "DELETE_NODE",
    "ADD_EDGE",
    "DELETE_EDGE",
    "ASSIGN_CELL",
    "CLEAR_CELL",
    "CURSOR_MOVE",
    "LOCK_NODE",
    "UNLOCK_NODE",
    "USER_JOINED",
    "USER_LEFT",
    "FULL_STATE",
    "PING",
]


class BaseOp(BaseModel):
    type: OpType
    user_id: str
    user_name: str = ""
    user_color: str = "#6366f1"
    timestamp: float = 0.0


class MoveNodeOp(BaseOp):
    type: Literal["MOVE_NODE"] = "MOVE_NODE"
    node_id: str
    x: float
    y: float


class ResizeNodeOp(BaseOp):
    type: Literal["RESIZE_NODE"] = "RESIZE_NODE"
    node_id: str
    width: float
    height: float


class AddNodeOp(BaseOp):
    type: Literal["ADD_NODE"] = "ADD_NODE"
    node: dict[str, Any]


class DeleteNodeOp(BaseOp):
    type: Literal["DELETE_NODE"] = "DELETE_NODE"
    node_id: str


class AddEdgeOp(BaseOp):
    type: Literal["ADD_EDGE"] = "ADD_EDGE"
    edge: dict[str, Any]


class DeleteEdgeOp(BaseOp):
    type: Literal["DELETE_EDGE"] = "DELETE_EDGE"
    edge_id: str


class AssignCellOp(BaseOp):
    type: Literal["ASSIGN_CELL"] = "ASSIGN_CELL"
    node_id: str
    cell_key: str
    assignment: Optional[dict[str, Any]]
    slot_span: int = 1


class ClearCellOp(BaseOp):
    type: Literal["CLEAR_CELL"] = "CLEAR_CELL"
    node_id: str
    cell_key: str


class CursorMoveOp(BaseOp):
    type: Literal["CURSOR_MOVE"] = "CURSOR_MOVE"
    x: float
    y: float


class LockNodeOp(BaseOp):
    type: Literal["LOCK_NODE"] = "LOCK_NODE"
    node_id: str


class UnlockNodeOp(BaseOp):
    type: Literal["UNLOCK_NODE"] = "UNLOCK_NODE"
    node_id: str


class UserJoinedOp(BaseOp):
    type: Literal["USER_JOINED"] = "USER_JOINED"


class UserLeftOp(BaseOp):
    type: Literal["USER_LEFT"] = "USER_LEFT"


class FullStateOp(BaseOp):
    type: Literal["FULL_STATE"] = "FULL_STATE"
    state: dict[str, Any]
    users: list[dict[str, Any]] = []

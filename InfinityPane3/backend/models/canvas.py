"""Pydantic models for canvas state."""

from __future__ import annotations
from typing import Optional, Literal, Any
from pydantic import BaseModel, Field
import uuid


def new_id(prefix: str = "node") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


# ──────────────────────────────────────────────
# Cell assignment inside a timetable block
# ──────────────────────────────────────────────

class CellAssignment(BaseModel):
    faculty_id: str
    faculty_name: str
    subject_id: str
    subject_code: str
    subject_name: str
    room_id: Optional[str] = None
    room_number: Optional[str] = None
    color: str = "#6366f1"
    conflict: bool = False


# Key format: "Monday-0", "Tuesday-2" etc.
CellKey = str


class TimetableConfig(BaseModel):
    """Configuration and cell data for one timetable block."""
    class_id: str
    class_name: str = ""
    days: list[str] = Field(default_factory=lambda: [
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"
    ])
    slots_per_day: int = 8
    slot_duration: int = 60          # minutes
    start_time: str = "09:00"
    break_slots: list[int] = Field(default_factory=list)  # slot indices that are breaks
    # cells: { "Monday-0": CellAssignment | null }
    cells: dict[CellKey, Optional[CellAssignment]] = Field(default_factory=dict)
    # lab_spans: { "Monday-0": 2 } means cell Mon-0 spans 2 rows
    lab_spans: dict[CellKey, int] = Field(default_factory=dict)


# ──────────────────────────────────────────────
# React Flow node / edge wrappers
# ──────────────────────────────────────────────

class NodePosition(BaseModel):
    x: float
    y: float


class CanvasNode(BaseModel):
    id: str = Field(default_factory=lambda: new_id("node"))
    type: Literal["timetable", "group", "faculty", "subject", "text", "structure"]
    position: NodePosition
    data: dict[str, Any] = Field(default_factory=dict)
    width: Optional[float] = None
    height: Optional[float] = None
    parent_id: Optional[str] = None   # for grouping


class CanvasEdge(BaseModel):
    id: str = Field(default_factory=lambda: new_id("edge"))
    source: str          # node id
    source_handle: Optional[str] = None
    target: str          # node id
    target_handle: Optional[str] = None
    type: str = "assignment"
    label: Optional[str] = None
    data: dict[str, Any] = Field(default_factory=dict)


# ──────────────────────────────────────────────
# Full canvas state (what we persist)
# ──────────────────────────────────────────────

class CanvasState(BaseModel):
    institution_id: str
    session_name: str = "Untitled Session"
    nodes: list[CanvasNode] = Field(default_factory=list)
    edges: list[CanvasEdge] = Field(default_factory=list)
    viewport: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0, "zoom": 1})


# ──────────────────────────────────────────────
# Request/response shapes for API
# ──────────────────────────────────────────────

class AssignCellRequest(BaseModel):
    node_id: str
    cell_key: CellKey
    assignment: Optional[CellAssignment]   # None = clear cell
    slot_span: int = 1                      # 1 = normal, 2+ = lab block


class SaveCanvasRequest(BaseModel):
    institution_id: str
    session_name: str = "Untitled Session"
    canvas: CanvasState


class LoadCanvasResponse(BaseModel):
    session_id: int
    session_name: str
    canvas: CanvasState
    saved_at: str

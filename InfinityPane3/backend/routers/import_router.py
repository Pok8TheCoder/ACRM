"""CSV/XLSX bulk import router — validates against ACRM DB and returns a canvas patch."""

from __future__ import annotations
import csv
import io
import json
import uuid
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from routes.database import get_db_connection

router = APIRouter()

DAYS_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@router.post("/csv")
async def import_csv(
    file: UploadFile = File(...),
    institution_id: str = Query("iit_delhi"),
    mode: str = Query("auto"),  # "auto" | "preview"
):
    """
    Accept a CSV file and validate it against ACRM data.

    Expected columns (flexible):
      faculty_id, subject_code, class_id, day, slot, slot_span (optional), room_id (optional)

    Returns:
      - valid_rows: list of confirmed assignments
      - conflicts: list of issues found
      - canvas_patch: React-Flow-ready node list (one timetable node per class)
    """
    try:
        content = (await file.read()).decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "Could not decode file — ensure UTF-8 encoding")

    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    if not rows:
        raise HTTPException(400, "CSV file is empty")

    # Normalise header names (strip, lowercase)
    norm_rows = []
    for r in rows:
        norm_rows.append({k.strip().lower(): v.strip() for k, v in r.items()})

    # Load ACRM reference data for validation
    with get_db_connection(institution_id, "student") as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id, faculty_id, first_name, last_name FROM faculty WHERE institution_id = ?", (institution_id,))
        faculty_map = {r["faculty_id"]: r for r in cursor.fetchall()}

        cursor.execute("SELECT id, subject_id, name FROM subjects WHERE institution_id = ?", (institution_id,))
        subject_map = {r["subject_id"]: r for r in cursor.fetchall()}

        cursor.execute("SELECT id, class_id, class_name FROM classes WHERE institution_id = ?", (institution_id,))
        class_map = {r["class_id"]: r for r in cursor.fetchall()}

        cursor.execute("SELECT id, room_number FROM campus_rooms WHERE institution_id = ?", (institution_id,))
        room_map = {r["room_number"]: r for r in cursor.fetchall()}

    valid_rows = []
    conflicts = []

    # Group by class_id for canvas layout
    class_assignments: dict[str, list] = {}

    for i, row in enumerate(norm_rows, start=2):  # start=2 accounting for header
        line_errors = []

        faculty_id = row.get("faculty_id", "").strip()
        subject_code = row.get("subject_code", "").strip()
        class_id = row.get("class_id", "").strip()
        day = row.get("day", "").strip().capitalize()
        slot_raw = row.get("slot", "").strip()
        slot_span = int(row.get("slot_span", "1") or "1")
        room_id_str = row.get("room_id", "").strip()

        # Validate each field
        if faculty_id not in faculty_map:
            line_errors.append(f"Faculty '{faculty_id}' not found")
        if subject_code not in subject_map:
            line_errors.append(f"Subject '{subject_code}' not found")
        if class_id not in class_map:
            line_errors.append(f"Class '{class_id}' not found")
        if day not in DAYS_ORDER:
            line_errors.append(f"Day '{day}' invalid (use Monday, Tuesday ...)")
        try:
            slot_index = int(slot_raw)
        except ValueError:
            line_errors.append(f"Slot '{slot_raw}' must be an integer")
            slot_index = -1

        if line_errors:
            conflicts.append({"row": i, "errors": line_errors, "data": row})
            continue

        fac = faculty_map[faculty_id]
        sub = subject_map[subject_code]
        cls = class_map[class_id]
        room = room_map.get(room_id_str)

        assignment = {
            "faculty_id": faculty_id,
            "faculty_name": f"{fac['first_name']} {fac['last_name']}".strip(),
            "subject_id": subject_code,
            "subject_code": subject_code,
            "subject_name": sub["name"],
            "room_id": str(room["id"]) if room else None,
            "room_number": room_id_str if room else None,
            "color": _subject_color(sub["id"]),
            "conflict": False,
        }

        cell_key = f"{day}-{slot_index}"
        valid_rows.append({
            "class_id": class_id,
            "class_name": cls["class_name"],
            "cell_key": cell_key,
            "slot_span": slot_span,
            "assignment": assignment,
        })

        class_assignments.setdefault(class_id, []).append({
            "cell_key": cell_key,
            "slot_span": slot_span,
            "assignment": assignment,
            "class_name": cls["class_name"],
        })

    # Build canvas patch — one timetable node per class, laid out in a grid
    canvas_nodes = []
    col_count = 4
    node_width = 760
    node_height = 400
    gap_x = 80
    gap_y = 60

    for idx, (class_id, assignments) in enumerate(class_assignments.items()):
        col = idx % col_count
        row_num = idx // col_count
        x = col * (node_width + gap_x)
        y = row_num * (node_height + gap_y)

        cells = {}
        lab_spans = {}
        for a in assignments:
            cells[a["cell_key"]] = a["assignment"]
            if a["slot_span"] > 1:
                lab_spans[a["cell_key"]] = a["slot_span"]

        node = {
            "id": f"tt_{uuid.uuid4().hex[:8]}",
            "type": "timetable",
            "position": {"x": x, "y": y},
            "data": {
                "class_id": class_id,
                "class_name": assignments[0]["class_name"],
                "days": DAYS_ORDER[:6],
                "slots_per_day": 8,
                "slot_duration": 60,
                "start_time": "09:00",
                "break_slots": [],
                "cells": cells,
                "lab_spans": lab_spans,
            },
        }
        canvas_nodes.append(node)

    return {
        "status": "ok",
        "rows_processed": len(rows),
        "valid_count": len(valid_rows),
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "canvas_patch": canvas_nodes,
    }


def _subject_color(subject_db_id: int) -> str:
    """Generate a stable color for a subject based on its ID."""
    palette = [
        "#6366f1", "#ec4899", "#f59e0b", "#10b981", "#3b82f6",
        "#8b5cf6", "#ef4444", "#06b6d4", "#84cc16", "#f97316",
    ]
    return palette[subject_db_id % len(palette)]

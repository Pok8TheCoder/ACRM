"""Canvas persistence router — save/load canvas sessions to ACRM's student.db."""

from __future__ import annotations
import json
from fastapi import APIRouter, HTTPException, Query
from routes.database import get_db_connection
from models.canvas import CanvasState, SaveCanvasRequest

router = APIRouter()


def _ensure_canvas_table(institution_id: str):
    """Create canvas_sessions table if it doesn't exist."""
    with get_db_connection(institution_id, "student") as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS canvas_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                institution_id TEXT NOT NULL,
                session_name TEXT NOT NULL DEFAULT 'Untitled Session',
                canvas_json TEXT NOT NULL,
                saved_by TEXT,
                saved_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


@router.get("/sessions")
def list_sessions(institution_id: str = Query("iit_delhi")):
    """List all saved canvas sessions for an institution."""
    _ensure_canvas_table(institution_id)
    with get_db_connection(institution_id, "student") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, session_name, saved_by, saved_at
            FROM canvas_sessions
            WHERE institution_id = ?
            ORDER BY saved_at DESC
        """, (institution_id,))
        rows = cursor.fetchall()
    return [
        {
            "session_id": r["id"],
            "session_name": r["session_name"],
            "saved_by": r.get("saved_by"),
            "saved_at": r["saved_at"],
        }
        for r in rows
    ]


@router.get("/sessions/{session_id}")
def load_session(session_id: int, institution_id: str = Query("iit_delhi")):
    """Load a specific canvas session."""
    _ensure_canvas_table(institution_id)
    with get_db_connection(institution_id, "student") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, session_name, canvas_json, saved_by, saved_at
            FROM canvas_sessions
            WHERE id = ? AND institution_id = ?
        """, (session_id, institution_id))
        row = cursor.fetchone()

    if not row:
        raise HTTPException(404, "Canvas session not found")

    canvas = json.loads(row["canvas_json"])
    return {
        "session_id": row["id"],
        "session_name": row["session_name"],
        "saved_by": row.get("saved_by"),
        "saved_at": row["saved_at"],
        "canvas": canvas,
    }


@router.post("/sessions")
def save_session(body: SaveCanvasRequest):
    """Save (create new) canvas session."""
    _ensure_canvas_table(body.institution_id)
    canvas_json = body.canvas.model_dump_json()
    with get_db_connection(body.institution_id, "student") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO canvas_sessions (institution_id, session_name, canvas_json)
            VALUES (?, ?, ?)
        """, (body.institution_id, body.session_name, canvas_json))
        session_id = cursor.lastrowid
        conn.commit()
    return {"status": "saved", "session_id": session_id}


@router.put("/sessions/{session_id}")
def update_session(session_id: int, body: SaveCanvasRequest):
    """Overwrite an existing canvas session (auto-save)."""
    _ensure_canvas_table(body.institution_id)
    canvas_json = body.canvas.model_dump_json()
    with get_db_connection(body.institution_id, "student") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE canvas_sessions
            SET canvas_json = ?, session_name = ?, saved_at = CURRENT_TIMESTAMP
            WHERE id = ? AND institution_id = ?
        """, (canvas_json, body.session_name, session_id, body.institution_id))
        if cursor.rowcount == 0:
            raise HTTPException(404, "Session not found")
        conn.commit()
    return {"status": "updated", "session_id": session_id}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, institution_id: str = Query("iit_delhi")):
    """Delete a canvas session."""
    _ensure_canvas_table(institution_id)
    with get_db_connection(institution_id, "student") as conn:
        conn.execute(
            "DELETE FROM canvas_sessions WHERE id = ? AND institution_id = ?",
            (session_id, institution_id)
        )
        conn.commit()
    return {"status": "deleted"}


@router.post("/sessions/{session_id}/export-timetable")
def export_to_timetable(session_id: int, institution_id: str = Query("iit_delhi")):
    """
    Convert a canvas session's cell assignments into timetable_entries in ACRM.
    Creates a new timetable_run and populates timetable_entries.
    """
    _ensure_canvas_table(institution_id)

    # Load session
    with get_db_connection(institution_id, "student") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT canvas_json FROM canvas_sessions WHERE id = ? AND institution_id = ?",
            (session_id, institution_id)
        )
        row = cursor.fetchone()
    if not row:
        raise HTTPException(404, "Session not found")

    canvas = json.loads(row["canvas_json"])
    nodes = canvas.get("nodes", [])

    entries_created = 0
    conflicts = []

    with get_db_connection(institution_id, "student") as conn:
        cursor = conn.cursor()

        # Create a new timetable run
        cursor.execute("""
            INSERT INTO timetable_runs (institution_id, status, targeting_mode, focus_mode)
            VALUES (?, 'draft', 'strict', 'balanced')
        """, (institution_id,))
        run_id = cursor.lastrowid

        for node in nodes:
            if node.get("type") != "timetable":
                continue

            data = node.get("data", {})
            class_id_str = data.get("class_id")
            cells = data.get("cells", {})
            days = data.get("days", [])
            lab_spans = data.get("lab_spans", {})

            if not class_id_str:
                continue

            # Resolve class db id
            cursor.execute(
                "SELECT id FROM classes WHERE class_id = ? AND institution_id = ?",
                (class_id_str, institution_id)
            )
            class_row = cursor.fetchone()
            if not class_row:
                conflicts.append(f"Class {class_id_str} not found")
                continue
            class_db_id = class_row["id"]

            for cell_key, assignment in cells.items():
                if not assignment:
                    continue
                try:
                    day_str, slot_str = cell_key.rsplit("-", 1)
                    day_index = days.index(day_str) if day_str in days else -1
                    slot_index = int(slot_str)
                except (ValueError, IndexError):
                    continue

                if day_index < 0:
                    continue

                faculty_id_str = assignment.get("faculty_id")
                subject_id_str = assignment.get("subject_id")
                room_id = assignment.get("room_id")
                slot_span = lab_spans.get(cell_key, 1)

                # Resolve faculty
                cursor.execute(
                    "SELECT id FROM faculty WHERE faculty_id = ? AND institution_id = ?",
                    (faculty_id_str, institution_id)
                )
                fac_row = cursor.fetchone()
                if not fac_row:
                    conflicts.append(f"Faculty {faculty_id_str} not found")
                    continue

                # Resolve subject
                cursor.execute(
                    "SELECT id FROM subjects WHERE subject_id = ? AND institution_id = ?",
                    (subject_id_str, institution_id)
                )
                sub_row = cursor.fetchone()
                if not sub_row:
                    conflicts.append(f"Subject {subject_id_str} not found")
                    continue

                cursor.execute("""
                    INSERT OR IGNORE INTO timetable_entries
                    (run_id, institution_id, class_id, subject_id, faculty_id, room_id,
                     day_index, slot_index, slot_span)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    run_id, institution_id,
                    class_db_id, sub_row["id"], fac_row["id"],
                    room_id, day_index, slot_index, slot_span
                ))
                entries_created += cursor.rowcount

        conn.commit()

    return {
        "status": "exported",
        "run_id": run_id,
        "entries_created": entries_created,
        "conflicts": conflicts,
    }

"""
Data router — reads faculty, subjects, classes, rooms directly from ACRM's SQLite databases.
Imports routes.database from the ACRM root (sys.path set in main.py).
"""

from __future__ import annotations
import json
from fastapi import APIRouter, Query, HTTPException

# These imports resolve because main.py adds ACRM root to sys.path
from routes.database import (
    get_db_connection,
    get_all_faculty,
    get_all_subjects,
    get_all_programs,
    get_all_semesters_flat,
    get_campus_rooms,
)

router = APIRouter()


# ──────────────────────────────────────────────
# Faculty
# ──────────────────────────────────────────────

@router.get("/faculty")
def api_faculty(
    institution_id: str = Query("iit_delhi"),
    search: str = Query(""),
):
    """
    Return all faculty with their subject assignments and qualification scores.
    Enriched with a match_score (proficiency * experience weight) for sidebar sorting.
    """
    faculty_list = get_all_faculty(institution_id)
    results = []
    for f in faculty_list:
        # Parse majors JSON if stored as string
        majors = f.get("majors") or "[]"
        if isinstance(majors, str):
            try:
                majors = json.loads(majors)
            except Exception:
                majors = [m.strip() for m in majors.split(",") if m.strip()]

        proficiency = f.get("proficiency_score") or 0
        experience = f.get("experience_years") or 0
        value = f.get("value_score") or 0

        # Simple composite score for sidebar ranking
        match_score = round((proficiency * 0.5) + (min(experience, 30) / 30 * 30) + (value * 0.2), 1)

        entry = {
            "id": f["faculty_id"],
            "db_id": f["id"],
            "name": f"{f.get('first_name', '')} {f.get('last_name', '')}".strip(),
            "email": f.get("email", ""),
            "is_teaching_staff": bool(f.get("is_teaching_staff", 0)),
            "majors": majors,
            "proficiency_score": proficiency,
            "experience_years": experience,
            "value_score": value,
            "match_score": match_score,
            "time_preference": f.get("time_preference"),
            "extra_notes": f.get("extra_notes", ""),
        }

        # Apply search filter
        if search:
            q = search.lower()
            if not (
                q in entry["name"].lower()
                or q in entry["id"].lower()
                or any(q in m.lower() for m in majors)
            ):
                continue

        results.append(entry)

    # Sort by match_score descending so best candidates appear first
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results


# ──────────────────────────────────────────────
# Subjects
# ──────────────────────────────────────────────

@router.get("/subjects")
def api_subjects(
    institution_id: str = Query("iit_delhi"),
    search: str = Query(""),
    semester_id: int = Query(None),
):
    """Return all subjects, optionally filtered by semester."""
    subjects = get_all_subjects(institution_id)
    results = []
    for s in subjects:
        if semester_id and s.get("semester_id") != semester_id:
            continue
        entry = {
            "id": s["subject_id"],
            "db_id": s["id"],
            "name": s["name"],
            "code": s["subject_id"],
            "description": s.get("description", ""),
            "delivery_mode": s.get("delivery_mode", "theory"),
            "has_theory": bool(s.get("has_theory_component", 1)),
            "has_practical": bool(s.get("has_practical_component", 0)),
            "theory_hours": s.get("theory_hours", 0),
            "practical_hours": s.get("practical_hours", 0),
            "requires_lab": bool(s.get("requires_lab", 0)),
            "semester_id": s.get("semester_id"),
            "required_majors": s.get("required_majors"),
            "min_proficiency": s.get("min_proficiency"),
            "min_experience": s.get("min_experience"),
        }
        if search:
            q = search.lower()
            if not (q in entry["name"].lower() or q in entry["code"].lower()):
                continue
        results.append(entry)
    return results


# ──────────────────────────────────────────────
# Classes
# ──────────────────────────────────────────────

@router.get("/classes")
def api_classes(
    institution_id: str = Query("iit_delhi"),
    semester_id: int = Query(None),
    program_id: int = Query(None),
):
    """Return all classes with their program and semester info."""
    with get_db_connection(institution_id, "student") as conn:
        cursor = conn.cursor()
        query = """
            SELECT c.*, p.program_name, p.code as program_code,
                   s.semester_number
            FROM classes c
            LEFT JOIN programs p ON c.program_id = p.id
            LEFT JOIN semesters s ON c.semester_id = s.id
            WHERE c.institution_id = ?
        """
        params = [institution_id]
        if semester_id:
            query += " AND c.semester_id = ?"
            params.append(semester_id)
        if program_id:
            query += " AND c.program_id = ?"
            params.append(program_id)
        query += " ORDER BY p.program_name, s.semester_number, c.section"
        cursor.execute(query, params)
        rows = cursor.fetchall()

    return [
        {
            "id": r["class_id"],
            "db_id": r["id"],
            "name": r["class_name"],
            "program_name": r.get("program_name", ""),
            "program_code": r.get("program_code", ""),
            "semester_number": r.get("semester_number"),
            "section": r["section"],
            "total_students": r.get("total_students", 0),
            "room_number": r.get("room_number"),
            "semester_id": r.get("semester_id"),
            "program_id": r.get("program_id"),
        }
        for r in rows
    ]


# ──────────────────────────────────────────────
# Programs / Branches
# ──────────────────────────────────────────────

@router.get("/programs")
def api_programs(institution_id: str = Query("iit_delhi")):
    return get_all_programs(institution_id)


# ──────────────────────────────────────────────
# Semesters
# ──────────────────────────────────────────────

@router.get("/semesters")
def api_semesters(institution_id: str = Query("iit_delhi")):
    return get_all_semesters_flat(institution_id)


# ──────────────────────────────────────────────
# Rooms
# ──────────────────────────────────────────────

@router.get("/rooms")
def api_rooms(
    institution_id: str = Query("iit_delhi"),
    room_type: str = Query(None),
):
    """Return campus rooms — classrooms and labs are the main ones used for scheduling."""
    rooms = get_campus_rooms(institution_id, room_type=room_type)
    return [
        {
            "id": r["id"],
            "room_number": r["room_number"],
            "room_type": r["room_type"],
            "capacity": r.get("capacity", 0),
            "floor_id": r.get("floor_id"),
            "section_id": r.get("section_id"),
        }
        for r in rooms
    ]


# ──────────────────────────────────────────────
# Faculty–Subject compatibility check
# ──────────────────────────────────────────────

@router.get("/faculty/{faculty_id}/can-teach/{subject_id}")
def api_can_teach(
    faculty_id: str,
    subject_id: str,
    institution_id: str = Query("iit_delhi"),
    mode: str = Query("strict"),  # strict | moderate | loose
):
    """
    Check whether a faculty member meets a subject's requirements.
    Returns a match result with score and any warnings.
    """
    faculty_list = get_all_faculty(institution_id)
    faculty = next((f for f in faculty_list if f["faculty_id"] == faculty_id), None)
    if not faculty:
        raise HTTPException(404, "Faculty not found")

    subjects = get_all_subjects(institution_id)
    subject = next((s for s in subjects if s["subject_id"] == subject_id), None)
    if not subject:
        raise HTTPException(404, "Subject not found")

    majors = faculty.get("majors") or "[]"
    if isinstance(majors, str):
        try:
            majors = json.loads(majors)
        except Exception:
            majors = [m.strip() for m in majors.split(",") if m.strip()]

    required_majors_raw = subject.get("required_majors") or "[]"
    try:
        required_majors = json.loads(required_majors_raw) if isinstance(required_majors_raw, str) else required_majors_raw
    except Exception:
        required_majors = []

    warnings = []
    score = 100

    # Major check
    if required_majors:
        overlap = [m for m in majors if m in required_majors]
        if not overlap:
            warnings.append(f"No matching major (faculty: {majors}, required: {required_majors})")
            score -= 40 if mode == "strict" else 20

    # Proficiency
    min_prof = subject.get("min_proficiency")
    fac_prof = faculty.get("proficiency_score") or 0
    if min_prof and fac_prof < min_prof:
        warnings.append(f"Proficiency {fac_prof} < required {min_prof}")
        score -= 20 if mode != "loose" else 5

    # Experience
    min_exp = subject.get("min_experience")
    fac_exp = faculty.get("experience_years") or 0
    if min_exp and fac_exp < min_exp:
        warnings.append(f"Experience {fac_exp}y < required {min_exp}y")
        score -= 15 if mode != "loose" else 5

    can_teach = score >= (60 if mode == "loose" else 80 if mode == "moderate" else 95)

    return {
        "faculty_id": faculty_id,
        "subject_id": subject_id,
        "can_teach": can_teach,
        "score": max(0, score),
        "warnings": warnings,
        "mode": mode,
    }

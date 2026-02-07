#!/usr/bin/env python
"""Utility script to bulk-generate a realistic demo dataset.

The generator builds the following structure for the chosen institution:
- 4 programs / branches.
- 3 active semesters per branch (created as 6, then odd semesters removed).
- 2 classes (sections A & B) per semester, each with 60 students and a unique homeroom.
- A campus grid with 8 floors (0-7), 2 sections per floor, 6 classrooms + 12 labs per section.
- 4-6 subjects per semester with the specified theory/practical breakdown.
- Faculty sized at ceil(1.25 * total_students / 30) with valid teaching metadata.

Usage:
    Edit the config settings at the top of this file, then run:
        python scripts/generate_sample_data.py
"""
from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

# Ensure project root is importable when script runs from anywhere
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from routes.database import (  # type: ignore  # pylint: disable=wrong-import-position
    create_campus_room,
    create_campus_sections,
    create_class,
    create_faculty,
    create_program,
    create_semester,
    create_student,
    create_subject,
    delete_semester,
    ensure_campus_floors,
    get_campus_floors,
    get_campus_sections,
    get_db_connection,
    get_semesters_by_program,
    reset_institution_data,
)

BRANCH_DEFINITIONS = [
    {"code": "CSE", "name": "Computer Science & Engineering"},
    {"code": "ECE", "name": "Electronics & Communication"},
    {"code": "ME", "name": "Mechanical Engineering"},
    {"code": "CIV", "name": "Civil & Infrastructure"},
]
SECTION_LABELS = ("A", "B")
FIRST_NAMES = [
    "Asha",
    "Neeraj",
    "Kavya",
    "Rohan",
    "Divya",
    "Ishaan",
    "Saanvi",
    "Kartik",
    "Meera",
    "Varun",
    "Anika",
    "Ritika",
    "Dev",
    "Tara",
    "Arjun",
    "Siddhi",
    "Riya",
    "Kabir",
    "Aarav",
    "Nisha",
]
LAST_NAMES = [
    "Sharma",
    "Patel",
    "Iyer",
    "Menon",
    "Kapoor",
    "Basu",
    "Singh",
    "Malik",
    "Desai",
    "Reddy",
    "Chopra",
    "Khanna",
    "Ganguly",
    "Mishra",
    "Garg",
    "Sethi",
]
SUBJECT_THEMES = [
    "Data Structures",
    "Signals & Systems",
    "Manufacturing Science",
    "Structural Analysis",
    "Control Theory",
    "Embedded Platforms",
    "Fluid Mechanics",
    "Geotechnics",
    "Numerical Methods",
    "Materials Lab",
    "Operating Systems",
    "Wireless Networks",
    "Robotics",
    "Thermal Systems",
]
TIME_PREFERENCES = ["early", "late", "any"]
MAJOR_OPTIONS = [
    "Mathematics",
    "Physics",
    "Chemistry",
    "Computer Science",
    "Electronics",
    "Mechanical",
    "Civil",
    "Humanities",
    "Management",
]

# Configurable settings for quick edits without CLI flags
INSTITUTION_ID = "iit_delhi"
RESET_INSTITUTION = True
RANDOM_SEED = 42
STUDENTS_PER_CLASS = 60


@dataclass
class ProgramRecord:
    code: str
    name: str
    db_id: int
    semesters: List[Dict]


@dataclass
class ClassRecord:
    class_id: str
    db_id: int
    program_id: int
    semester_id: int
    semester_number: int
    section: str
    room_id: int
    room_number: str
    program_code: str


def ensure_clean_slate(institution_id: str, do_reset: bool) -> None:
    if do_reset:
        print(f"[reset] Wiping institution '{institution_id}'...")
        result = reset_institution_data(institution_id)
        if result.get("status") != "success":
            raise RuntimeError(f"Reset failed: {result}")
    else:
        print(
            "[info] Reset skipped. Existing data may cause duplicate warnings; set RESET_INSTITUTION=True for a clean slate."
        )


def ensure_programs_and_semesters(institution_id: str) -> List[ProgramRecord]:
    records: List[ProgramRecord] = []
    for branch in BRANCH_DEFINITIONS:
        program_code = branch["code"]
        program_name = branch["name"]
        create_program(program_code, program_name, program_code, institution_id)
        program_row = fetch_program_row(institution_id, program_code)
        if not program_row:
            raise RuntimeError(f"Unable to load program row for {program_code}")

        for semester_number in range(1, 7):
            semester_code = f"{program_code}-SEM{semester_number}"
            create_semester(semester_code, semester_number, program_row["id"], institution_id)

        semesters = get_semesters_by_program(program_row["id"], institution_id)
        for semester in semesters:
            if semester["semester_number"] % 2 == 1:
                delete_semester(semester["id"], institution_id)

        even_semesters = get_semesters_by_program(program_row["id"], institution_id)
        records.append(
            ProgramRecord(
                code=program_code,
                name=program_name,
                db_id=program_row["id"],
                semesters=even_semesters,
            )
        )
    return records


def fetch_program_row(institution_id: str, program_code: str) -> Dict | None:
    with get_db_connection(institution_id, "student") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, program_id, program_name, code
            FROM programs
            WHERE institution_id = ? AND program_id = ?
            """,
            (institution_id, program_code),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def fetch_rooms_by_type(institution_id: str, room_type: str) -> List[Dict]:
    with get_db_connection(institution_id, "student") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, room_number
            FROM campus_rooms
            WHERE institution_id = ? AND room_type = ?
            ORDER BY room_number
            """,
            (institution_id, room_type),
        )
        return [dict(row) for row in cursor.fetchall()]


def seed_campus(institution_id: str, floors: int = 7) -> None:
    ensure_campus_floors(floors, institution_id)
    floor_rows = get_campus_floors(institution_id)
    floor_ids = [row["id"] for row in floor_rows]
    for label in SECTION_LABELS:
        create_campus_sections(label, floor_ids, institution_id)

    sections = get_campus_sections(institution_id)
    section_lookup: Dict[tuple[int, str], int] = {
        (section["floor_id"], section["name"].upper()): section["id"] for section in sections
    }

    for floor in floor_rows:
        floor_number = floor["floor_number"]
        for label in SECTION_LABELS:
            section_id = section_lookup.get((floor["id"], label))
            if not section_id:
                continue
            for idx in range(6):
                room_number = f"F{floor_number}{label}-C{idx+1:02d}"
                create_campus_room(
                    room_number,
                    "classroom",
                    floor["id"],
                    institution_id,
                    section_id=section_id,
                    capacity=72,
                )
            for idx in range(12):
                room_number = f"F{floor_number}{label}-L{idx+1:02d}"
                create_campus_room(
                    room_number,
                    "lab",
                    floor["id"],
                    institution_id,
                    section_id=section_id,
                    capacity=36,
                )


def build_classes(
    institution_id: str,
    programs: Sequence[ProgramRecord],
    classrooms: Sequence[Dict],
) -> List[ClassRecord]:
    needed_classes = sum(len(p.semesters) * len(SECTION_LABELS) for p in programs)
    if len(classrooms) < needed_classes:
        raise RuntimeError(
            f"Not enough classrooms ({len(classrooms)}) for {needed_classes} classes. Run with --reset to regenerate rooms."
        )

    class_records: List[ClassRecord] = []
    room_iter = iter(classrooms)
    for program in programs:
        for semester in program.semesters:
            for section in SECTION_LABELS:
                room = next(room_iter)
                class_code = f"{program.code}{semester['semester_number']:02d}{section}"
                class_name = f"{program.code} Sem {semester['semester_number']} {section}"
                create_class(
                    class_code,
                    class_name,
                    semester["id"],
                    program.db_id,
                    section,
                    institution_id,
                    room_number=room["room_number"],
                    home_room_id=room["id"],
                )
                class_row = fetch_class_row(institution_id, class_code)
                if not class_row:
                    raise RuntimeError(f"Failed to load class row for {class_code}")
                class_records.append(
                    ClassRecord(
                        class_id=class_code,
                        db_id=class_row["id"],
                        program_id=program.db_id,
                        semester_id=semester["id"],
                        semester_number=semester["semester_number"],
                        section=section,
                        room_id=room["id"],
                        room_number=room["room_number"],
                        program_code=program.code,
                    )
                )
    return class_records


def fetch_class_row(institution_id: str, class_code: str) -> Dict | None:
    with get_db_connection(institution_id, "student") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, class_id
            FROM classes
            WHERE institution_id = ? AND class_id = ?
            """,
            (institution_id, class_code),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def generate_students(
    institution_id: str,
    classes: Sequence[ClassRecord],
    students_per_class: int,
    rng: random.Random,
) -> int:
    student_counter = 1
    created = 0
    for classroom in classes:
        for idx in range(students_per_class):
            student_id = f"STD{student_counter:04d}"
            first_name = rng.choice(FIRST_NAMES)
            last_name = rng.choice(LAST_NAMES)
            email = f"{student_id.lower()}@example.edu"
            roll_no = f"{classroom.class_id}-{idx+1:02d}"
            phone = f"9000{rng.randint(100000, 999999)}"
            gender = rng.choice(["Male", "Female", "Other"])
            password = f"Pass@{rng.randint(1000, 9999)}"
            result = create_student(
                student_id,
                first_name,
                "",
                last_name,
                email,
                roll_no,
                phone,
                gender,
                password,
                classroom.program_id,
                classroom.semester_id,
                classroom.db_id,
                institution_id,
            )
            if result.get("status") == "success":
                created += 1
            student_counter += 1
    return created


def build_subjects(
    institution_id: str,
    programs: Sequence[ProgramRecord],
    rng: random.Random,
) -> int:
    planned_subjects: List[Dict] = []

    for program in programs:
        for semester in program.semesters:
            subject_total = rng.randint(4, 6)
            config = ["both", "both", "practical"] + ["theory"] * (subject_total - 3)
            rng.shuffle(config)
            for idx, kind in enumerate(config, start=1):
                subject_code = f"{program.code}{semester['semester_number']:02d}SUB{idx:02d}"
                base_name = rng.choice(SUBJECT_THEMES)
                subject_name = f"{base_name} {rng.choice(['Foundations', 'Systems', 'Lab', 'Advanced'])}"
                theory_hours, practical_hours, requires_lab = generate_hours(kind, rng)
                delivery_mode = "practical" if practical_hours > 0 else "theory"
                planned_subjects.append(
                    {
                        "code": subject_code,
                        "name": subject_name,
                        "description": f"{subject_name} for {program.name} semester {semester['semester_number']}.",
                        "program": program,
                        "semester": semester,
                        "teaching_hours": theory_hours + practical_hours,
                        "delivery_mode": delivery_mode,
                        "has_theory_component": theory_hours > 0,
                        "has_practical_component": practical_hours > 0,
                        "theory_hours": theory_hours,
                        "practical_hours": practical_hours,
                        "requires_lab": requires_lab,
                        "required_majors": generate_required_majors(rng),
                        "min_value": rng.randint(1, 10),
                    }
                )

    total_subjects = len(planned_subjects)
    if total_subjects == 0:
        return 0

    def allocate_bucket_counts(total_count: int, high_ratio: float, mid_ratio: float) -> tuple[int, int, int]:
        if total_count <= 0:
            return 0, 0, 0
        high = math.floor(total_count * high_ratio)
        mid = math.floor(total_count * mid_ratio)
        low = total_count - high - mid
        if low < 0:
            low = 0
            mid = total_count - high
        if high == 0 and total_count > 0:
            high = 1
            if low > 0:
                low -= 1
            elif mid > 0:
                mid -= 1
        if mid == 0 and total_count - high > 0:
            mid = 1
            if low > 0:
                low -= 1
            elif high > 1:
                high -= 1
        return high, mid, total_count - high - mid

    high_prof, mid_prof, _ = allocate_bucket_counts(total_subjects, 0.2, 0.4)
    prof_indices = list(range(total_subjects))
    rng.shuffle(prof_indices)
    high_prof_set = set(prof_indices[:high_prof])
    mid_prof_set = set(prof_indices[high_prof : high_prof + mid_prof])

    exp_high_count = min(total_subjects, max(1, math.floor(total_subjects * 0.2))) if total_subjects else 0
    exp_indices = list(range(total_subjects))
    rng.shuffle(exp_indices)
    exp_high_set = set(exp_indices[:exp_high_count])

    for idx, subject in enumerate(planned_subjects):
        if idx in high_prof_set:
            subject["min_proficiency"] = rng.randint(81, 100)
        elif idx in mid_prof_set:
            subject["min_proficiency"] = rng.randint(61, 80)
        else:
            subject["min_proficiency"] = rng.randint(36, 60)

        subject["min_experience"] = rng.randint(5, 8) if idx in exp_high_set else rng.randint(1, 3)

    created = 0
    for subject in planned_subjects:
        result = create_subject(
            subject["code"],
            subject["name"],
            subject["description"],
            "semester",
            institution_id,
            semester_id=subject["semester"]["id"],
            student_identifiers=[],
            semester_ids=[subject["semester"]["id"]],
            teaching_hours=subject["teaching_hours"],
            delivery_mode=subject["delivery_mode"],
            required_majors=subject["required_majors"],
            min_proficiency=subject["min_proficiency"],
            min_experience=subject["min_experience"],
            min_value=subject["min_value"],
            has_theory_component=subject["has_theory_component"],
            has_practical_component=subject["has_practical_component"],
            theory_hours=subject["theory_hours"],
            practical_hours=subject["practical_hours"],
            requires_lab=subject["requires_lab"],
        )
        if result.get("status") == "success":
            created += 1
    return created


def generate_hours(kind: str, rng: random.Random) -> tuple[int, int, bool]:
    if kind == "both":
        theory = rng.randint(24, 34)
        practical = rng.randint(18, 26)
        return theory, practical, True
    if kind == "practical":
        practical = rng.randint(24, 36)
        return 0, practical, False
    theory = rng.randint(36, 52)
    return theory, 0, False


def generate_required_majors(rng: random.Random) -> List[str]:
    if not MAJOR_OPTIONS:
        return []
    count = 1 if len(MAJOR_OPTIONS) == 1 else rng.choice([1, 2])
    return rng.sample(MAJOR_OPTIONS, k=count)


def build_faculty(
    institution_id: str,
    total_students: int,
    rng: random.Random,
) -> int:
    raw = (total_students / 30.0) * 1.25
    faculty_target = math.ceil(raw)
    created = 0
    major_pool = MAJOR_OPTIONS if MAJOR_OPTIONS else [branch["code"] for branch in BRANCH_DEFINITIONS]
    for idx in range(1, faculty_target + 1):
        faculty_id = f"FAC{idx:03d}"
        first_name = rng.choice(FIRST_NAMES)
        last_name = rng.choice(LAST_NAMES)
        email = f"{faculty_id.lower()}@example.edu"
        password = f"Teach@{rng.randint(1000, 9999)}"
        sample_count = 1 if len(major_pool) == 1 else rng.choice([1, 2])
        majors = rng.sample(major_pool, k=sample_count)
        proficiency = rng.randint(60, 100)
        experience = rng.randint(1, 20)
        value_score = rng.randint(5, 10)
        extra_notes = f"Specializes in {rng.choice(SUBJECT_THEMES)}."
        result = create_faculty(
            faculty_id,
            first_name,
            "",
            last_name,
            email,
            f"9100{rng.randint(100000, 999999)}",
            rng.choice(["Male", "Female", "Other"]),
            password,
            "faculty",
            institution_id,
            extra_notes,
            rng.choice(TIME_PREFERENCES),
            is_teaching_staff=True,
            majors=majors,
            proficiency_score=proficiency,
            experience_years=experience,
            value_score=value_score,
        )
        if result.get("status") == "success":
            created += 1
    return created


def summarize_counts(institution_id: str) -> Dict[str, int]:
    tables = {
        "students": "students",
        "faculty": "faculty",
        "classes": "classes",
        "subjects": "subjects",
        "rooms": "campus_rooms",
    }
    counts = {}
    with get_db_connection(institution_id, "student") as conn:
        cursor = conn.cursor()
        for label, table in tables.items():
            cursor.execute(
                f"SELECT COUNT(*) AS total FROM {table} WHERE institution_id = ?",
                (institution_id,),
            )
            counts[label] = cursor.fetchone()["total"]
    return counts


def main() -> None:
    rng = random.Random(RANDOM_SEED)
    ensure_clean_slate(INSTITUTION_ID, RESET_INSTITUTION)

    seed_campus(INSTITUTION_ID)
    classroom_rows = fetch_rooms_by_type(INSTITUTION_ID, "classroom")
    programs = ensure_programs_and_semesters(INSTITUTION_ID)
    classes = build_classes(INSTITUTION_ID, programs, classroom_rows)
    students_created = generate_students(INSTITUTION_ID, classes, STUDENTS_PER_CLASS, rng)
    subjects_created = build_subjects(INSTITUTION_ID, programs, rng)
    faculty_created = build_faculty(INSTITUTION_ID, len(classes) * STUDENTS_PER_CLASS, rng)

    counts = summarize_counts(INSTITUTION_ID)
    print("\n[done] Seeding complete!")
    print(f"Programs: {len(programs)}")
    print(f"Semesters: {sum(len(p.semesters) for p in programs)}")
    print(f"Classes: {len(classes)}")
    print(f"Students (new): {students_created} (total: {counts['students']})")
    print(f"Subjects (new): {subjects_created} (total: {counts['subjects']})")
    print(f"Faculty (new): {faculty_created} (total: {counts['faculty']})")
    print(f"Campus rooms total: {counts['rooms']}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from routes.database import (
    MAX_LAB_BATCH_SIZE,
    get_campus_rooms,
    get_db_connection,
    get_timetable_run,
    replace_timetable_entries,
    update_timetable_run_config,
    update_timetable_run_status,
)

DEFAULT_START_MINUTES = 9 * 60
SESSION_CAP_THEORY = 5
SESSION_CAP_PRACTICAL = 3


class TimetableEngineError(Exception):
    """Raised when the timetable processor cannot complete a run."""


@dataclass
class ClassContext:
    id: int
    class_code: str
    class_name: str
    section: str
    program_id: int
    program_code: str
    program_name: str
    semester_id: int
    semester_number: int
    total_students: int
    home_room_id: Optional[int]
    label: str
    is_focus: bool
    batch_codes: List[Optional[str]] = field(default_factory=list)


@dataclass
class AssignmentRecord:
    class_id: int
    faculty_id: int
    subject_id: int
    subject_code: str
    subject_name: str
    subject_type: str
    teaching_hours: int
    theory_hours: int
    practical_hours: int
    has_theory: bool
    has_practical: bool
    requires_lab: bool
    delivery_mode: str
    required_majors: Sequence[str]
    min_proficiency: Optional[int]
    min_experience: Optional[int]
    min_value: Optional[int]
    faculty_code: str
    faculty_name: str
    faculty_time_preference: str
    faculty_is_teaching: bool
    faculty_majors: Sequence[str]
    faculty_proficiency: Optional[int]
    faculty_experience: Optional[int]
    faculty_value: Optional[int]


@dataclass
class SessionRequirement:
    assignment: AssignmentRecord
    class_context: ClassContext
    session_type: str
    slot_span: int
    requires_lab: bool
    batch_code: Optional[str]
    priority: Tuple
    warnings: List[str]
    component_label: str
    session_index: int


def process_timetable_run(run_id: int, institution_id: str) -> Dict:
    run_record = get_timetable_run(run_id, institution_id)
    if not run_record:
        raise TimetableEngineError('Timetable run not found')
    engine = TimetableEngine(institution_id, run_record)
    return engine.execute()


class TimetableEngine:
    def __init__(self, institution_id: str, run_record: Dict):
        self.institution_id = institution_id
        self.run = run_record
        self.run_id = run_record.get('id')
        self.targeting_mode = (run_record.get('targeting_mode') or 'strict').lower()
        self.focus_mode = (run_record.get('focus_mode') or 'balanced').lower()
        self.margin_proficiency = self._coerce_int(run_record.get('margin_proficiency'), 0)
        self.margin_experience = self._coerce_int(run_record.get('margin_experience'), 0)
        self.slots_per_day = max(1, self._coerce_int(run_record.get('slots_per_day'), 6))
        self.slot_duration = max(15, self._coerce_int(run_record.get('slot_duration_minutes'), 60))
        self.days_per_week = max(1, self._coerce_int(run_record.get('days_per_week'), 5))
        self.lab_multi_slot = bool(run_record.get('lab_multi_slot', 1))
        self.slot_indices = list(range(self.slots_per_day))
        self.day_indices = list(range(self.days_per_week))
        self.first_slot_minutes = self._time_to_minutes(run_record.get('first_slot_start'))
        self.breaks = self._normalize_breaks(run_record.get('breaks') or [])
        self.break_slots = self._map_breaks_to_slots()
        self.random = random.Random(self.run_id or 1)
        self.room_lookup: Dict[int, Dict] = {}
        self.room_pools: Dict[str, List[int]] = {'classroom': [], 'lab': []}
        self.room_rotation: Dict[str, int] = {'classroom': 0, 'lab': 0}
        self.class_usage = set()
        self.faculty_usage = set()
        self.room_usage = set()
        self.warning_counter = Counter()
        self.unscheduled_counter = Counter()
        self.notes: List[str] = []
        self.classes: Dict[int, ClassContext] = {}
        self.assignments: List[AssignmentRecord] = []
        self.summary: Dict = {}
        self.focus_sets = {
            'programs': set(self._coerce_list(run_record.get('focus_branches'))),
            'semesters': set(self._coerce_list(run_record.get('focus_semesters'))),
            'classes': set(self._coerce_list(run_record.get('focus_classes'))),
        }
        self.margin_multiplier = {
            'strict': 1.0,
            'moderate': 1.5,
            'loose': 2.5,
        }.get(self.targeting_mode, 1.0)

    def execute(self) -> Dict:
        if not self.run_id:
            raise TimetableEngineError('Run identifier is missing')
        self._load_rooms()
        self._load_context()
        requirements = self._build_requirements()
        scheduled_entries: List[Dict] = []
        scheduled_meta: List[Dict] = []
        if requirements:
            scheduled_entries, scheduled_meta = self._schedule(requirements)
        replace_timetable_entries(self.run_id, self.institution_id, scheduled_entries)
        status = 'completed'
        if requirements and not scheduled_entries:
            status = 'failed'
            self.notes.append('No requirement could be placed. Please review conflicts.')
        update_timetable_run_status(self.run_id, self.institution_id, status)
        summary = self._build_summary(requirements, scheduled_entries, scheduled_meta, status)
        config_snapshot = dict(self.run.get('config') or {})
        config_snapshot['engine_summary'] = summary
        update_timetable_run_config(self.run_id, self.institution_id, config_snapshot)
        return summary

    def _load_rooms(self) -> None:
        rooms = get_campus_rooms(self.institution_id)
        for room in rooms:
            self.room_lookup[room['id']] = room
            room_type = room.get('room_type') or 'classroom'
            if room_type == 'lab':
                self.room_pools['lab'].append(room['id'])
            else:
                self.room_pools['classroom'].append(room['id'])
        if not self.room_pools['classroom']:
            self.notes.append('No classrooms found; theory sessions may fail to place.')
        if not self.room_pools['lab']:
            self.notes.append('No labs found; lab-required sessions cannot be scheduled.')

    def _load_context(self) -> None:
        with get_db_connection(self.institution_id, 'student') as conn:
            cursor = conn.cursor()
            self.classes = self._fetch_classes(cursor)
            self._attach_class_batches(cursor)
            self.assignments = self._fetch_assignments(cursor)
        if not self.assignments:
            self.notes.append('No faculty-class assignments detected. Generated timetable will be empty.')

    def _fetch_classes(self, cursor) -> Dict[int, ClassContext]:
        cursor.execute('''
            SELECT c.id, c.class_id, c.class_name, c.section,
                   c.program_id, p.program_name, p.program_id AS program_code,
                   c.semester_id, s.semester_number,
                   COALESCE(c.total_students, 0) AS total_students,
                   c.home_room_id
            FROM classes c
            JOIN programs p ON c.program_id = p.id
            JOIN semesters s ON c.semester_id = s.id
            WHERE c.institution_id = ?
        ''', (self.institution_id,))
        class_map: Dict[int, ClassContext] = {}
        for row in cursor.fetchall():
            class_id = row['id']
            section = row['section'] or ''
            label = f"{row['program_code'] or row['program_id'] or 'PRG'}-{row['semester_number'] or '0'}{section}"
            is_focus = False
            if self.focus_mode == 'focus':
                is_focus = (
                    class_id in self.focus_sets['classes'] or
                    row['semester_id'] in self.focus_sets['semesters'] or
                    row['program_id'] in self.focus_sets['programs']
                )
            home_room_id = row['home_room_id'] if row['home_room_id'] in self.room_lookup else None
            if row['home_room_id'] and home_room_id is None:
                self.notes.append(f"Class {row['class_name']} references a missing home room.")
            context = ClassContext(
                id=class_id,
                class_code=row['class_id'],
                class_name=row['class_name'],
                section=section,
                program_id=row['program_id'],
                program_code=row['program_code'] or row['program_id'] or '',
                program_name=row['program_name'],
                semester_id=row['semester_id'],
                semester_number=row['semester_number'],
                total_students=row['total_students'],
                home_room_id=home_room_id,
                label=label,
                is_focus=is_focus,
            )
            class_map[class_id] = context
        return class_map

    def _attach_class_batches(self, cursor) -> None:
        if not self.classes:
            return
        class_ids = list(self.classes.keys())
        placeholders = ','.join('?' for _ in class_ids)
        cursor.execute(
            f'''SELECT class_id, batch_code, sequence_index FROM class_batches
                WHERE institution_id = ? AND class_id IN ({placeholders})
                ORDER BY class_id, sequence_index''',
            (self.institution_id, *class_ids)
        )
        grouped: Dict[int, List[str]] = defaultdict(list)
        for row in cursor.fetchall():
            grouped[row['class_id']].append(row['batch_code'])
        for context in self.classes.values():
            batch_codes = grouped.get(context.id)
            if not batch_codes:
                batch_codes = self._fallback_batches(context.total_students)
            context.batch_codes = batch_codes or [None]
            if context.home_room_id is None:
                self.unscheduled_counter['missing-home-room'] += 1

    def _fetch_assignments(self, cursor) -> List[AssignmentRecord]:
        cursor.execute('''
            SELECT fc.class_id, fc.faculty_id, fc.subject_ref_id,
                   subj.subject_id AS subject_code, subj.name AS subject_name,
                   subj.subject_type, subj.teaching_hours,
                   COALESCE(subj.theory_hours, 0) AS theory_hours,
                   COALESCE(subj.practical_hours, 0) AS practical_hours,
                   subj.has_theory_component, subj.has_practical_component,
                   subj.requires_lab, subj.delivery_mode,
                   subj.required_majors, subj.min_proficiency,
                   subj.min_experience, subj.min_value,
                   fac.faculty_id AS faculty_code,
                   fac.first_name || ' ' || fac.last_name AS faculty_name,
                   COALESCE(fac.time_preference, 'any') AS time_pref,
                   fac.is_teaching_staff,
                   fac.majors AS faculty_majors,
                   fac.proficiency_score, fac.experience_years, fac.value_score
            FROM faculty_classes fc
            JOIN subjects subj ON fc.subject_ref_id = subj.id
            JOIN faculty fac ON fc.faculty_id = fac.id
            WHERE fc.institution_id = ?
        ''', (self.institution_id,))
        assignments: List[AssignmentRecord] = []
        for row in cursor.fetchall():
            class_context = self.classes.get(row['class_id'])
            if not class_context:
                self.unscheduled_counter['missing-class'] += 1
                continue
            assignment = AssignmentRecord(
                class_id=row['class_id'],
                faculty_id=row['faculty_id'],
                subject_id=row['subject_ref_id'],
                subject_code=row['subject_code'] or f"SUB-{row['subject_ref_id']}",
                subject_name=row['subject_name'] or 'Subject',
                subject_type=row['subject_type'] or 'semester',
                teaching_hours=self._coerce_int(row['teaching_hours'], 0),
                theory_hours=self._coerce_int(row['theory_hours'], 0),
                practical_hours=self._coerce_int(row['practical_hours'], 0),
                has_theory=bool(row['has_theory_component']),
                has_practical=bool(row['has_practical_component']),
                requires_lab=bool(row['requires_lab']),
                delivery_mode=row['delivery_mode'] or 'theory',
                required_majors=self._split_csv(row['required_majors']),
                min_proficiency=self._coerce_optional_int(row['min_proficiency']),
                min_experience=self._coerce_optional_int(row['min_experience']),
                min_value=self._coerce_optional_int(row['min_value']),
                faculty_code=row['faculty_code'] or f"FAC-{row['faculty_id']}",
                faculty_name=row['faculty_name'] or 'Faculty',
                faculty_time_preference=(row['time_pref'] or 'any').lower(),
                faculty_is_teaching=bool(row['is_teaching_staff']),
                faculty_majors=self._split_csv(row['faculty_majors']),
                faculty_proficiency=self._coerce_optional_int(row['proficiency_score']),
                faculty_experience=self._coerce_optional_int(row['experience_years']),
                faculty_value=self._coerce_optional_int(row['value_score']),
            )
            assignments.append(assignment)
        return assignments

    def _build_requirements(self) -> List[SessionRequirement]:
        requirements: List[SessionRequirement] = []
        skipped_constraints = 0
        for assignment in self.assignments:
            class_context = self.classes.get(assignment.class_id)
            if not class_context:
                continue
            eligible, penalty, warnings = self._evaluate_constraints(assignment)
            if not eligible:
                skipped_constraints += 1
                self.unscheduled_counter['constraint-blocked'] += 1
                continue
            focus_bucket = 0 if (self.focus_mode == 'focus' and class_context.is_focus) else 1
            priority_base = (
                focus_bucket,
                penalty,
            )
            if assignment.has_theory:
                sessions = self._estimate_sessions(assignment.theory_hours or assignment.teaching_hours, SESSION_CAP_THEORY)
                for index in range(sessions):
                    req = SessionRequirement(
                        assignment=assignment,
                        class_context=class_context,
                        session_type='theory',
                        slot_span=1,
                        requires_lab=False,
                        batch_code=None,
                        priority=priority_base + (1, -int(assignment.min_value or 0), -int(assignment.faculty_value or 0), self.random.random()),
                        warnings=list(warnings),
                        component_label='Theory',
                        session_index=index,
                    )
                    requirements.append(req)
            if assignment.has_practical:
                sessions = self._estimate_sessions(assignment.practical_hours or assignment.teaching_hours, SESSION_CAP_PRACTICAL)
                slot_span = 2 if (self.lab_multi_slot and (assignment.requires_lab or assignment.delivery_mode == 'practical')) else 1
                slot_span = min(slot_span, self.slots_per_day)
                batches = class_context.batch_codes or [None]
                for index in range(sessions):
                    for batch_code in batches:
                        req = SessionRequirement(
                            assignment=assignment,
                            class_context=class_context,
                            session_type='practical',
                            slot_span=slot_span,
                            requires_lab=assignment.requires_lab or assignment.delivery_mode == 'practical',
                            batch_code=batch_code,
                            priority=priority_base + (0, -int(assignment.min_value or 0), -int(assignment.faculty_value or 0), self.random.random()),
                            warnings=list(warnings),
                            component_label=f"Practical{f' • {batch_code}' if batch_code else ''}",
                            session_index=index,
                        )
                        requirements.append(req)
        if skipped_constraints:
            self.notes.append(f"{skipped_constraints} assignments violated strict targeting rules and were skipped.")
        return requirements

    def _estimate_sessions(self, hours: int, cap: int) -> int:
        if hours <= 0:
            return 1
        estimate = math.ceil((hours * 5) / max(1, self.slot_duration))
        return max(1, min(cap, estimate))

    def _schedule(self, requirements: Sequence[SessionRequirement]) -> Tuple[List[Dict], List[Dict]]:
        ordered = sorted(requirements, key=lambda req: req.priority)
        entries: List[Dict] = []
        metadata: List[Dict] = []
        for requirement in ordered:
            placement = self._place_requirement(requirement)
            if not placement:
                continue
            entries.append(placement['entry'])
            metadata.append(placement['meta'])
        return entries, metadata

    def _place_requirement(self, requirement: SessionRequirement) -> Optional[Dict]:
        slot_sequence = self._slot_sequence(requirement.assignment)
        day_sequence = self._day_sequence(requirement)
        for day in day_sequence:
            for slot in slot_sequence:
                if not self._slots_available(requirement, day, slot):
                    continue
                room_id = self._allocate_room(requirement, day, slot)
                if room_id is None and requirement.requires_lab:
                    self.unscheduled_counter['room-unavailable'] += 1
                    continue
                if room_id is None:
                    room_id = self._allocate_room(requirement, day, slot, fallback_to_classroom=True)
                if room_id is None:
                    self.unscheduled_counter['room-unavailable'] += 1
                    continue
                self._book(requirement, day, slot, room_id)
                meta = {
                    'class_id': requirement.class_context.id,
                    'subject_id': requirement.assignment.subject_id,
                    'faculty_id': requirement.assignment.faculty_id,
                    'session_type': requirement.session_type,
                    'slot_span': requirement.slot_span,
                    'batch_code': requirement.batch_code,
                }
                entry = {
                    'class_id': requirement.class_context.id,
                    'subject_id': requirement.assignment.subject_id,
                    'faculty_id': requirement.assignment.faculty_id,
                    'room_id': room_id,
                    'day_index': day,
                    'slot_index': slot,
                    'slot_span': requirement.slot_span,
                }
                return {'entry': entry, 'meta': meta}
        self.unscheduled_counter['slot-unavailable'] += 1
        return None

    def _slot_sequence(self, assignment: AssignmentRecord) -> List[int]:
        preference = assignment.faculty_time_preference
        if preference == 'late':
            return list(reversed(self.slot_indices))
        if preference == 'early':
            return list(self.slot_indices)
        midpoint = len(self.slot_indices) // 2
        return self.slot_indices[midpoint:] + self.slot_indices[:midpoint]

    def _day_sequence(self, requirement: SessionRequirement) -> List[int]:
        if not self.day_indices:
            return [0]
        shift = (requirement.class_context.id + requirement.session_index) % len(self.day_indices)
        return self.day_indices[shift:] + self.day_indices[:shift]

    def _slots_available(self, requirement: SessionRequirement, day: int, slot: int) -> bool:
        for offset in range(requirement.slot_span):
            current_slot = slot + offset
            if current_slot >= self.slots_per_day:
                return False
            if current_slot in self.break_slots:
                return False
            class_key = (requirement.class_context.id, day, current_slot)
            faculty_key = (requirement.assignment.faculty_id, day, current_slot)
            if class_key in self.class_usage or faculty_key in self.faculty_usage:
                return False
        return True

    def _allocate_room(self, requirement: SessionRequirement, day: int, slot: int, fallback_to_classroom: bool = False) -> Optional[int]:
        if requirement.session_type == 'theory' and requirement.class_context.home_room_id and not fallback_to_classroom:
            if self._room_available(requirement.class_context.home_room_id, day, slot, requirement.slot_span):
                return requirement.class_context.home_room_id
        pool_key = 'lab' if requirement.requires_lab else 'classroom'
        if fallback_to_classroom and pool_key == 'lab':
            pool_key = 'classroom'
        pool = self.room_pools.get(pool_key) or []
        if not pool:
            reason = 'no-lab-room' if pool_key == 'lab' else 'no-classroom'
            self.unscheduled_counter[reason] += 1
            return None
        candidates = self._rotating_pool(pool_key)
        for room_id in candidates:
            if self._room_available(room_id, day, slot, requirement.slot_span):
                return room_id
        return None

    def _rotating_pool(self, pool_key: str) -> List[int]:
        pool = self.room_pools.get(pool_key) or []
        if not pool:
            return []
        start = self.room_rotation.get(pool_key, 0) % len(pool)
        ordered = pool[start:] + pool[:start]
        self.room_rotation[pool_key] = (start + 1) % len(pool)
        return ordered

    def _room_available(self, room_id: int, day: int, slot: int, span: int) -> bool:
        for offset in range(span):
            current_slot = slot + offset
            if (room_id, day, current_slot) in self.room_usage:
                return False
        return True

    def _book(self, requirement: SessionRequirement, day: int, slot: int, room_id: int) -> None:
        for offset in range(requirement.slot_span):
            current_slot = slot + offset
            self.class_usage.add((requirement.class_context.id, day, current_slot))
            self.faculty_usage.add((requirement.assignment.faculty_id, day, current_slot))
            self.room_usage.add((room_id, day, current_slot))

    def _evaluate_constraints(self, assignment: AssignmentRecord) -> Tuple[bool, int, List[str]]:
        warnings: List[str] = []
        penalty = 0
        if assignment.required_majors:
            if not set(assignment.required_majors).intersection(set(assignment.faculty_majors)):
                if self.targeting_mode == 'strict':
                    return False, penalty, warnings
                warnings.append('major_mismatch')
        if not assignment.faculty_is_teaching:
            if self.targeting_mode == 'strict':
                return False, penalty, warnings
            warnings.append('non_teaching_staff')
        prof_threshold = self._threshold(assignment.min_proficiency, self.margin_proficiency)
        if prof_threshold is not None:
            value = assignment.faculty_proficiency or 0
            if value < prof_threshold:
                if self.targeting_mode == 'strict':
                    return False, penalty, warnings
                warnings.append('proficiency_gap')
        exp_threshold = self._threshold(assignment.min_experience, self.margin_experience)
        if exp_threshold is not None:
            value = assignment.faculty_experience or 0
            if value < exp_threshold:
                if self.targeting_mode == 'strict':
                    return False, penalty, warnings
                warnings.append('experience_gap')
        value_threshold = assignment.min_value or 0
        if self.targeting_mode == 'moderate':
            value_threshold = max(0, value_threshold - 1)
        elif self.targeting_mode == 'loose':
            value_threshold = max(0, value_threshold - 2)
        if value_threshold:
            faculty_value = assignment.faculty_value or 0
            if faculty_value < value_threshold and self.targeting_mode == 'strict':
                return False, penalty, warnings
            if faculty_value < value_threshold:
                warnings.append('value_gap')
        for warning in warnings:
            self.warning_counter[warning] += 1
        penalty = min(3, len(warnings))
        return True, penalty, warnings

    def _build_summary(self, requirements, entries, metadata, status):
        class_ids = {item['class_id'] for item in entries}
        faculty_ids = {item['faculty_id'] for item in entries}
        subject_ids = {item['subject_id'] for item in entries}
        span_counter = Counter(item['slot_span'] for item in entries)
        lab_blocks = sum(1 for meta in metadata if meta['session_type'] == 'practical')
        summary = {
            'run_id': self.run_id,
            'status': status,
            'generated_at': datetime.utcnow().isoformat() + 'Z',
            'requirements_total': len(requirements),
            'sessions_scheduled': len(entries),
            'sessions_unscheduled': sum(self.unscheduled_counter.values()),
            'unscheduled_reasons': dict(self.unscheduled_counter),
            'warnings': dict(self.warning_counter),
            'classes_touched': len(class_ids),
            'faculty_touched': len(faculty_ids),
            'subjects_touched': len(subject_ids),
            'lab_blocks': lab_blocks,
            'theory_blocks': len(entries) - lab_blocks,
            'slot_span_usage': dict(span_counter),
            'slot_config': {
                'days_per_week': self.days_per_week,
                'slots_per_day': self.slots_per_day,
                'slot_duration_minutes': self.slot_duration,
                'break_slots': sorted(self.break_slots),
                'lab_multi_slot': self.lab_multi_slot,
            },
            'focus_mode': self.focus_mode,
            'targeting_mode': self.targeting_mode,
            'notes': self.notes,
        }
        total_capacity = max(1, len(self.classes)) * self.days_per_week * self.slots_per_day
        summary['slot_fill_rate'] = round(len(entries) / total_capacity, 4)
        summary['focus_class_count'] = sum(1 for cls in self.classes.values() if cls.is_focus)
        summary['room_pool'] = {
            'classrooms': len(self.room_pools['classroom']),
            'labs': len(self.room_pools['lab']),
        }
        return summary

    @staticmethod
    def _fallback_batches(total_students: int) -> List[Optional[str]]:
        if not total_students:
            return [None]
        count = max(1, math.ceil(total_students / MAX_LAB_BATCH_SIZE))
        return [f"B{index + 1}" for index in range(count)]

    @staticmethod
    def _split_csv(raw_value: Optional[str]) -> List[str]:
        if not raw_value:
            return []
        return [segment.strip() for segment in str(raw_value).split(',') if segment.strip()]

    @staticmethod
    def _coerce_int(value, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _coerce_optional_int(value) -> Optional[int]:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_list(values) -> List[int]:
        if not values:
            return []
        cleaned = []
        for value in values:
            try:
                cleaned.append(int(value))
            except (TypeError, ValueError):
                continue
        return cleaned

    def _normalize_breaks(self, breaks: Iterable[Dict]) -> List[Dict]:
        normalized = []
        for item in breaks:
            if not isinstance(item, dict):
                continue
            start = (item.get('start') or '').strip()
            duration = self._coerce_int(item.get('duration_minutes'), 0)
            if not start or duration <= 0:
                continue
            normalized.append({'start': start, 'duration_minutes': duration})
            if len(normalized) >= 8:
                break
        return normalized

    def _map_breaks_to_slots(self) -> set:
        blocked = set()
        slot_starts = [self.first_slot_minutes + idx * self.slot_duration for idx in self.slot_indices]
        for brk in self.breaks:
            start_minutes = self._time_to_minutes(brk['start'])
            window = (start_minutes, start_minutes + brk['duration_minutes'])
            for idx, slot_start in enumerate(slot_starts):
                if window[0] <= slot_start < window[1]:
                    blocked.add(idx)
        return blocked

    @staticmethod
    def _time_to_minutes(label: Optional[str]) -> int:
        if not label:
            return DEFAULT_START_MINUTES
        try:
            hour, minute = label.split(':')
            return int(hour) * 60 + int(minute)
        except (ValueError, AttributeError):
            return DEFAULT_START_MINUTES

    def _threshold(self, required: Optional[int], margin: int) -> Optional[int]:
        if required is None:
            return None
        threshold = required - (margin * self.margin_multiplier)
        return max(0, int(threshold))
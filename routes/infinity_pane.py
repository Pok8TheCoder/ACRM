"""Infinity Pane integration routes and APIs."""
import json
import os
from hashlib import md5
from flask import Blueprint, jsonify, request, session, redirect, url_for, send_from_directory, current_app
from routes.database import (
    get_all_faculty,
    get_all_subjects,
    get_faculty_subjects,
    get_all_classes,
    get_infinity_pane_state,
    save_infinity_pane_state,
    create_infinity_pane_audit,
    get_infinity_pane_audit,
)

infinity_pane_bp = Blueprint('infinity_pane', __name__)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
FRONTEND_BUILD_DIR = os.path.join(PROJECT_ROOT, 'infinity_pane_frontend', 'build')


def _require_admin_role():
    if 'role' not in session or session['role'] != 'admin':
        return False
    return True


def _color_from_seed(value, saturation=70, lightness=55):
    if value is None:
        return '#808080'
    digest = md5(str(value).encode('utf-8')).hexdigest()
    hue = int(digest[:6], 16) % 360
    return f"hsl({hue}, {saturation}%, {lightness}%)"


def _build_canvas_summary(payload):
    def count(value):
        return len(value) if isinstance(value, list) else 0
    return {
        'groups': count(payload.get('groups')),
        'timetables': count(payload.get('timetables')),
        'arrows': count(payload.get('arrows')),
        'freeArrows': count(payload.get('freeArrows')),
        'teacherPlacements': count(payload.get('teacherPlacements')),
        'subjectPlacements': count(payload.get('subjectPlacements')),
        'textBlocks': count(payload.get('textBlocks')),
        'structureBlocks': count(payload.get('structureBlocks')),
        'classesWithSubjects': len(payload.get('classSubjects') or {}),
    }


def _summary_diff(previous, current):
    diff = {}
    for key in set(previous.keys()) | set(current.keys()):
        before = previous.get(key, 0)
        after = current.get(key, 0)
        if before != after:
            diff[key] = {'before': before, 'after': after}
    return diff


@infinity_pane_bp.route('/admin/infinity-pane')
def infinity_pane_page():
    if not _require_admin_role():
        return redirect(url_for('home.login'))
    index_path = os.path.join(FRONTEND_BUILD_DIR, 'index.html')
    if not os.path.exists(index_path):
        current_app.logger.error('Infinity Pane build not found at %s', FRONTEND_BUILD_DIR)
        return "Infinity Pane build not found. Please build the frontend.", 500
    return send_from_directory(FRONTEND_BUILD_DIR, 'index.html')


@infinity_pane_bp.route('/admin/infinity-pane/<path:path>')
def infinity_pane_assets(path):
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    return send_from_directory(FRONTEND_BUILD_DIR, path)


@infinity_pane_bp.route('/api/teachers', methods=['GET'])
def api_infinity_pane_teachers():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    institution_id = session.get('institution_id')
    search = (request.args.get('search') or '').lower().strip()

    faculty = get_all_faculty(institution_id)
    subjects = get_all_subjects(institution_id)
    subject_map = {str(s['id']): s for s in subjects}

    teachers = []
    for row in faculty:
        full_name = ' '.join(filter(None, [row.get('first_name'), row.get('middle_name'), row.get('last_name')])).strip()
        teacher_name = full_name or row.get('faculty_id')
        teacher_id = str(row.get('faculty_id') or row.get('id'))
        if search:
            haystack = f"{teacher_name} {teacher_id}".lower()
            if search not in haystack:
                continue

        subject_rows = get_faculty_subjects(row.get('id'), institution_id)
        subject_ids = [str(s.get('subject_db_id')) for s in subject_rows if s.get('subject_db_id')]
        subject_details = [
            {
                'id': sid,
                'name': subject_map.get(sid, {}).get('name', 'Unknown')
            }
            for sid in subject_ids
        ]

        teachers.append({
            'id': teacher_id,
            'name': teacher_name,
            'subjects': subject_ids,
            'subjectDetails': subject_details,
            'color': _color_from_seed(teacher_id),
        })

    return jsonify(teachers)


@infinity_pane_bp.route('/api/subjects', methods=['GET'])
def api_infinity_pane_subjects():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    institution_id = session.get('institution_id')
    search = (request.args.get('search') or '').lower().strip()

    subjects = []
    for row in get_all_subjects(institution_id):
        base_id = str(row.get('id'))
        name = row.get('name') or row.get('subject_id') or base_id
        code = row.get('subject_id') or base_id
        assigned_semesters = row.get('assigned_semesters') or []
        assigned_ids = [str(s.get('semester_id')) for s in assigned_semesters if s.get('semester_id')]
        if not assigned_ids:
            continue

        has_theory = bool(row.get('has_theory_component'))
        has_practical = bool(row.get('has_practical_component'))
        theory_hours = row.get('theory_hours') or 0
        practical_hours = row.get('practical_hours') or 0
        teaching_hours = row.get('teaching_hours') or 0

        def matches(term_name, term_code, term_id):
            if not search:
                return True
            haystack = f"{term_name} {term_code} {term_id}".lower()
            return search in haystack

        if has_theory and has_practical:
            if matches(name, code, f"{base_id}-theory"):
                subjects.append({
                    'id': f"{base_id}-theory",
                    'baseSubjectId': base_id,
                    'name': name,
                    'code': code,
                    'component': 'theory',
                    'hours': theory_hours or teaching_hours,
                    'assignedSemesterIds': assigned_ids,
                    'color': _color_from_seed(f"{base_id}-theory", lightness=60),
                })
            if matches(f"{name} (Prac.)", f"{code}-P", f"{base_id}-practical"):
                subjects.append({
                    'id': f"{base_id}-practical",
                    'baseSubjectId': base_id,
                    'name': f"{name} (Prac.)",
                    'code': f"{code}-P" if code else f"{base_id}-P",
                    'component': 'practical',
                    'hours': practical_hours or teaching_hours,
                    'assignedSemesterIds': assigned_ids,
                    'color': _color_from_seed(f"{base_id}-practical", lightness=60),
                })
            continue

        if not matches(name, code, base_id):
            continue
        subjects.append({
            'id': base_id,
            'baseSubjectId': base_id,
            'name': name,
            'code': code,
            'component': 'theory' if has_theory else 'practical' if has_practical else 'general',
            'hours': teaching_hours or theory_hours or practical_hours,
            'assignedSemesterIds': assigned_ids,
            'color': _color_from_seed(base_id, lightness=60),
        })

    return jsonify(subjects)


@infinity_pane_bp.route('/api/classes', methods=['GET'])
def api_infinity_pane_classes():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    institution_id = session.get('institution_id')
    classes = []
    for row in get_all_classes(institution_id):
        class_id = str(row.get('id'))
        classes.append({
            'id': class_id,
            'name': row.get('class_name') or row.get('class_id') or class_id,
            'section': row.get('section') or '',
            'strength': row.get('total_students') or 0,
            'semesterId': str(row.get('semester_id')) if row.get('semester_id') else None,
        })
    return jsonify(classes)


@infinity_pane_bp.route('/api/canvas', methods=['GET'])
def api_infinity_pane_canvas():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    institution_id = session.get('institution_id')
    payload = get_infinity_pane_state(institution_id)
    if not payload:
        payload = {
            'classSubjects': {},
            'classWeeks': {},
            'groups': [],
            'timetables': [],
            'arrows': [],
            'freeArrows': [],
            'teacherPlacements': [],
            'subjectPlacements': [],
            'textBlocks': [],
            'structureBlocks': [],
        }
    return jsonify(payload)


@infinity_pane_bp.route('/api/canvas', methods=['POST'])
def api_infinity_pane_save_canvas():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    institution_id = session.get('institution_id')
    payload = request.get_json(silent=True) or {}

    previous = get_infinity_pane_state(institution_id) or {}
    previous_summary = _build_canvas_summary(previous)
    current_summary = _build_canvas_summary(payload)

    save_infinity_pane_state(
        institution_id,
        payload,
        actor=session.get('user_id') or session.get('user_name')
    )

    diff = _summary_diff(previous_summary, current_summary)
    create_infinity_pane_audit(
        institution_id,
        session.get('user_id'),
        session.get('user_name'),
        'canvas_saved',
        {
            'summary': current_summary,
            'changes': diff
        }
    )

    return jsonify({'success': True})


@infinity_pane_bp.route('/api/infinity-pane/audit', methods=['GET'])
def api_infinity_pane_audit():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    institution_id = session.get('institution_id')
    limit = request.args.get('limit', 50)
    entries = get_infinity_pane_audit(institution_id, limit=limit)
    return jsonify({'entries': entries})

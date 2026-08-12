"""Admin dashboard and management routes"""
import json
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, send_file, Response, current_app
import csv
import io
from routes.database import (get_admin_info, get_admin_stats, get_db_connection,
                     get_all_programs, create_program, delete_program,
                     get_semesters_by_program, create_semester, delete_semester,
                     get_classes_by_semester, create_class, delete_class,
                     get_students_by_class, get_all_students_flat, create_student, get_student_by_id, update_student, delete_student,
                     get_all_faculty, create_faculty, get_faculty_by_id, update_faculty, delete_faculty,
                     assign_faculty_to_class, assign_faculty_to_subjects, auto_assign_subject_faculty, remove_faculty_subject_assignment,
                     get_faculty_classes, get_faculty_subjects,
                     export_full_institution_data, import_full_institution_data,
                     get_all_subjects, create_subject, delete_subject, update_subject,
                     get_all_semesters_flat, get_subject_resources, get_subject_by_id,
                     get_subject_resource, delete_subject_resource,
                     ensure_campus_floors, get_campus_layout, create_campus_sections,
                     create_campus_room, get_campus_rooms, get_campus_room_by_id,
                     update_campus_room, delete_campus_room, delete_campus_section,
                     delete_campus_floor, reset_campus_layout, get_floor_summary,
                     get_section_summary, get_room_summary, get_classes_without_home_room,
                     get_class_by_id, update_class_record, get_class_using_home_room,
                     get_campus_rooms_flat, import_campus_rooms_from_rows,
                     reset_institution_data, create_timetable_run, get_recent_timetable_runs,
                     update_timetable_run_status, delete_timetable_run, get_timetable_run, get_latest_timetable_run,
                     get_timetable_sessions_for_faculty, get_timetable_preview_snapshot)
from routes.timetable_engine import process_timetable_run, TimetableEngineError

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def _require_admin_role():
    """Check if user is admin"""
    if 'role' not in session or session['role'] != 'admin':
        return False
    return True

@admin_bp.route('/dashboard')
def admin_dashboard():
    """Admin dashboard"""
    if not _require_admin_role():
        return redirect(url_for('home.login'))
    
    admin_name = session.get('user_name')
    return render_template('admin/dashboard.html', admin_name=admin_name)

# Info & Stats API Endpoints
@admin_bp.route('/api/info', methods=['GET'])
def api_admin_info():
    """Get current admin information"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    admin_id = session.get('user_id')
    institution_id = session.get('institution_id')
    admin = get_admin_info(admin_id, institution_id)
    
    if admin:
        return jsonify({'admin': admin})
    return jsonify({'error': 'Admin not found'}), 404

@admin_bp.route('/api/stats', methods=['GET'])
def api_admin_stats():
    """Get dashboard statistics for admin"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM students WHERE institution_id = ?', (institution_id,))
        students = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM classes WHERE institution_id = ?', (institution_id,))
        classes = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM faculty WHERE institution_id = ?', (institution_id,))
        faculty = cursor.fetchone()[0]
    
    return jsonify({
        'stats': {
            'students': students,
            'faculty': faculty,
            'classes': classes
        }
    })


@admin_bp.route('/api/reset-institution', methods=['POST'])
def api_admin_reset_institution():
    """Wipe the institution workspace and reinitialize clean databases"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    if not institution_id:
        return jsonify({'status': 'error', 'message': 'Institution not found in session'}), 400

    result = reset_institution_data(institution_id)
    status_code = 200 if result.get('status') == 'success' else 500
    return jsonify(result), status_code

# ============ ACADEMIC STRUCTURE API ENDPOINTS ============

# Programs/Branches
@admin_bp.route('/api/programs', methods=['GET'])
def api_admin_programs():
    """Get all programs/branches"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    programs = get_all_programs(institution_id)
    return jsonify({'programs': programs})

@admin_bp.route('/api/create-program', methods=['POST'])
def api_admin_create_program():
    """Create a new program/branch"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    institution_id = session.get('institution_id')
    
    program_id = data.get('program_id')
    program_name = data.get('program_name')
    code = data.get('code')
    
    if not all([program_id, program_name, code]):
        return jsonify({'error': 'Missing required fields', 'status': 'error'}), 400
    
    result = create_program(program_id, program_name, code, institution_id)
    if result.get('status') == 'success':
        return jsonify(result), 201
    return jsonify(result), 400

@admin_bp.route('/api/delete-branch', methods=['POST'])
def api_admin_delete_branch():
    """Delete a branch/program"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    institution_id = session.get('institution_id')
    program_id = data.get('program_id')
    
    if not program_id:
        return jsonify({'status': 'error', 'message': 'Missing program_id'}), 400
    
    result = delete_program(program_id, institution_id)
    return jsonify(result), (201 if result.get('status') == 'success' else 400)

# Semesters
@admin_bp.route('/api/semesters/<int:program_id>', methods=['GET'])
def api_admin_semesters(program_id):
    """Get semesters for a program"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    semesters = get_semesters_by_program(program_id, institution_id)
    return jsonify({'semesters': semesters})

@admin_bp.route('/api/create-semester', methods=['POST'])
def api_admin_create_semester():
    """Create a new semester"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    institution_id = session.get('institution_id')
    
    semester_id = data.get('semester_id')
    semester_number = data.get('semester_number')
    program_id = data.get('program_id')
    
    if not all([semester_id, semester_number, program_id]):
        return jsonify({'error': 'Missing required fields', 'status': 'error'}), 400
    
    result = create_semester(semester_id, semester_number, program_id, institution_id)
    if result.get('status') == 'success':
        return jsonify(result), 201
    return jsonify(result), 400

@admin_bp.route('/api/delete-semester', methods=['POST'])
def api_admin_delete_semester():
    """Delete a semester"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    institution_id = session.get('institution_id')
    semester_id = data.get('semester_id')
    
    if not semester_id:
        return jsonify({'status': 'error', 'message': 'Missing semester_id'}), 400
    
    result = delete_semester(semester_id, institution_id)
    return jsonify(result), (201 if result.get('status') == 'success' else 400)

# Classes
@admin_bp.route('/api/classes/<int:semester_id>', methods=['GET'])
def api_admin_classes(semester_id):
    """Get classes for a semester"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    classes = get_classes_by_semester(semester_id, institution_id)
    return jsonify({'classes': classes})


@admin_bp.route('/api/class/<int:class_db_id>', methods=['GET', 'PUT'])
def api_admin_single_class(class_db_id):
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    if request.method == 'GET':
        record = get_class_by_id(class_db_id, institution_id)
        if not record:
            return jsonify({'status': 'error', 'message': 'Class not found'}), 404
        return jsonify({'class': record})

    data = request.get_json() or {}
    updates = {}
    if 'class_name' in data:
        updates['class_name'] = data['class_name']
    if 'section' in data:
        updates['section'] = data['section']

    if 'home_room_id' in data:
        home_room_id = data.get('home_room_id')
        if home_room_id in (None, '', 0):
            updates['home_room_id'] = None
            updates['room_number'] = None
        else:
            home_room = get_campus_room_by_id(home_room_id, institution_id)
            if not home_room:
                return jsonify({'status': 'error', 'message': 'Home room not found'}), 400
            if home_room['room_type'] not in ('classroom', 'custom'):
                return jsonify({'status': 'error', 'message': 'Home room must be classroom or custom'}), 400
            conflict = get_class_using_home_room(home_room_id, institution_id, exclude_class_id=class_db_id)
            if conflict:
                msg = f"Home room already assigned to {conflict['class_name']} ({conflict['section'] or 'Section'})"
                return jsonify({'status': 'error', 'message': msg}), 400
            updates['home_room_id'] = home_room_id
            updates['room_number'] = home_room.get('room_number')

    if not updates:
        return jsonify({'status': 'error', 'message': 'No valid fields provided'}), 400

    result = update_class_record(class_db_id, institution_id, **updates)
    status_code = 200 if result.get('status') == 'success' else 400
    return jsonify(result), status_code

@admin_bp.route('/api/create-class', methods=['POST'])
def api_admin_create_class():
    """Create a new class"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    institution_id = session.get('institution_id')
    
    class_id = data.get('class_id')
    class_name = data.get('class_name')
    semester_id = data.get('semester_id')
    program_id = data.get('program_id')
    section = data.get('section')
    room_number = data.get('room_number')
    home_room_id = data.get('home_room_id')
    
    if not all([class_id, class_name, semester_id, program_id, section]):
        return jsonify({'error': 'Missing required fields', 'status': 'error'}), 400

    room_number_value = room_number
    home_room = None
    home_room_id_clean = None
    if home_room_id not in (None, '', 0):
        try:
            home_room_id_clean = int(home_room_id)
        except (TypeError, ValueError):
            return jsonify({'status': 'error', 'message': 'Home room must be a number'}), 400
        home_room = get_campus_room_by_id(home_room_id_clean, institution_id)
        if not home_room:
            return jsonify({'status': 'error', 'message': 'Home room not found'}), 400
        if home_room['room_type'] not in ('classroom', 'custom'):
            return jsonify({'status': 'error', 'message': 'Home room must be a classroom or custom room'}), 400
        conflict = get_class_using_home_room(home_room_id_clean, institution_id)
        if conflict:
            msg = f"Home room already assigned to {conflict['class_name']} ({conflict['section'] or 'Section'})"
            return jsonify({'status': 'error', 'message': msg}), 400
        room_number_value = home_room.get('room_number')
    
    result = create_class(
        class_id,
        class_name,
        semester_id,
        program_id,
        section,
        institution_id,
        room_number_value,
        home_room_id_clean if home_room else None
    )
    if result.get('status') == 'success':
        return jsonify(result), 201
    return jsonify(result), 400


# Campus infrastructure management
@admin_bp.route('/api/campus/layout', methods=['GET'])
def api_admin_campus_layout():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    layout = get_campus_layout(institution_id)
    return jsonify({'layout': layout})


@admin_bp.route('/api/campus/warnings', methods=['GET'])
def api_admin_campus_warnings():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    unassigned_classes = get_classes_without_home_room(institution_id)
    return jsonify({
        'unassigned_classes': unassigned_classes,
        'unassigned_count': len(unassigned_classes)
    })


@admin_bp.route('/api/campus/floors', methods=['POST'])
def api_admin_campus_floors():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    max_floor = data.get('max_floor')
    if max_floor is None:
        return jsonify({'status': 'error', 'message': 'max_floor is required'}), 400

    institution_id = session.get('institution_id')
    floors = ensure_campus_floors(int(max_floor), institution_id)
    return jsonify({'status': 'success', 'floors': floors})


@admin_bp.route('/api/campus/layout/reset', methods=['POST'])
def api_admin_reset_campus_layout():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    result = reset_campus_layout(institution_id)
    status_code = 200 if result.get('status') == 'success' else 400
    return jsonify(result), status_code


@admin_bp.route('/api/campus/floors/<int:floor_id>/summary', methods=['GET'])
def api_admin_floor_summary(floor_id):
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    summary = get_floor_summary(floor_id, institution_id)
    if not summary:
        return jsonify({'status': 'error', 'message': 'Floor not found'}), 404
    return jsonify({'summary': summary})


@admin_bp.route('/api/campus/floors/<int:floor_id>', methods=['DELETE'])
def api_admin_delete_floor(floor_id):
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    result = delete_campus_floor(floor_id, institution_id)
    status_code = 200 if result.get('status') == 'success' else 400
    if result.get('status') == 'success':
        result['layout'] = get_campus_layout(institution_id)
    return jsonify(result), status_code


@admin_bp.route('/api/campus/sections', methods=['POST'])
def api_admin_campus_sections():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    raw_floor_ids = data.get('floor_ids') or []
    floor_ids = []
    for fid in raw_floor_ids:
        try:
            floor_ids.append(int(fid))
        except (TypeError, ValueError):
            continue
    institution_id = session.get('institution_id')

    result = create_campus_sections(name, floor_ids, institution_id)
    status_code = 200 if result.get('status') == 'success' else 400
    if result.get('status') == 'success':
        layout = get_campus_layout(institution_id)
        result['layout'] = layout
    return jsonify(result), status_code


@admin_bp.route('/api/campus/sections/<int:section_id>/summary', methods=['GET'])
def api_admin_section_summary(section_id):
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    summary = get_section_summary(section_id, institution_id)
    if not summary:
        return jsonify({'status': 'error', 'message': 'Section not found'}), 404
    return jsonify({'summary': summary})


@admin_bp.route('/api/campus/sections/<int:section_id>', methods=['DELETE'])
def api_admin_delete_section(section_id):
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    result = delete_campus_section(section_id, institution_id)
    status_code = 200 if result.get('status') == 'success' else 400
    if result.get('status') == 'success':
        result['layout'] = get_campus_layout(institution_id)
    return jsonify(result), status_code


@admin_bp.route('/api/campus/rooms/export', methods=['GET'])
def api_admin_export_rooms_csv():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    rows = get_campus_rooms_flat(institution_id)
    fieldnames = ['floor_number', 'floor_label', 'section_name', 'room_number', 'room_type', 'capacity', 'subject_code', 'custom_title', 'custom_function']
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({
            'floor_number': row.get('floor_number', ''),
            'floor_label': row.get('floor_label', ''),
            'section_name': row.get('section_name', ''),
            'room_number': row.get('room_number', ''),
            'room_type': row.get('room_type', ''),
            'capacity': row.get('capacity', ''),
            'subject_code': row.get('subject_code', ''),
            'custom_title': row.get('custom_title', ''),
            'custom_function': row.get('custom_function', '')
        })
    output.seek(0)
    buffer = io.BytesIO(output.getvalue().encode('utf-8'))
    filename = f"{institution_id}-campus-layout.csv"
    return send_file(buffer, mimetype='text/csv', as_attachment=True, download_name=filename)


@admin_bp.route('/api/campus/rooms/import', methods=['POST'])
def api_admin_import_rooms_csv():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file provided'}), 400

    upload = request.files['file']
    if upload.filename == '':
        return jsonify({'status': 'error', 'message': 'No file selected'}), 400

    try:
        content = upload.stream.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        return jsonify({'status': 'error', 'message': 'Unable to decode file'}), 400

    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return jsonify({'status': 'error', 'message': 'CSV file is empty'}), 400

    institution_id = session.get('institution_id')
    result = import_campus_rooms_from_rows(rows, institution_id)
    status_code = 200 if result.get('status') in ('success', 'warning') else 400
    return jsonify(result), status_code


@admin_bp.route('/api/campus/rooms', methods=['GET'])
def api_admin_list_rooms():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    room_type = request.args.get('room_type')
    rooms = get_campus_rooms(institution_id, room_type=room_type if room_type else None)
    return jsonify({'rooms': rooms})


@admin_bp.route('/api/campus/rooms', methods=['POST'])
def api_admin_create_room():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    room_number = data.get('room_number')
    room_type = data.get('room_type')
    floor_id = data.get('floor_id')
    section_id = data.get('section_id')
    capacity = data.get('capacity')
    subject_id = data.get('subject_id')
    custom_title = data.get('custom_title')
    custom_function = data.get('custom_function')

    if room_type == 'custom' and not custom_title:
        return jsonify({'status': 'error', 'message': 'Custom rooms require a title'}), 400

    institution_id = session.get('institution_id')
    try:
        floor_id_int = int(floor_id) if floor_id is not None else None
    except (TypeError, ValueError):
        floor_id_int = None
    try:
        section_id_int = int(section_id) if section_id is not None else None
    except (TypeError, ValueError):
        section_id_int = None
    try:
        capacity_val = int(capacity) if capacity not in (None, '') else 0
    except (TypeError, ValueError):
        capacity_val = 0
    try:
        subject_id_int = int(subject_id) if subject_id not in (None, '') else None
    except (TypeError, ValueError):
        subject_id_int = None

    result = create_campus_room(room_number, room_type, floor_id_int, institution_id,
                                section_id=section_id_int, capacity=capacity_val,
                                subject_id=subject_id_int, custom_title=custom_title,
                                custom_function=custom_function)
    status_code = 201 if result.get('status') == 'success' else 400
    if result.get('status') == 'success':
        result['layout'] = get_campus_layout(institution_id)
    return jsonify(result), status_code


@admin_bp.route('/api/campus/rooms/<int:room_id>/summary', methods=['GET'])
def api_admin_room_summary(room_id):
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    summary = get_room_summary(room_id, institution_id)
    if not summary:
        return jsonify({'status': 'error', 'message': 'Room not found'}), 404
    return jsonify({'summary': summary})


@admin_bp.route('/api/campus/rooms/<int:room_id>', methods=['PUT'])
def api_admin_update_room(room_id):
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    data = request.get_json() or {}
    payload = {}
    for key in ('room_number', 'capacity', 'section_id', 'assigned_subject_id', 'custom_title', 'custom_function'):
        if key not in data:
            continue
        value = data[key]
        if key == 'capacity' and value not in (None, ''):
            try:
                payload[key] = int(value)
            except (TypeError, ValueError):
                return jsonify({'status': 'error', 'message': 'Capacity must be a number'}), 400
        elif key in ('section_id', 'assigned_subject_id'):
            if value in (None, '', 0):
                payload[key] = None
            else:
                try:
                    payload[key] = int(value)
                except (TypeError, ValueError):
                    return jsonify({'status': 'error', 'message': f'{key} must be an integer'}), 400
        else:
            payload[key] = value
    if not payload:
        return jsonify({'status': 'error', 'message': 'No valid fields provided'}), 400
    result = update_campus_room(room_id, institution_id, **payload)
    status_code = 200 if result.get('status') == 'success' else 400
    if result.get('status') == 'success':
        result['layout'] = get_campus_layout(institution_id)
    return jsonify(result), status_code


@admin_bp.route('/api/campus/rooms/<int:room_id>', methods=['DELETE'])
def api_admin_delete_room(room_id):
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    result = delete_campus_room(room_id, institution_id)
    status_code = 200 if result.get('status') == 'success' else 400
    if result.get('status') == 'success':
        result['layout'] = get_campus_layout(institution_id)
    return jsonify(result), status_code

@admin_bp.route('/api/delete-class', methods=['POST'])
def api_admin_delete_class():
    """Delete a class"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    institution_id = session.get('institution_id')
    class_id = data.get('class_id')
    
    if not class_id:
        return jsonify({'status': 'error', 'message': 'Missing class_id'}), 400
    
    result = delete_class(class_id, institution_id)
    return jsonify(result), (201 if result.get('status') == 'success' else 400)

# Students
@admin_bp.route('/api/students', methods=['GET'])
def api_admin_all_students():
    """Get every student for cross-branch lookup"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    students = get_all_students_flat(institution_id)
    return jsonify({'students': students})

@admin_bp.route('/api/students/<int:class_id>', methods=['GET'])
def api_admin_students(class_id):
    """Get students in a class"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    students = get_students_by_class(class_id, institution_id)
    return jsonify({'students': students})

@admin_bp.route('/api/create-student', methods=['POST'])
def api_admin_create_student():
    """Create a new student"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    institution_id = session.get('institution_id')
    
    student_id = data.get('student_id')
    first_name = data.get('first_name')
    middle_name = data.get('middle_name')
    last_name = data.get('last_name')
    email = data.get('email')
    roll_no = data.get('roll_no')
    phone_number = data.get('phone_number')
    gender = data.get('gender')
    password = data.get('password', 'password123')
    program_id = data.get('program_id')
    semester_id = data.get('semester_id')
    class_id = data.get('class_id')
    
    if not all([student_id, first_name, last_name, email, password, program_id, semester_id, class_id]):
        return jsonify({'error': 'Missing required fields', 'status': 'error'}), 400
    
    result = create_student(student_id, first_name, middle_name, last_name, email, roll_no, phone_number, gender, password, 
                           program_id, semester_id, class_id, institution_id)
    if result.get('status') == 'success':
        return jsonify(result), 201
    return jsonify(result), 400

@admin_bp.route('/api/student/<int:student_id>', methods=['GET'])
def api_admin_get_student(student_id):
    """Get a single student"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    student = get_student_by_id(student_id, institution_id)
    if student:
        return jsonify({'student': student})
    return jsonify({'error': 'Student not found'}), 404

@admin_bp.route('/api/update-student', methods=['POST'])
def api_admin_update_student():
    """Update student information"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    institution_id = session.get('institution_id')
    
    student_id = data.get('id')
    student_id_str = data.get('student_id')
    first_name = data.get('first_name')
    middle_name = data.get('middle_name')
    last_name = data.get('last_name')
    email = data.get('email')
    roll_no = data.get('roll_no')
    phone_number = data.get('phone_number')
    password = data.get('password')
    
    if not all([student_id, student_id_str, first_name, last_name, email]):
        return jsonify({'error': 'Missing required fields', 'status': 'error'}), 400
    
    result = update_student(student_id, student_id_str, first_name, middle_name, last_name, email, roll_no, phone_number, password, institution_id)
    if result.get('status') == 'success':
        return jsonify(result), 200
    return jsonify(result), 400

@admin_bp.route('/api/delete-student', methods=['POST'])
def api_admin_delete_student():
    """Delete a student"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    institution_id = session.get('institution_id')
    student_id = data.get('student_id')
    
    if not student_id:
        return jsonify({'status': 'error', 'message': 'Missing student_id'}), 400
    
    result = delete_student(student_id, institution_id)
    return jsonify(result), (201 if result.get('status') == 'success' else 400)

# Faculty
@admin_bp.route('/api/faculty', methods=['GET'])
def api_admin_faculty():
    """Get all faculty members"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    faculty = get_all_faculty(institution_id)
    return jsonify({'faculty': faculty})

@admin_bp.route('/api/create-faculty', methods=['POST'])
def api_admin_create_faculty():
    """Create a new faculty member"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    institution_id = session.get('institution_id')
    
    faculty_id = data.get('faculty_id')
    first_name = data.get('first_name')
    middle_name = data.get('middle_name')
    last_name = data.get('last_name')
    email = data.get('email')
    phone_number = data.get('phone_number')
    gender = data.get('gender')
    password = data.get('password', 'password123')
    role = data.get('role', 'faculty')
    extra_notes = data.get('extra_notes', '')
    time_preference = data.get('time_preference')

    raw_teaching_flag = data.get('is_teaching_staff', False)
    if isinstance(raw_teaching_flag, str):
        is_teaching_staff = raw_teaching_flag.strip().lower() in ('true', '1', 'yes', 'on')
    else:
        is_teaching_staff = bool(raw_teaching_flag)

    majors = data.get('majors') or []
    if isinstance(majors, str):
        majors = [segment.strip() for segment in majors.split(',') if segment.strip()]
    elif not isinstance(majors, (list, tuple, set)):
        majors = []

    proficiency_input = data.get('proficiency_score')
    experience_input = data.get('experience_years')
    value_input = data.get('value_score')

    def _parse_int(raw_value):
        if raw_value in (None, '', []):
            return None
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return None

    proficiency_score = _parse_int(proficiency_input)
    experience_years = _parse_int(experience_input)
    value_score = _parse_int(value_input)

    if is_teaching_staff:
        if not majors:
            return jsonify({'status': 'error', 'message': 'Select at least one major for teaching staff'}), 400
        if proficiency_score is None or proficiency_score < 0 or proficiency_score > 100:
            return jsonify({'status': 'error', 'message': 'Provide a proficiency score between 0 and 100'}), 400
        if experience_years is None or experience_years < 0:
            return jsonify({'status': 'error', 'message': 'Provide a non-negative experience value'}), 400
        if value_input not in (None, '', []):
            if value_score is None or value_score < 1 or value_score > 10:
                return jsonify({'status': 'error', 'message': 'Value must be between 1 and 10 when provided'}), 400
        else:
            value_score = None
    else:
        majors = []
        proficiency_score = None
        experience_years = None
        value_score = None
    
    if not all([faculty_id, first_name, last_name, email, password]):
        return jsonify({'error': 'Missing required fields', 'status': 'error'}), 400
    
    result = create_faculty(
        faculty_id,
        first_name,
        middle_name,
        last_name,
        email,
        phone_number,
        gender,
        password,
        role,
        institution_id,
        extra_notes,
        time_preference,
        is_teaching_staff,
        majors,
        proficiency_score,
        experience_years,
        value_score
    )
    if result.get('status') == 'success':
        return jsonify(result), 201
    return jsonify(result), 400

@admin_bp.route('/api/faculty/<int:faculty_id>', methods=['GET'])
def api_admin_get_faculty(faculty_id):
    """Get a single faculty member"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    faculty = get_faculty_by_id(faculty_id, institution_id)
    if faculty:
        return jsonify({'faculty': faculty})
    return jsonify({'error': 'Faculty not found'}), 404

@admin_bp.route('/api/update-faculty', methods=['POST'])
def api_admin_update_faculty():
    """Update faculty information"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    institution_id = session.get('institution_id')
    
    faculty_id = data.get('id')
    faculty_id_str = data.get('faculty_id')
    first_name = data.get('first_name')
    middle_name = data.get('middle_name')
    last_name = data.get('last_name')
    email = data.get('email')
    phone_number = data.get('phone_number')
    role = data.get('role')
    password = data.get('password')
    time_preference = data.get('time_preference')
    
    if not all([faculty_id, faculty_id_str, first_name, last_name, email]):
        return jsonify({'error': 'Missing required fields', 'status': 'error'}), 400
    
    result = update_faculty(
        faculty_id,
        faculty_id_str,
        first_name,
        middle_name,
        last_name,
        email,
        phone_number,
        role,
        password,
        institution_id,
        time_preference
    )
    if result.get('status') == 'success':
        return jsonify(result), 200
    return jsonify(result), 400

@admin_bp.route('/api/delete-faculty', methods=['POST'])
def api_admin_delete_faculty():
    """Delete a faculty member"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    institution_id = session.get('institution_id')
    faculty_id = data.get('faculty_id')
    
    if not faculty_id:
        return jsonify({'status': 'error', 'message': 'Missing faculty_id'}), 400
    
    result = delete_faculty(faculty_id, institution_id)
    return jsonify(result), (201 if result.get('status') == 'success' else 400)

@admin_bp.route('/api/faculty/<int:faculty_id>/classes', methods=['GET'])
def api_admin_faculty_classes(faculty_id):
    """Get classes assigned to faculty"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    classes = get_faculty_classes(faculty_id, institution_id)
    return jsonify({'classes': classes})


@admin_bp.route('/api/faculty/<int:faculty_id>/subjects', methods=['GET'])
def api_admin_faculty_subjects(faculty_id):
    """Get subjects linked to faculty"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    subjects = get_faculty_subjects(faculty_id, institution_id)
    return jsonify({'subjects': subjects})


@admin_bp.route('/api/faculty/<int:faculty_id>/subjects/<int:subject_id>', methods=['DELETE'])
def api_admin_remove_faculty_subject(faculty_id, subject_id):
    """Remove a single subject assignment from a faculty member."""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    removed = remove_faculty_subject_assignment(faculty_id, subject_id, institution_id)
    if removed:
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Assignment not found'}), 404


# ============ SUBJECT MANAGEMENT ============

@admin_bp.route('/api/semesters/all', methods=['GET'])
def api_admin_all_semesters():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    semesters = get_all_semesters_flat(institution_id)
    return jsonify({'semesters': semesters})


@admin_bp.route('/api/subjects', methods=['GET'])
def api_admin_subjects():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    subjects = get_all_subjects(institution_id)
    return jsonify({'subjects': subjects})


@admin_bp.route('/api/create-subject', methods=['POST'])
def api_admin_create_subject():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    institution_id = session.get('institution_id')

    subject_id = data.get('subject_id')
    name = data.get('name')
    description = data.get('description', '')
    subject_type = data.get('subject_type')
    semester_id = data.get('semester_id')
    student_ids = data.get('student_ids') or []
    semester_ids = data.get('semester_ids') or []
    teaching_hours = data.get('teaching_hours')
    delivery_mode = data.get('delivery_mode')
    required_majors = data.get('required_majors') or []
    min_proficiency = data.get('min_proficiency')
    min_experience = data.get('min_experience')
    min_value = data.get('min_value')
    has_theory_component = data.get('has_theory_component')
    has_practical_component = data.get('has_practical_component')
    theory_hours = data.get('theory_hours')
    practical_hours = data.get('practical_hours')
    requires_lab = data.get('requires_lab')

    if isinstance(required_majors, str):
        required_majors = [segment.strip() for segment in required_majors.split(',') if segment.strip()]
    elif not isinstance(required_majors, (list, tuple, set)):
        required_majors = []

    def _parse_int(raw_value):
        if raw_value in (None, '', []):
            return None
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return None

    min_proficiency_value = _parse_int(min_proficiency)
    min_experience_value = _parse_int(min_experience)
    min_value_value = _parse_int(min_value)

    if not required_majors:
        return jsonify({'status': 'error', 'message': 'Select at least one major requirement'}), 400

    if min_proficiency_value is None or min_proficiency_value < 0 or min_proficiency_value > 100:
        return jsonify({'status': 'error', 'message': 'Provide a minimum proficiency between 0 and 100'}), 400

    if min_experience_value is None or min_experience_value < 0:
        return jsonify({'status': 'error', 'message': 'Provide a non-negative minimum experience'}), 400

    if min_value not in (None, '', []):
        if min_value_value is None or min_value_value < 1 or min_value_value > 10:
            return jsonify({'status': 'error', 'message': 'Value must be between 1 and 10 when provided'}), 400
    else:
        min_value_value = None

    if isinstance(semester_ids, str):
        semester_ids = [sem_id.strip() for sem_id in semester_ids.split(',') if sem_id.strip()]
    elif not isinstance(semester_ids, list):
        semester_ids = []

    if not all([subject_id, name, subject_type]):
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

    def _parse_bool_flag(value):
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        text = str(value).strip().lower()
        if text == '':
            return None
        if text in ('1', 'true', 'yes', 'y', 'on', 'checked'):
            return True
        if text in ('0', 'false', 'no', 'n', 'off', 'unchecked'):
            return False
        return None

    normalized_delivery = (delivery_mode or 'theory').lower()
    theory_flag = _parse_bool_flag(has_theory_component)
    practical_flag = _parse_bool_flag(has_practical_component)
    if theory_flag is None and practical_flag is None:
        theory_flag = normalized_delivery != 'practical'
        practical_flag = normalized_delivery == 'practical'
    else:
        theory_flag = bool(theory_flag)
        practical_flag = bool(practical_flag)

    if not theory_flag and not practical_flag:
        return jsonify({'status': 'error', 'message': 'Select at least one delivery component'}), 400

    requires_lab_flag = _parse_bool_flag(requires_lab)
    if requires_lab_flag is None:
        requires_lab_flag = practical_flag
    if not practical_flag:
        requires_lab_flag = False

    delivery_mode = 'practical' if practical_flag else 'theory'

    result = create_subject(
        subject_id,
        name,
        description,
        subject_type,
        institution_id,
        int(semester_id) if semester_id else None,
        student_ids,
        semester_ids,
        teaching_hours,
        delivery_mode,
        required_majors,
        min_proficiency_value,
        min_experience_value,
        min_value_value,
        theory_flag,
        practical_flag,
        theory_hours,
        practical_hours,
        requires_lab_flag
    )

    status_code = 201 if result.get('status') == 'success' else 400
    return jsonify(result), status_code


@admin_bp.route('/api/delete-subject', methods=['POST'])
def api_admin_delete_subject():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    subject_id = data.get('subject_id')
    institution_id = session.get('institution_id')

    if not subject_id:
        return jsonify({'status': 'error', 'message': 'Missing subject_id'}), 400

    result = delete_subject(subject_id, institution_id)
    status_code = 200 if result.get('status') == 'success' else 400
    return jsonify(result), status_code


@admin_bp.route('/api/subjects/<int:subject_id>', methods=['GET'])
def api_admin_get_subject(subject_id):
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    subject = get_subject_by_id(subject_id, institution_id)
    if not subject:
        return jsonify({'error': 'Subject not found'}), 404
    return jsonify({'subject': subject})


@admin_bp.route('/api/subjects/<int:subject_id>/update', methods=['PUT'])
def api_admin_update_subject(subject_id):
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    institution_id = session.get('institution_id')

    result = update_subject(subject_id, data, institution_id)
    status_code = 200 if result.get('status') == 'success' else 400
    return jsonify(result), status_code


@admin_bp.route('/api/subjects/<int:subject_id>/resources', methods=['GET'])
def api_admin_subject_resources(subject_id):
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    subject = get_subject_by_id(subject_id, institution_id)
    if not subject:
        return jsonify({'error': 'Subject not found'}), 404

    resources = get_subject_resources(subject_id, institution_id)
    return jsonify({'subject': subject, 'resources': resources})


@admin_bp.route('/api/resources/<int:resource_id>/delete', methods=['POST'])
def api_admin_delete_resource(resource_id):
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    deleted = delete_subject_resource(resource_id, institution_id)
    if deleted:
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Resource not found'}), 404


@admin_bp.route('/api/resources/<int:resource_id>/download', methods=['GET'])
def api_admin_download_resource(resource_id):
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    resource = get_subject_resource(resource_id, institution_id)
    if not resource:
        return jsonify({'error': 'Resource not found'}), 404

    return send_file(resource['file_path'], as_attachment=True, download_name=resource['file_name'])

@admin_bp.route('/api/assign-faculty-to-subjects', methods=['POST'])
def api_admin_assign_faculty_to_subjects():
    """Assign faculty to one or more subjects"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    institution_id = session.get('institution_id')

    faculty_id = data.get('faculty_id')
    subject_ids = data.get('subject_ids') or []

    if not faculty_id:
        return jsonify({'status': 'error', 'message': 'Missing faculty_id'}), 400

    try:
        faculty_id = int(faculty_id)
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Invalid faculty_id'}), 400

    result = assign_faculty_to_subjects(faculty_id, subject_ids, institution_id)
    status_code = 201 if result.get('status') == 'success' else 400
    return jsonify(result), status_code


@admin_bp.route('/api/assignments/hotfix', methods=['POST'])
def api_admin_assignment_hotfix():
    """Auto-assign faculty to subjects based on targeting rules."""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    targeting_mode = (data.get('targeting_mode') or 'strict').lower()
    institution_id = session.get('institution_id')

    result = auto_assign_subject_faculty(institution_id, targeting_mode)
    status_code = 200 if result.get('status') == 'success' else 400
    return jsonify(result), status_code

# ============ CSV UPLOAD/DOWNLOAD ============
@admin_bp.route('/api/upload-faculty-csv', methods=['POST'])
def api_upload_faculty_csv():
    """Upload and process faculty CSV file"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No file selected'}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({'status': 'error', 'message': 'Only CSV files allowed'}), 400
    
    try:
        stream = io.StringIO(file.stream.read().decode('UTF-8'), newline=None)
        csv_data = csv.DictReader(stream)
        
        success_count = 0
        error_count = 0
        errors = []

        def _parse_bool(value):
            if value is None:
                return False
            if isinstance(value, bool):
                return value
            text = str(value).strip().lower()
            if not text:
                return False
            return text in ('1', 'true', 'yes', 'y', 'on')

        def _parse_list(value):
            if not value:
                return []
            if isinstance(value, (list, tuple, set)):
                return [str(item).strip() for item in value if str(item).strip()]
            return [segment.strip() for segment in str(value).split(',') if segment.strip()]

        def _parse_int(value):
            if value in (None, ''):
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
        
        for row_num, row in enumerate(csv_data, 1):
            try:
                faculty_id = row.get('faculty_id', '').strip()
                first_name = row.get('first_name', '').strip()
                last_name = row.get('last_name', '').strip()
                email = row.get('email', '').strip()
                phone_number = row.get('phone_number', '').strip()
                gender = row.get('gender', '').strip()
                role = row.get('role', 'faculty').strip()
                password = row.get('password', '').strip()
                class_ids_str = row.get('class_ids', '').strip()
                extra_notes = row.get('extra_notes', '').strip()
                time_preference = row.get('time_preference', '').strip()
                is_teaching_staff = _parse_bool(row.get('is_teaching_staff'))
                majors_list = _parse_list(row.get('majors'))
                proficiency_score = _parse_int(row.get('proficiency_score'))
                experience_years = _parse_int(row.get('experience_years'))
                value_score = _parse_int(row.get('value_score'))
                
                if not all([faculty_id, first_name, last_name, email, password]):
                    error_count += 1
                    errors.append(f"Row {row_num}: Missing required fields")
                    continue

                if is_teaching_staff:
                    if not majors_list:
                        error_count += 1
                        errors.append(f"Row {row_num}: Teaching staff rows must include majors")
                        continue
                    if proficiency_score is None or not (0 <= proficiency_score <= 100):
                        error_count += 1
                        errors.append(f"Row {row_num}: Provide proficiency between 0 and 100 for teaching staff")
                        continue
                    if experience_years is None or experience_years < 0:
                        error_count += 1
                        errors.append(f"Row {row_num}: Provide a non-negative experience value for teaching staff")
                        continue
                    if value_score is not None and (value_score < 1 or value_score > 10):
                        error_count += 1
                        errors.append(f"Row {row_num}: Value score must be between 1 and 10")
                        continue
                else:
                    majors_list = []
                    proficiency_score = None
                    experience_years = None
                    value_score = None
                
                result = create_faculty(
                    faculty_id,
                    first_name,
                    row.get('middle_name', '').strip(),
                    last_name,
                    email,
                    phone_number,
                    gender,
                    password,
                    role,
                    institution_id,
                    extra_notes,
                    time_preference,
                    is_teaching_staff=is_teaching_staff,
                    majors=majors_list,
                    proficiency_score=proficiency_score,
                    experience_years=experience_years,
                    value_score=value_score
                )
                
                if result.get('status') == 'success':
                    if class_ids_str:
                        class_ids = [cid.strip() for cid in class_ids_str.split(',')]
                        subjects = [subj.strip() for subj in row.get('subjects', '').split(',')] if row.get('subjects', '').strip() else ['']*len(class_ids)
                        with get_db_connection(institution_id, 'student') as conn:
                            cursor = conn.cursor()
                            cursor.execute('SELECT id FROM faculty WHERE faculty_id = ? AND institution_id = ?', 
                                         (faculty_id, institution_id))
                            fac_row = cursor.fetchone()
                            if fac_row:
                                fac_db_id = fac_row['id']
                                for idx, class_id in enumerate(class_ids):
                                    try:
                                        subject = subjects[idx] if idx < len(subjects) else ''
                                        assign_faculty_to_class(fac_db_id, int(class_id), institution_id, subject)
                                    except Exception as e:
                                        errors.append(f"Row {row_num}: Could not assign class {class_id}: {str(e)}")
                    
                    success_count += 1
                else:
                    error_count += 1
                    errors.append(f"Row {row_num}: {result.get('message', 'Unknown error')}")
            except Exception as e:
                error_count += 1
                errors.append(f"Row {row_num}: {str(e)}")
        
        return jsonify({
            'status': 'success',
            'message': f'Imported {success_count} faculty members',
            'success_count': success_count,
            'error_count': error_count,
            'errors': errors[:10]
        })
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error processing file: {str(e)}'}), 400

@admin_bp.route('/api/upload-student-csv', methods=['POST'])
def api_upload_student_csv():
    """Upload and process student CSV file"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No file selected'}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({'status': 'error', 'message': 'Only CSV files allowed'}), 400
    
    try:
        stream = io.StringIO(file.stream.read().decode('UTF-8'), newline=None)
        csv_data = csv.DictReader(stream)
        
        success_count = 0
        error_count = 0
        errors = []
        
        for row_num, row in enumerate(csv_data, 1):
            try:
                student_id = row.get('student_id', '').strip()
                first_name = row.get('first_name', '').strip()
                last_name = row.get('last_name', '').strip()
                email = row.get('email', '').strip()
                roll_no = row.get('roll_no', '').strip()
                phone_number = row.get('phone_number', '').strip()
                gender = row.get('gender', '').strip()
                password = row.get('password', '').strip()
                program_id = row.get('program_id', '').strip()
                semester_id = row.get('semester_id', '').strip()
                class_id = row.get('class_id', '').strip()
                
                if not all([student_id, first_name, last_name, email, password, program_id, class_id]):
                    error_count += 1
                    errors.append(f"Row {row_num}: Missing required fields")
                    continue
                
                result = create_student(student_id, first_name, row.get('middle_name', '').strip(), last_name, 
                                      email, roll_no, phone_number, gender, password, 
                                      int(program_id), int(semester_id) if semester_id else None, int(class_id), institution_id)
                
                if result.get('status') == 'success':
                    success_count += 1
                else:
                    error_count += 1
                    errors.append(f"Row {row_num}: {result.get('message', 'Unknown error')}")
            except Exception as e:
                error_count += 1
                errors.append(f"Row {row_num}: {str(e)}")
        
        return jsonify({
            'status': 'success',
            'message': f'Imported {success_count} students',
            'success_count': success_count,
            'error_count': error_count,
            'errors': errors[:10]
        })
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error processing file: {str(e)}'}), 400

@admin_bp.route('/api/download-faculty-csv')
def api_download_faculty_csv():
    """Download all faculty as CSV"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                id,
                faculty_id,
                first_name,
                middle_name,
                last_name,
                email,
                phone_number,
                gender,
                role,
                extra_notes,
                time_preference,
                is_teaching_staff,
                majors,
                proficiency_score,
                experience_years,
                value_score
            FROM faculty
            WHERE institution_id = ?
            ORDER BY last_name
        ''', (institution_id,))
        
        rows = cursor.fetchall()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'faculty_id',
            'first_name',
            'middle_name',
            'last_name',
            'email',
            'phone_number',
            'gender',
            'role',
            'extra_notes',
            'password',
            'class_ids',
            'subjects',
            'time_preference',
            'is_teaching_staff',
            'majors',
            'proficiency_score',
            'experience_years',
            'value_score'
        ])
        
        for row in rows:
            # Get assigned classes and subjects for this faculty
            cursor.execute('''
                SELECT fc.class_id, fc.subject, c.class_name
                FROM faculty_classes fc
                JOIN classes c ON fc.class_id = c.id
                WHERE fc.faculty_id = ?
                ORDER BY c.class_name
            ''', (row['id'],))
            
            assigned_classes = cursor.fetchall()
            class_ids_str = ','.join([str(ac['class_id']) for ac in assigned_classes])
            subjects_str = ','.join([ac['subject'] or '' for ac in assigned_classes])
            
            writer.writerow([
                row['faculty_id'],
                row['first_name'],
                row['middle_name'] or '',
                row['last_name'],
                row['email'],
                row['phone_number'] or '',
                row['gender'] or '',
                row['role'] or 'faculty',
                row['extra_notes'] or '',
                '***',
                class_ids_str,
                subjects_str,
                row['time_preference'] or '',
                1 if row['is_teaching_staff'] else 0,
                row['majors'] or '',
                row['proficiency_score'] if row['proficiency_score'] is not None else '',
                row['experience_years'] if row['experience_years'] is not None else '',
                row['value_score'] if row['value_score'] is not None else ''
            ])
        
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name='faculty.csv'
        )

@admin_bp.route('/api/download-student-csv')
def api_download_student_csv():
    """Download all students as CSV"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT student_id, first_name, middle_name, last_name, email, roll_no, phone_number, gender, program_id, semester_id, class_id
            FROM students
            WHERE institution_id = ?
            ORDER BY last_name
        ''', (institution_id,))
        
        rows = cursor.fetchall()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['student_id', 'first_name', 'middle_name', 'last_name', 'email', 'roll_no', 'phone_number', 'gender', 'password', 'program_id', 'semester_id', 'class_id'])
        
        for row in rows:
            writer.writerow([
                row['student_id'],
                row['first_name'],
                row['middle_name'] or '',
                row['last_name'],
                row['email'],
                row['roll_no'] or '',
                row['phone_number'] or '',
                row['gender'] or '',
                '***',
                row['program_id'],
                row['semester_id'] or '',
                row['class_id']
            ])
        
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name='students.csv'
        )


@admin_bp.route('/api/export-all', methods=['GET'])
def api_export_all_data():
    """Export the entire institution dataset as JSON"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    try:
        payload = export_full_institution_data(institution_id)
        json_data = json.dumps(payload, indent=2)
        filename = f"{institution_id}-acrm-full-backup.json"
        return Response(
            json_data,
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as exc:
        return jsonify({'status': 'error', 'message': str(exc)}), 500


@admin_bp.route('/api/import-all', methods=['POST'])
def api_import_all_data():
    """Import a previously exported full dataset"""
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No file selected'}), 400

    try:
        payload = json.load(file.stream)
    except json.JSONDecodeError:
        return jsonify({'status': 'error', 'message': 'Invalid JSON file'}), 400

    institution_id = session.get('institution_id')
    try:
        summary = import_full_institution_data(institution_id, payload)
        return jsonify({
            'status': 'success',
            'message': 'Full dataset imported successfully',
            'summary': summary
        })
    except Exception as exc:
        return jsonify({'status': 'error', 'message': str(exc)}), 500


# ============ TIMETABLE PROTOTYPE API ============

_TIMETABLE_DAY_LABELS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def _build_day_labels(days_per_week):
    try:
        count = int(days_per_week)
    except (TypeError, ValueError):
        count = 5
    count = max(1, min(len(_TIMETABLE_DAY_LABELS), count))
    return _TIMETABLE_DAY_LABELS[:count]

def _normalize_id_list(raw_values):
    """Convert a mixed list into clean integer IDs while preserving order."""
    if not isinstance(raw_values, (list, tuple, set)):
        return []
    seen = set()
    normalized = []
    for value in raw_values:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number <= 0 or number in seen:
            continue
        seen.add(number)
        normalized.append(number)
    return normalized


def _normalize_breaks(raw_breaks):
    """Keep only valid break definitions with start + positive duration."""
    normalized = []
    if not isinstance(raw_breaks, list):
        return normalized
    for item in raw_breaks:
        if not isinstance(item, dict):
            continue
        start = (item.get('start') or '').strip()
        duration = item.get('duration_minutes')
        try:
            duration_value = int(duration)
        except (TypeError, ValueError):
            continue
        if not start or duration_value <= 0:
            continue
        normalized.append({'start': start, 'duration_minutes': duration_value})
        if len(normalized) >= 8:
            break
    return normalized


def _normalize_bool(value, default=True):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ('true', '1', 'yes', 'on'):
            return True
        if lowered in ('false', '0', 'no', 'off'):
            return False
    try:
        return bool(int(value))
    except (TypeError, ValueError):
        return default


@admin_bp.route('/api/timetable/runs', methods=['GET'])
def api_admin_timetable_runs():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    if not institution_id:
        return jsonify({'status': 'error', 'message': 'Missing institution context'}), 400

    limit = request.args.get('limit', default=8, type=int)
    if not limit or limit <= 0:
        limit = 5
    limit = min(limit, 20)

    try:
        runs = get_recent_timetable_runs(institution_id, limit=limit)
    except Exception as exc:
        return jsonify({'status': 'error', 'message': str(exc)}), 500

    return jsonify({'status': 'success', 'runs': runs})


@admin_bp.route('/api/timetable/run/<int:run_id>', methods=['DELETE'])
def api_admin_delete_timetable_run(run_id):
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    if not institution_id:
        return jsonify({'status': 'error', 'message': 'Missing institution context'}), 400

    try:
        removed = delete_timetable_run(run_id, institution_id)
    except Exception as exc:  # pylint: disable=broad-except
        return jsonify({'status': 'error', 'message': str(exc)}), 500

    if not removed:
        return jsonify({'status': 'error', 'message': 'Prototype run not found.'}), 404

    return jsonify({'status': 'success', 'message': f'Run #{run_id} deleted.'})


@admin_bp.route('/api/timetable/run', methods=['POST'])
def api_admin_create_timetable_run_config():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    if not institution_id:
        return jsonify({'status': 'error', 'message': 'Missing institution context'}), 400

    payload = request.get_json() or {}
    raw_action = payload.get('action')
    if isinstance(raw_action, str):
        action = raw_action.strip().lower() or 'run'
    else:
        action = 'run'
    config = {
        'targeting_mode': payload.get('targeting_mode'),
        'margin_proficiency': payload.get('margin_proficiency'),
        'margin_experience': payload.get('margin_experience'),
        'focus_mode': payload.get('focus_mode'),
        'focus_branches': _normalize_id_list(payload.get('focus_branches') or []),
        'focus_semesters': _normalize_id_list(payload.get('focus_semesters') or []),
        'focus_classes': _normalize_id_list(payload.get('focus_classes') or []),
        'slots_per_day': payload.get('slots_per_day'),
        'slot_duration_minutes': payload.get('slot_duration_minutes'),
        'days_per_week': payload.get('days_per_week'),
        'term_weeks': payload.get('term_weeks'),
        'first_slot_start': payload.get('first_slot_start'),
        'lab_multi_slot': _normalize_bool(payload.get('lab_multi_slot'), True),
        'breaks': _normalize_breaks(payload.get('breaks') or [])
    }

    try:
        result = create_timetable_run(institution_id, config)
    except Exception as exc:
        return jsonify({'status': 'error', 'message': str(exc)}), 500

    if result.get('status') != 'success':
        return jsonify(result), 400

    engine_summary = None
    run_id = result.get('run_id')
    if action == 'save':
        message = 'Preferences saved. They will be available for the next prototype run.'
    else:
        try:
            engine_summary = process_timetable_run(run_id, institution_id)
        except TimetableEngineError as exc:
            current_app.logger.exception('Timetable run %s failed validation', run_id)
            if run_id:
                update_timetable_run_status(run_id, institution_id, 'failed')
            return jsonify({'status': 'error', 'message': str(exc)}), 500
        except Exception as exc:  # pylint: disable=broad-except
            current_app.logger.exception('Timetable engine crashed for run %s', run_id)
            if run_id:
                update_timetable_run_status(run_id, institution_id, 'failed')
            return jsonify({'status': 'error', 'message': f'Timetable engine failed to execute: {exc}'}), 500

        scheduled = engine_summary.get('sessions_scheduled', 0)
        unscheduled = engine_summary.get('sessions_unscheduled', 0)
        engine_status = engine_summary.get('status', 'completed').lower()
        message = (
            f"Prototype run {engine_status}. Scheduled {scheduled} session"
            f"{'s' if scheduled != 1 else ''}."
        )
        if unscheduled:
            message += f" {unscheduled} session{'s' if unscheduled != 1 else ''} still pending placement."
        else:
            message += ' All requested blocks were placed.'

    response = {
        'status': 'success',
        'run_id': result.get('run_id'),
        'message': message
    }
    if engine_summary:
        response['engine_summary'] = engine_summary
    return jsonify(response), 201


@admin_bp.route('/api/timetable/prototype-preview', methods=['GET'])
def api_admin_timetable_preview():
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    if not institution_id:
        return jsonify({'status': 'error', 'message': 'Missing institution context'}), 400

    run_id = request.args.get('run_id', type=int)
    status_filter = request.args.get('status', default='completed')

    if run_id:
        run = get_timetable_run(run_id, institution_id)
        if not run:
            return jsonify({'status': 'error', 'message': 'Prototype run not found.'}), 404
    else:
        run = get_latest_timetable_run(institution_id, status_filter)

    if not run:
        return jsonify({
            'status': 'empty',
            'message': 'No prototype runs yet.',
            'run': None,
            'rollups': {'totals': {}, 'faculty': [], 'classes': []},
            'layout': {}
        })

    rollups = get_timetable_preview_snapshot(run['id'], institution_id, rollup_limit=8)
    layout = {
        'slots_per_day': run.get('slots_per_day'),
        'slot_duration_minutes': run.get('slot_duration_minutes'),
        'days_per_week': run.get('days_per_week'),
        'term_weeks': run.get('term_weeks'),
        'first_slot_start': run.get('first_slot_start'),
        'day_labels': _build_day_labels(run.get('days_per_week'))
    }

    return jsonify({
        'status': 'success',
        'run': run,
        'rollups': rollups,
        'summary': rollups.get('totals', {}),
        'layout': layout
    })


@admin_bp.route('/api/timetable/faculty/<int:faculty_id>', methods=['GET'])
def api_admin_faculty_timetable(faculty_id):
    if not _require_admin_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    if not institution_id:
        return jsonify({'status': 'error', 'message': 'Missing institution context'}), 400

    run_id = request.args.get('run_id', type=int)
    status_filter = request.args.get('status', default='completed')

    if run_id:
        run = get_timetable_run(run_id, institution_id)
        if not run:
            return jsonify({'status': 'error', 'message': 'Prototype run not found.'}), 404
    else:
        run = get_latest_timetable_run(institution_id, status_filter)

    if not run:
        return jsonify({
            'status': 'empty',
            'message': 'No prototype runs yet.',
            'run': None,
            'sessions': [],
            'layout': {}
        })

    sessions = get_timetable_sessions_for_faculty(run['id'], institution_id, faculty_id)
    layout = {
        'slots_per_day': run.get('slots_per_day'),
        'slot_duration_minutes': run.get('slot_duration_minutes'),
        'days_per_week': run.get('days_per_week'),
        'term_weeks': run.get('term_weeks'),
        'first_slot_start': run.get('first_slot_start'),
        'day_labels': _build_day_labels(run.get('days_per_week'))
    }

    return jsonify({
        'status': 'success',
        'run': run,
        'sessions': sessions,
        'layout': layout
    })

"""Faculty dashboard and assignment routes"""
import os
import mimetypes
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, send_file
from werkzeug.utils import secure_filename
from routes.database import (get_faculty_info, get_faculty_classes, get_class_faculty_assignments,
                     create_assignment, get_assignment_students, update_student_assignment_status,
                     get_db_connection, get_all_subjects, get_subject_resources,
                     add_subject_resource, get_subject_resource, get_subject_by_id,
                     get_subject_storage_path, get_subject_chapters, create_subject_chapter,
                     get_chapter_resources, get_subject_chapter, delete_subject_chapter,
                     delete_subject_resource)

faculty_bp = Blueprint('faculty', __name__, url_prefix='/faculty')

TEXT_PREVIEW_EXTENSIONS = {
    '.txt', '.md', '.py', '.java', '.js', '.ts', '.css', '.html', '.json', '.csv',
    '.xml', '.yaml', '.yml', '.ini', '.log', '.sql'
}
IMAGE_PREVIEW_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp'}
VIDEO_PREVIEW_EXTENSIONS = {'.mp4', '.webm', '.ogg', '.mov', '.avi', '.mkv'}
PDF_PREVIEW_EXTENSIONS = {'.pdf'}
DOCUMENT_PREVIEW_EXTENSIONS = {'.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx'}
MAX_TEXT_PREVIEW_BYTES = 200 * 1024


def _detect_preview_type(file_name):
    """Return the preview type string based on file extension."""
    ext = os.path.splitext(file_name or '')[1].lower()
    if ext in TEXT_PREVIEW_EXTENSIONS:
        return 'text'
    if ext in IMAGE_PREVIEW_EXTENSIONS:
        return 'image'
    if ext in VIDEO_PREVIEW_EXTENSIONS:
        return 'video'
    if ext in PDF_PREVIEW_EXTENSIONS:
        return 'pdf'
    if ext in DOCUMENT_PREVIEW_EXTENSIONS:
        return 'document'
    return 'none'


def _resource_mimetype(file_name):
    """Best effort mime-type detection for preview/streaming."""
    return mimetypes.guess_type(file_name or '')[0] or 'application/octet-stream'


def _build_resource_preview_payload(resource):
    """Attach preview metadata for frontend rendering."""
    preview_type = _detect_preview_type(resource.get('file_name'))
    preview_payload = {
        'preview_type': preview_type,
        'preview_stream_url': None,
        'text_preview_url': None,
        'document_preview_url': None,
        'preview_open_url': None,
        'mime_type': _resource_mimetype(resource.get('file_name'))
    }

    if preview_type == 'text':
        preview_payload['text_preview_url'] = url_for(
            'faculty.api_faculty_text_preview_resource', resource_id=resource['id']
        )
    elif preview_type in {'image', 'video', 'pdf'}:
        preview_payload['preview_stream_url'] = url_for(
            'faculty.api_faculty_stream_resource', resource_id=resource['id']
        )
    elif preview_type == 'document':
        preview_payload['preview_open_url'] = url_for('faculty.api_faculty_stream_resource', resource_id=resource['id'])

    return preview_payload


def _sanitize_relative_path(relative_path):
    """Return a safe, normalized relative path for folder uploads."""
    if not relative_path:
        return ''
    cleaned = relative_path.replace('\\', '/').strip().lstrip('/')
    safe_segments = [segment for segment in cleaned.split('/') if segment not in ('', '.', '..')]
    return '/'.join(safe_segments)

    return preview_payload

def _require_faculty_role():
    """Check if user is faculty"""
    if 'role' not in session or session['role'] != 'faculty':
        return False
    return True

@faculty_bp.route('/dashboard')
def faculty_dashboard():
    """Faculty dashboard"""
    if not _require_faculty_role():
        return redirect(url_for('home.login'))
    
    faculty_id = session.get('user_id')
    institution_id = session.get('institution_id')
    faculty = get_faculty_info(faculty_id, institution_id)
    
    return render_template('faculty/dashboard.html', faculty=faculty)

@faculty_bp.route('/classroom')
def faculty_classroom():
    """Faculty classroom management"""
    if not _require_faculty_role():
        return redirect(url_for('home.login'))
    
    return render_template('faculty/classroom.html')

@faculty_bp.route('/timetable')
def faculty_timetable():
    """Faculty timetable"""
    if not _require_faculty_role():
        return redirect(url_for('home.login'))
    
    return render_template('faculty/timetable.html')


@faculty_bp.route('/resources')
def faculty_resources():
    """Faculty resources browser"""
    if not _require_faculty_role():
        return redirect(url_for('home.login'))

    return render_template('faculty/resources.html')

@faculty_bp.route('/assignment/<int:assignment_id>')
def faculty_assignment_detail(assignment_id):
    """View assignment details and student submissions"""
    if not _require_faculty_role():
        return redirect(url_for('home.login'))
    
    institution_id = session.get('institution_id')
    students = get_assignment_students(assignment_id, institution_id)
    return render_template('faculty/assignment_detail.html', assignment_id=assignment_id, students=students)

# API Endpoints for Faculty
@faculty_bp.route('/api/classes', methods=['GET'])
def api_faculty_classes():
    """Get all classes for the logged-in faculty"""
    if not _require_faculty_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    faculty_id = session.get('user_id')
    institution_id = session.get('institution_id')
    
    classes = get_faculty_classes(faculty_id, institution_id)
    return jsonify({'classes': classes})

@faculty_bp.route('/api/assignments/<int:class_faculty_id>', methods=['GET'])
def api_faculty_assignments(class_faculty_id):
    """Get all assignments for a specific class-faculty pair"""
    if not _require_faculty_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    assignments = get_class_faculty_assignments(class_faculty_id, institution_id)
    return jsonify({'assignments': assignments})


@faculty_bp.route('/api/subjects', methods=['GET'])
def api_faculty_subjects():
    """Return all subjects for faculty resource center"""
    if not _require_faculty_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    subjects = get_all_subjects(institution_id)
    return jsonify({'subjects': subjects})


@faculty_bp.route('/api/subjects/<int:subject_id>/resources', methods=['GET'])
def api_faculty_subject_resources(subject_id):
    if not _require_faculty_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    resources = get_subject_resources(subject_id, institution_id)
    subject = get_subject_by_id(subject_id, institution_id)
    if not subject:
        return jsonify({'error': 'Subject not found'}), 404

    resources_payload = []
    for resource in resources:
        safe_resource = {k: v for k, v in resource.items() if k != 'file_path'}
        safe_resource.update(_build_resource_preview_payload(resource))
        resources_payload.append(safe_resource)

    return jsonify({'resources': resources_payload, 'subject': subject})


@faculty_bp.route('/api/subjects/<int:subject_id>/chapters', methods=['GET'])
def api_faculty_subject_chapters(subject_id):
    if not _require_faculty_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    subject = get_subject_by_id(subject_id, institution_id)
    if not subject:
        return jsonify({'error': 'Subject not found'}), 404

    chapters = get_subject_chapters(subject_id, institution_id)
    return jsonify({'subject': subject, 'chapters': chapters})


@faculty_bp.route('/api/subjects/<int:subject_id>/chapters', methods=['POST'])
def api_faculty_create_chapter(subject_id):
    if not _require_faculty_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    subject = get_subject_by_id(subject_id, institution_id)
    if not subject:
        return jsonify({'error': 'Subject not found'}), 404

    payload = request.get_json(silent=True) or {}
    name = (payload.get('name') or '').strip()
    if not name:
        return jsonify({'status': 'error', 'message': 'Chapter name is required'}), 400

    number = payload.get('number')
    chapter_number = None
    if number not in (None, ''):
        try:
            chapter_number = int(number)
        except (TypeError, ValueError):
            return jsonify({'status': 'error', 'message': 'Chapter number must be an integer'}), 400

    description = (payload.get('description') or '').strip()
    try:
        chapter_id = create_subject_chapter(
            subject_id,
            name,
            chapter_number,
            institution_id,
            session.get('user_id'),
            description
        )
    except Exception as exc:  # pragma: no cover - defensive handling
        return jsonify({'status': 'error', 'message': str(exc)}), 400

    return jsonify({'status': 'success', 'chapter_id': chapter_id})


@faculty_bp.route('/api/chapters/<int:chapter_id>', methods=['DELETE'])
def api_faculty_delete_chapter(chapter_id):
    if not _require_faculty_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    chapter = get_subject_chapter(chapter_id, institution_id)
    if not chapter:
        return jsonify({'status': 'error', 'message': 'Chapter not found'}), 404

    deleted = delete_subject_chapter(chapter_id, institution_id)
    if not deleted:
        return jsonify({'status': 'error', 'message': 'Unable to delete chapter'}), 400

    return jsonify({'status': 'success', 'message': 'Chapter deleted'})


@faculty_bp.route('/api/chapters/<int:chapter_id>/resources', methods=['GET'])
def api_faculty_chapter_resources(chapter_id):
    if not _require_faculty_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    chapter, resources = get_chapter_resources(chapter_id, institution_id)
    if not chapter:
        return jsonify({'error': 'Chapter not found'}), 404

    resources_payload = []
    for resource in resources:
        safe_resource = {k: v for k, v in resource.items() if k != 'file_path'}
        safe_resource.update(_build_resource_preview_payload(resource))
        resources_payload.append(safe_resource)

    return jsonify({'chapter': chapter, 'resources': resources_payload})


@faculty_bp.route('/api/subjects/<int:subject_id>/upload-resource', methods=['POST'])
def api_faculty_upload_resource(subject_id):
    if not _require_faculty_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    subject = get_subject_by_id(subject_id, institution_id)
    if not subject:
        return jsonify({'error': 'Subject not found'}), 404

    chapter_id_value = request.form.get('chapter_id')
    chapter_id = None
    if chapter_id_value not in (None, ''):
        try:
            chapter_id = int(chapter_id_value)
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Invalid chapter reference'}), 400
        chapter = get_subject_chapter(chapter_id, institution_id)
        if not chapter or chapter['subject_id'] != subject_id:
            return jsonify({'status': 'error', 'message': 'Chapter not found for this subject'}), 400

    files = request.files.getlist('files')
    if not files:
        single_file = request.files.get('file')
        if single_file:
            files = [single_file]

    valid_files = [file for file in files if file and file.filename]
    if not valid_files:
        return jsonify({'status': 'error', 'message': 'At least one file is required'}), 400

    title_input = (request.form.get('title') or '').strip()
    description = request.form.get('description', '')
    relative_paths = request.form.getlist('relative_paths')
    storage_root = get_subject_storage_path(institution_id, subject['subject_id'])

    saved_resources = 0
    errors = []
    timestamp = int(datetime.utcnow().timestamp())

    for index, file in enumerate(valid_files):
        original_name = os.path.basename(file.filename)
        safe_base_name = secure_filename(original_name) or f'resource_{index}'
        relative_label = relative_paths[index] if index < len(relative_paths) else original_name
        clean_relative = _sanitize_relative_path(relative_label)
        target_subdir = clean_relative.rsplit('/', 1)[0] if '/' in clean_relative else ''
        target_dir = os.path.join(storage_root, *target_subdir.split('/')) if target_subdir else storage_root
        os.makedirs(target_dir, exist_ok=True)

        unique_name = f"{timestamp}_{index}_{safe_base_name}"
        file_path = os.path.join(target_dir, unique_name)

        try:
            file.save(file_path)
        except OSError as exc:
            errors.append(f"Failed to save {original_name}: {exc}")
            continue

        resource_title = title_input if (title_input and len(valid_files) == 1) else (
            f"{title_input} - {clean_relative or original_name}" if title_input else (clean_relative or original_name)
        )

        add_subject_resource(
            subject_id,
            resource_title,
            description,
            original_name,
            file_path,
            session.get('user_id'),
            institution_id,
            chapter_id=chapter_id
        )
        saved_resources += 1

    if saved_resources == 0:
        return jsonify({'status': 'error', 'message': 'Failed to upload files', 'errors': errors}), 400

    return jsonify({'status': 'success', 'message': f'Uploaded {saved_resources} file(s)', 'errors': errors})


@faculty_bp.route('/api/resources/<int:resource_id>/stream', methods=['GET'])
def api_faculty_stream_resource(resource_id):
    if not _require_faculty_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    resource = get_subject_resource(resource_id, institution_id)
    if not resource or not os.path.isfile(resource['file_path']):
        return jsonify({'error': 'Resource not found'}), 404

    mimetype = _resource_mimetype(resource.get('file_name'))
    return send_file(
        resource['file_path'],
        mimetype=mimetype,
        as_attachment=False,
        download_name=resource.get('file_name')
    )


@faculty_bp.route('/api/resources/<int:resource_id>/text-preview', methods=['GET'])
def api_faculty_text_preview_resource(resource_id):
    if not _require_faculty_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    resource = get_subject_resource(resource_id, institution_id)
    if not resource or not os.path.isfile(resource['file_path']):
        return jsonify({'error': 'Resource not found'}), 404

    if _detect_preview_type(resource.get('file_name')) != 'text':
        return jsonify({'error': 'Preview not available for this resource'}), 400

    try:
        with open(resource['file_path'], 'rb') as file_handle:
            data = file_handle.read(MAX_TEXT_PREVIEW_BYTES + 1)
    except OSError:
        return jsonify({'error': 'Unable to open file for preview'}), 500

    truncated = len(data) > MAX_TEXT_PREVIEW_BYTES
    preview_bytes = data[:MAX_TEXT_PREVIEW_BYTES]
    content = preview_bytes.decode('utf-8', errors='replace')
    return jsonify({
        'status': 'success',
        'content': content,
        'truncated': truncated,
        'file_name': resource.get('file_name')
    })


@faculty_bp.route('/api/resources/<int:resource_id>/download', methods=['GET'])
def api_faculty_download_resource(resource_id):
    if not _require_faculty_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    resource = get_subject_resource(resource_id, institution_id)
    if not resource or not os.path.isfile(resource['file_path']):
        return jsonify({'error': 'Resource not found'}), 404

    return send_file(resource['file_path'], as_attachment=True, download_name=resource['file_name'])


@faculty_bp.route('/api/resources/<int:resource_id>', methods=['DELETE'])
def api_faculty_delete_resource(resource_id):
    if not _require_faculty_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    resource = get_subject_resource(resource_id, institution_id)
    if not resource:
        return jsonify({'status': 'error', 'message': 'Resource not found'}), 404

    deleted = delete_subject_resource(resource_id, institution_id)
    if not deleted:
        return jsonify({'status': 'error', 'message': 'Unable to delete resource'}), 400

    return jsonify({'status': 'success', 'message': 'Resource deleted'})

@faculty_bp.route('/api/create-assignment', methods=['POST'])
def api_create_assignment():
    """Create a new assignment"""
    if not _require_faculty_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    class_faculty_id = data.get('class_faculty_id')
    title = data.get('title')
    description = data.get('description')
    due_date = data.get('due_date')
    institution_id = session.get('institution_id')
    
    if not all([class_faculty_id, title, due_date]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        assignment_id = create_assignment(class_faculty_id, title, description, due_date, institution_id)
        return jsonify({'status': 'success', 'assignment_id': assignment_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@faculty_bp.route('/api/assignment/<int:assignment_id>', methods=['GET'])
def api_assignment_detail(assignment_id):
    """Get assignment details and student submissions"""
    if not _require_faculty_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    with get_db_connection(institution_id) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM assignments WHERE id = ?', (assignment_id,))
        assignment = cursor.fetchone()
        
        if not assignment:
            return jsonify({'error': 'Assignment not found'}), 404
        
        assignment = dict(assignment)
    
    students = get_assignment_students(assignment_id, institution_id)
    return jsonify({'assignment': assignment, 'students': students})

@faculty_bp.route('/api/verify-submission', methods=['POST'])
def api_verify_submission():
    """Verify a student's submission"""
    if not _require_faculty_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    assignment_id = data.get('assignment_id')
    student_id = data.get('student_id')
    institution_id = session.get('institution_id')
    
    try:
        update_student_assignment_status(student_id, assignment_id, verification_status='verified', institution_id=institution_id)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

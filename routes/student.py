"""Student dashboard and classroom routes"""
import os
from flask import Blueprint, render_template, jsonify, session, redirect, url_for, send_file
from routes.database import (get_student_info, get_student_subjects, get_student_class_assignments, 
                     get_subject_assignments, get_subject_chapters, get_chapter_resources,
                     is_subject_accessible_to_student, get_subject_by_id, get_subject_chapter,
                     get_subject_resource)

student_bp = Blueprint('student', __name__, url_prefix='/student')

def _require_student_role():
    """Check if user is a student"""
    if 'role' not in session or session['role'] != 'student':
        return False
    return True


@student_bp.route('/dashboard')
def student_dashboard():
    """Student dashboard"""
    if not _require_student_role():
        return redirect(url_for('home.login'))
    
    student_id = session.get('user_id')
    institution_id = session.get('institution_id')
    student = get_student_info(student_id, institution_id)
    
    return render_template('student/dashboard.html', student=student)

@student_bp.route('/classroom')
def student_classroom():
    """Student classroom management"""
    if not _require_student_role():
        return redirect(url_for('home.login'))
    
    return render_template('student/classroom.html')

@student_bp.route('/timetable')
def student_timetable():
    """Student timetable"""
    if not _require_student_role():
        return redirect(url_for('home.login'))
    
    return render_template('student/timetable.html')

@student_bp.route('/knowledge')
def student_knowledge():
    """Student knowledge/resources section"""
    if not _require_student_role():
        return redirect(url_for('home.login'))
    
    return render_template('student/knowledge.html')

# API Endpoints
@student_bp.route('/api/subjects', methods=['GET'])
def api_student_subjects():
    """Get all subjects for the logged-in student"""
    if not _require_student_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    student_id = session.get('user_id')
    institution_id = session.get('institution_id')
    subjects = get_student_subjects(student_id, institution_id)
    return jsonify({'subjects': subjects})

@student_bp.route('/api/assignments', methods=['GET'])
def api_student_assignments():
    """Get all assignments for the student's class"""
    if not _require_student_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    student_id = session.get('user_id')
    institution_id = session.get('institution_id')
    assignments = get_student_class_assignments(student_id, institution_id)
    return jsonify({'assignments': assignments})

@student_bp.route('/api/subject/<int:class_faculty_id>/assignments', methods=['GET'])
def api_student_subject_assignments(class_faculty_id):
    """Get all assignments for a specific subject"""
    if not _require_student_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    assignments = get_subject_assignments(class_faculty_id, institution_id)
    return jsonify({'assignments': assignments})


@student_bp.route('/api/subjects/<int:subject_id>/chapters', methods=['GET'])
def api_student_subject_chapters(subject_id):
    if not _require_student_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    student_id = session.get('user_id')
    if not is_subject_accessible_to_student(student_id, subject_id, institution_id):
        return jsonify({'error': 'Subject not available'}), 404

    subject = get_subject_by_id(subject_id, institution_id)
    if not subject:
        return jsonify({'error': 'Subject not found'}), 404

    chapters = get_subject_chapters(subject_id, institution_id)
    return jsonify({'subject': subject, 'chapters': chapters})


@student_bp.route('/api/chapters/<int:chapter_id>/resources', methods=['GET'])
def api_student_chapter_resources(chapter_id):
    if not _require_student_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    student_id = session.get('user_id')
    chapter = get_subject_chapter(chapter_id, institution_id)
    if not chapter or not is_subject_accessible_to_student(student_id, chapter['subject_id'], institution_id):
        return jsonify({'error': 'Chapter not available'}), 404

    _, resources = get_chapter_resources(chapter_id, institution_id)
    sanitized = []
    for resource in resources:
        safe_resource = {k: v for k, v in resource.items() if k != 'file_path'}
        safe_resource['download_url'] = url_for('student.api_student_download_resource', resource_id=resource['id'])
        sanitized.append(safe_resource)

    return jsonify({'chapter': chapter, 'resources': sanitized})


@student_bp.route('/api/resources/<int:resource_id>/download', methods=['GET'])
def api_student_download_resource(resource_id):
    if not _require_student_role():
        return jsonify({'error': 'Unauthorized'}), 401

    institution_id = session.get('institution_id')
    student_id = session.get('user_id')
    resource = get_subject_resource(resource_id, institution_id)
    if not resource or not is_subject_accessible_to_student(student_id, resource['subject_id'], institution_id):
        return jsonify({'error': 'Resource not found'}), 404

    file_path = resource.get('file_path')
    if not file_path or not os.path.isfile(file_path):
        return jsonify({'error': 'Resource file missing'}), 404

    return send_file(file_path, as_attachment=True, download_name=resource.get('file_name'))

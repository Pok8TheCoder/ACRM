"""Principal/Master Admin dashboard and management routes"""
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from routes.database import (get_admin_stats, get_admin_by_id, get_all_admins, create_admin, 
                     update_admin_permissions, reset_admin_password, delete_admin)

principal_bp = Blueprint('principal', __name__, url_prefix='/principal')
principal_api_bp = Blueprint('principal_api', __name__, url_prefix='/api/principal')

def _require_principal_role():
    """Check if user is principal/master admin"""
    if 'role' not in session or session['role'] != 'master_admin':
        return False
    return True

@principal_bp.route('/dashboard')
def principal_dashboard():
    """Principal/Master Admin dashboard"""
    if not _require_principal_role():
        return redirect(url_for('home.login'))
    
    principal_name = session.get('user_name')
    return render_template('principal/dashboard.html', principal_name=principal_name)

# Admin Management API Endpoints
@principal_api_bp.route('/admin-stats', methods=['GET'])
def api_principal_admin_stats():
    """Get admin statistics"""
    if not _require_principal_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    stats = get_admin_stats(institution_id)
    return jsonify(stats)

@principal_api_bp.route('/admins', methods=['GET'])
def api_principal_get_admins():
    """Get all admins"""
    if not _require_principal_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    admins = get_all_admins(institution_id)
    return jsonify({'admins': admins})

@principal_api_bp.route('/admin/<admin_id>', methods=['GET'])
def api_principal_get_admin(admin_id):
    """Get specific admin details"""
    if not _require_principal_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    admin = get_admin_by_id(admin_id, institution_id)
    
    if not admin:
        return jsonify({'error': 'Admin not found'}), 404
    
    return jsonify(admin)

@principal_api_bp.route('/create-admin', methods=['POST'])
def api_principal_create_admin():
    """Create new admin account"""
    if not _require_principal_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    institution_id = session.get('institution_id')
    
    admin_id = data.get('admin_id')
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    role_type = data.get('role_type', 'admin')
    can_create_students = data.get('can_create_students', False)
    can_create_faculty = data.get('can_create_faculty', False)
    can_create_admins = data.get('can_create_admins', False)
    
    if not all([admin_id, name, email, password]):
        return jsonify({'error': 'Missing required fields', 'status': 'error'}), 400
    
    result = create_admin(admin_id, name, email, password, role_type, institution_id, 
                         can_create_students, can_create_faculty, can_create_admins)
    
    if result.get('status') == 'success':
        return jsonify(result), 201
    else:
        return jsonify(result), 400

@principal_api_bp.route('/admin/<admin_id>/reset-password', methods=['POST'])
def api_principal_reset_password(admin_id):
    """Reset admin password"""
    if not _require_principal_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    institution_id = session.get('institution_id')
    new_password = data.get('password')
    
    if not new_password:
        return jsonify({'error': 'New password required', 'status': 'error'}), 400
    
    result = reset_admin_password(admin_id, new_password, institution_id)
    
    if result.get('status') == 'success':
        return jsonify(result), 200
    else:
        return jsonify(result), 400

@principal_api_bp.route('/admin/<admin_id>/permissions', methods=['PUT'])
def api_principal_update_permissions(admin_id):
    """Update admin permissions"""
    if not _require_principal_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    institution_id = session.get('institution_id')
    
    can_create_students = data.get('can_create_students')
    can_create_faculty = data.get('can_create_faculty')
    can_create_admins = data.get('can_create_admins')
    
    result = update_admin_permissions(admin_id, institution_id, can_create_students, 
                                     can_create_faculty, can_create_admins)
    return jsonify(result)

@principal_api_bp.route('/admin/<admin_id>/delete', methods=['POST'])
def api_principal_delete_admin(admin_id):
    """Delete an admin account"""
    if not _require_principal_role():
        return jsonify({'error': 'Unauthorized'}), 401
    
    institution_id = session.get('institution_id')
    result = delete_admin(admin_id, institution_id)
    
    if result.get('status') == 'success':
        return jsonify(result), 200
    else:
        return jsonify(result), 400

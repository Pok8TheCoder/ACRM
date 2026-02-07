"""Home page, login, and general public routes"""
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from routes.database import (get_all_institutions, get_institution, verify_student, verify_faculty, 
                     verify_admin, verify_principal)

home_bp = Blueprint('home', __name__)

@home_bp.route('/')
def home():
    """Home page"""
    return render_template('home.html')

@home_bp.route('/features')
def features():
    """Features page"""
    return render_template('features.html')

@home_bp.route('/contact')
def contact():
    """Contact page"""
    return render_template('contact.html')

@home_bp.route('/logout', methods=['POST'])
def logout():
    """Logout user"""
    session.clear()
    return redirect(url_for('home.home'))

# Login Routes
@home_bp.route('/login')
def login():
    """Institution selection page"""
    institutions = get_all_institutions()
    return render_template('login.html', institutions=institutions)

@home_bp.route('/principal-login')
def principal_login():
    """Principal login page"""
    institutions = get_all_institutions()
    return render_template('principal_login.html', institutions=institutions)

@home_bp.route('/login-institution/<institution_id>')
def login_institution(institution_id):
    """Role selection page"""
    institution = get_institution(institution_id)
    
    if not institution:
        return redirect(url_for('home.login'))
    
    return render_template('login_role.html', institution=institution)

@home_bp.route('/login-form', methods=['GET', 'POST'])
def login_form():
    """Login form page"""
    if request.method == 'POST':
        data = request.get_json()
        institution_id = data.get('institution_id')
        role = data.get('role')
        user_id = data.get('user_id')
        password = data.get('password')
        
        user = None
        
        # Verify credentials based on role
        if role == 'student':
            user = verify_student(user_id, password, institution_id)
        elif role == 'faculty':
            user = verify_faculty(user_id, password, institution_id)
        elif role == 'admin':
            user = verify_admin(user_id, password, institution_id)
        elif role == 'master_admin':
            user = verify_principal(user_id, password, institution_id)
        
        if user:
            session.permanent = True
            session['user_id'] = user_id
            session['role'] = role
            session['institution_id'] = institution_id
            
            # Handle both old schema (name field) and new schema (first_name/last_name)
            if 'name' in user and user['name']:
                session['user_name'] = user['name']
            elif 'first_name' in user and 'last_name' in user:
                first_name = str(user.get('first_name', '')).strip() if user.get('first_name') else ''
                last_name = str(user.get('last_name', '')).strip() if user.get('last_name') else ''
                if first_name or last_name:
                    session['user_name'] = f"{first_name} {last_name}".strip()
                else:
                    session['user_name'] = user_id
            else:
                session['user_name'] = user_id
            
            # Store additional info based on role
            if role == 'student':
                session['class_id'] = user['class_id']
                session['program_id'] = user['program_id']
            
            # Route to role-specific dashboard
            if role == 'student':
                return jsonify({'status': 'success', 'redirect': '/student/dashboard'})
            elif role == 'faculty':
                return jsonify({'status': 'success', 'redirect': '/faculty/dashboard'})
            elif role == 'master_admin':
                return jsonify({'status': 'success', 'redirect': '/principal/dashboard'})
            else:  # admin
                return jsonify({'status': 'success', 'redirect': '/admin/dashboard'})
        
        return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 401
    
    # GET request - show login form
    institution_id = request.args.get('institution_id')
    role = request.args.get('role')
    
    institution = get_institution(institution_id)
    
    if not institution:
        return redirect(url_for('home.login'))
    
    return render_template('login_form.html', institution=institution, role=role)

@home_bp.route('/principal-login-form', methods=['GET', 'POST'])
def principal_login_form():
    """Principal login form"""
    if request.method == 'POST':
        data = request.get_json()
        institution_id = data.get('institution_id')
        principal_id = data.get('principal_id')
        password = data.get('password')
        
        principal = verify_principal(principal_id, password, institution_id)
        
        if principal:
            session.permanent = True
            session['user_id'] = principal_id
            session['role'] = 'principal'
            session['institution_id'] = institution_id
            session['user_name'] = principal['name']
            
            return jsonify({'status': 'success', 'redirect': '/principal/dashboard'})
        
        return jsonify({'status': 'error', 'message': 'Invalid principal credentials'}), 401
    
    # GET request - show login form
    institution_id = request.args.get('institution_id')
    institution = get_institution(institution_id)
    
    if not institution:
        return redirect(url_for('home.principal_login'))
    
    return render_template('principal_login_form.html', institution=institution)

@home_bp.route('/api/contact-message', methods=['POST'])
def contact_message():
    """Handle contact form submission"""
    data = request.get_json()
    print('Contact Message:', data)
    return jsonify({'status': 'success', 'message': 'Message sent successfully!'})

@home_bp.route('/dashboard')
def dashboard():
    """Role-aware dashboard routing"""
    if 'role' not in session:
        return redirect(url_for('home.login'))
    
    role = session.get('role')
    
    if role == 'student':
        return redirect(url_for('student.student_dashboard'))
    elif role == 'faculty':
        return redirect(url_for('faculty.faculty_dashboard'))
    elif role in ['admin', 'master_admin']:
        if role == 'master_admin':
            return redirect(url_for('principal.principal_dashboard'))
        return redirect(url_for('admin.admin_dashboard'))
    
    return redirect(url_for('home.login'))

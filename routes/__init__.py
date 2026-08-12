"""Routes package - Blueprint registration"""
from routes.home import home_bp
from routes.student import student_bp
from routes.faculty import faculty_bp
from routes.admin import admin_bp
from routes.principal import principal_bp, principal_api_bp

def register_blueprints(app):
    """Register all blueprints with the Flask app"""
    app.register_blueprint(home_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(faculty_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(principal_bp)
    app.register_blueprint(principal_api_bp)

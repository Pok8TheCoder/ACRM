from flask import Flask
from datetime import timedelta
from routes.database import init_db
from routes import register_blueprints

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.secret_key = 'acrm_secret_key_2024'
app.permanent_session_lifetime = timedelta(hours=24)

# Initialize database
init_db()

# Register all route blueprints
register_blueprints(app)

if __name__ == '__main__':
    app.run(debug=True)

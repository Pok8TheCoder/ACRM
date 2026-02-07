import sqlite3
import os
import shutil
import base64
import json
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime

# Base directory for institution databases
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
INSTITUTIONS_DIR = os.path.join(BASE_DIR, 'institutions')

# Global capacity constraints
MAX_CLASS_SIZE = 60
MAX_LAB_BATCH_SIZE = 30

def get_institution_db_path(institution_id, role=None):
    """Get the database path for a specific institution and role
    
    Args:
        institution_id: The institution ID (e.g., 'iit_delhi')
        role: The role type ('student', 'faculty', 'admin', or None for Master_Admin)
    
    Returns:
        Path to the database file
    """
    if role is None or role == 'master':
        # Master_Admin database at institution root level
        institution_folder = os.path.join(INSTITUTIONS_DIR, institution_id)
        os.makedirs(institution_folder, exist_ok=True)
        return os.path.join(institution_folder, 'Master_Admin.db')
    else:
        # Role-specific databases
        role_folder = os.path.join(INSTITUTIONS_DIR, institution_id, role)
        os.makedirs(role_folder, exist_ok=True)
        return os.path.join(role_folder, f'{role}.db')

def get_data_upload_path(institution_id, role, user_id=None):
    """Get the data upload path for a specific institution, role, and user
    
    Args:
        institution_id: The institution ID (e.g., 'iit_delhi')
        role: The role type ('student', 'faculty', 'admin')
        user_id: The user ID (optional, creates user-specific folder)
    
    Returns:
        Path to the data folder
    """
    data_path = os.path.join(INSTITUTIONS_DIR, institution_id, role, 'data')
    if user_id:
        data_path = os.path.join(data_path, user_id)
    os.makedirs(data_path, exist_ok=True)
    return data_path


def get_subject_storage_path(institution_id, subject_code):
    """Get storage directory for a subject's resources"""
    subject_dir = os.path.join(INSTITUTIONS_DIR, institution_id, 'Subjects', subject_code)
    os.makedirs(subject_dir, exist_ok=True)
    return subject_dir

def _current_context():
    """Get current institution and role from thread-local storage"""
    import threading
    thread = threading.current_thread()
    return {
        'institution_id': getattr(thread, '_institution_id', 'iit_delhi'),
        'role': getattr(thread, '_role', None)
    }

@contextmanager
def get_db_connection(institution_id=None, role=None):
    """Context manager for database connections
    
    Args:
        institution_id: The institution ID. If not provided, uses the current context.
        role: The role type ('student', 'faculty', 'admin', or None for Master_Admin).
              If not provided, uses the current context.
    """
    if institution_id is None or role is None:
        context = _current_context()
        institution_id = institution_id or context['institution_id']
        role = role or context['role']
    
    db_path = get_institution_db_path(institution_id, role)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_db(institution_id='iit_delhi', load_samples=True):
    """Initialize databases for all roles and Master_Admin for a specific institution"""
    
    # Initialize Master_Admin database
    _init_master_admin_db(institution_id)
    
    # Initialize role-specific databases
    _init_student_db(institution_id, load_samples=load_samples)
    _init_faculty_db(institution_id)
    _init_admin_db(institution_id)
    
    # Run migrations
    _migrate_databases(institution_id)


def reset_institution_data(institution_id='iit_delhi'):
    """Completely wipe an institution's storage and reinitialize fresh databases"""
    institution_path = os.path.join(INSTITUTIONS_DIR, institution_id)
    try:
        if os.path.exists(institution_path):
            shutil.rmtree(institution_path)
        init_db(institution_id, load_samples=False)
        return {'status': 'success', 'message': 'Institution data reset'}
    except Exception as exc:
        return {'status': 'error', 'message': str(exc)}

def _migrate_databases(institution_id='iit_delhi'):
    """Run database migrations to add new columns to existing tables"""
    # Ensure faculty metadata columns exist (extra notes, teaching metadata)
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA table_info(faculty)")
            columns = [col[1] for col in cursor.fetchall()]
            column_migrations = [
                ('extra_notes', 'ALTER TABLE faculty ADD COLUMN extra_notes TEXT'),
                ('time_preference', 'ALTER TABLE faculty ADD COLUMN time_preference TEXT'),
                ('is_teaching_staff', 'ALTER TABLE faculty ADD COLUMN is_teaching_staff INTEGER DEFAULT 0'),
                ('majors', 'ALTER TABLE faculty ADD COLUMN majors TEXT'),
                ('proficiency_score', 'ALTER TABLE faculty ADD COLUMN proficiency_score INTEGER'),
                ('experience_years', 'ALTER TABLE faculty ADD COLUMN experience_years INTEGER'),
                ('value_score', 'ALTER TABLE faculty ADD COLUMN value_score INTEGER')
            ]
            for column_name, alter_sql in column_migrations:
                if column_name not in columns:
                    cursor.execute(alter_sql)
                    columns.append(column_name)
            conn.commit()
        except Exception:
            pass  # Column might already exist
    
    # Add subject column to faculty_classes table if it doesn't exist
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA table_info(faculty_classes)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'subject' not in columns:
                cursor.execute('ALTER TABLE faculty_classes ADD COLUMN subject TEXT')
                conn.commit()
            if 'subject_ref_id' not in columns:
                cursor.execute('ALTER TABLE faculty_classes ADD COLUMN subject_ref_id INTEGER')
                conn.commit()
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='faculty_classes'")
            table_row = cursor.fetchone()
            table_sql = table_row['sql'] if table_row else ''
            if table_sql and 'UNIQUE(faculty_id, class_id)' in table_sql:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS faculty_classes__new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        faculty_id INTEGER NOT NULL,
                        class_id INTEGER NOT NULL,
                        subject TEXT,
                        subject_ref_id INTEGER,
                        institution_id TEXT NOT NULL,
                        FOREIGN KEY (faculty_id) REFERENCES faculty(id),
                        FOREIGN KEY (class_id) REFERENCES classes(id),
                        UNIQUE(class_id, subject_ref_id, institution_id)
                    )
                ''')
                cursor.execute('''
                    INSERT OR IGNORE INTO faculty_classes__new (faculty_id, class_id, subject, subject_ref_id, institution_id)
                    SELECT faculty_id, class_id, subject, subject_ref_id, institution_id
                    FROM faculty_classes
                ''')
                cursor.execute('DROP TABLE faculty_classes')
                cursor.execute('ALTER TABLE faculty_classes__new RENAME TO faculty_classes')
                conn.commit()
        except Exception as e:
            pass  # Column might already exist

    # Ensure subjects-related tables exist
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                teaching_hours INTEGER DEFAULT 0,
                delivery_mode TEXT NOT NULL CHECK(delivery_mode IN ('theory','practical')) DEFAULT 'theory',
                subject_type TEXT NOT NULL CHECK(subject_type IN ('semester', 'student', 'general')),
                has_theory_component INTEGER DEFAULT 1,
                has_practical_component INTEGER DEFAULT 0,
                theory_hours INTEGER DEFAULT 0,
                practical_hours INTEGER DEFAULT 0,
                requires_lab INTEGER DEFAULT 0,
                semester_id INTEGER,
                institution_id TEXT NOT NULL,
                required_majors TEXT,
                min_proficiency INTEGER,
                min_experience INTEGER,
                min_value INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (semester_id) REFERENCES semesters(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subject_students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                institution_id TEXT NOT NULL,
                UNIQUE(subject_id, student_id),
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subject_resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                chapter_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                uploaded_by TEXT,
                uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                institution_id TEXT NOT NULL,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subject_chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                chapter_name TEXT NOT NULL,
                chapter_number INTEGER,
                description TEXT,
                created_by TEXT,
                institution_id TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(subject_id, chapter_number),
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            )
        ''')

        cursor.execute("PRAGMA table_info(subject_resources)")
        resource_columns = [col[1] for col in cursor.fetchall()]
        if 'chapter_id' not in resource_columns:
            cursor.execute('ALTER TABLE subject_resources ADD COLUMN chapter_id INTEGER')
            conn.commit()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS faculty_subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faculty_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                institution_id TEXT NOT NULL,
                UNIQUE(faculty_id, subject_id, institution_id),
                FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subject_semesters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                semester_id INTEGER NOT NULL,
                institution_id TEXT NOT NULL,
                UNIQUE(subject_id, semester_id, institution_id),
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (semester_id) REFERENCES semesters(id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS class_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                batch_code TEXT NOT NULL,
                sequence_index INTEGER NOT NULL,
                start_position INTEGER NOT NULL,
                end_position INTEGER NOT NULL,
                student_count INTEGER NOT NULL,
                first_roll_label TEXT,
                last_roll_label TEXT,
                institution_id TEXT NOT NULL,
                UNIQUE(class_id, batch_code, institution_id),
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS infinity_pane_state (
                institution_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_by TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS infinity_pane_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                institution_id TEXT NOT NULL,
                actor_id TEXT,
                actor_name TEXT,
                action TEXT NOT NULL,
                summary TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Campus infrastructure (floors/sections/rooms)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS campus_floors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                institution_id TEXT NOT NULL,
                floor_number INTEGER NOT NULL,
                label TEXT,
                UNIQUE(institution_id, floor_number)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS campus_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                institution_id TEXT NOT NULL,
                floor_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (floor_id) REFERENCES campus_floors(id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS campus_rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                institution_id TEXT NOT NULL,
                floor_id INTEGER NOT NULL,
                section_id INTEGER,
                room_number TEXT NOT NULL,
                room_type TEXT NOT NULL CHECK(room_type IN ('classroom','lab','custom')),
                capacity INTEGER DEFAULT 0,
                assigned_subject_id INTEGER,
                custom_title TEXT,
                custom_function TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(institution_id, room_number),
                FOREIGN KEY (floor_id) REFERENCES campus_floors(id) ON DELETE CASCADE,
                FOREIGN KEY (section_id) REFERENCES campus_sections(id) ON DELETE SET NULL,
                FOREIGN KEY (assigned_subject_id) REFERENCES subjects(id) ON DELETE SET NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS timetable_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                institution_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                targeting_mode TEXT NOT NULL CHECK(targeting_mode IN ('strict','moderate','loose')) DEFAULT 'strict',
                margin_proficiency INTEGER DEFAULT 0,
                margin_experience INTEGER DEFAULT 0,
                focus_mode TEXT NOT NULL CHECK(focus_mode IN ('balanced','focus')) DEFAULT 'balanced',
                focus_branches TEXT,
                focus_semesters TEXT,
                focus_classes TEXT,
                slots_per_day INTEGER NOT NULL DEFAULT 6,
                slot_duration_minutes INTEGER NOT NULL DEFAULT 60,
                days_per_week INTEGER NOT NULL DEFAULT 5,
                term_weeks INTEGER NOT NULL DEFAULT 20,
                first_slot_start TEXT,
                breaks_json TEXT,
                lab_multi_slot INTEGER NOT NULL DEFAULT 1,
                config_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute("PRAGMA table_info(timetable_runs)")
        timetable_run_columns = [col[1] for col in cursor.fetchall()]
        if 'term_weeks' not in timetable_run_columns:
            cursor.execute('ALTER TABLE timetable_runs ADD COLUMN term_weeks INTEGER NOT NULL DEFAULT 20')
            conn.commit()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS timetable_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                institution_id TEXT NOT NULL,
                class_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                faculty_id INTEGER NOT NULL,
                room_id INTEGER,
                day_index INTEGER NOT NULL,
                slot_index INTEGER NOT NULL,
                slot_span INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (run_id) REFERENCES timetable_runs(id) ON DELETE CASCADE
            )
        ''')

        cursor.execute("PRAGMA table_info(classes)")
        class_columns = [col[1] for col in cursor.fetchall()]
        if 'home_room_id' not in class_columns:
            cursor.execute('ALTER TABLE classes ADD COLUMN home_room_id INTEGER')
            conn.commit()

        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='subjects'")
        table_sql = cursor.fetchone()
        if table_sql and "'general'" not in table_sql['sql']:
            cursor.execute('ALTER TABLE subjects RENAME TO subjects_old')
            cursor.execute('''
                CREATE TABLE subjects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    teaching_hours INTEGER DEFAULT 0,
                    delivery_mode TEXT NOT NULL CHECK(delivery_mode IN ('theory','practical')) DEFAULT 'theory',
                    subject_type TEXT NOT NULL CHECK(subject_type IN ('semester', 'student', 'general')),
                    semester_id INTEGER,
                    institution_id TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (semester_id) REFERENCES semesters(id)
                )
            ''')
            cursor.execute('''
                INSERT INTO subjects (id, subject_id, name, description, teaching_hours, delivery_mode, subject_type, semester_id, institution_id, created_at)
                SELECT id, subject_id, name, description, 0, 'theory', subject_type, semester_id, institution_id, created_at
                FROM subjects_old
            ''')
            cursor.execute('DROP TABLE subjects_old')
            conn.commit()

        cursor.execute("PRAGMA table_info(subjects)")
        subject_columns = [col[1] for col in cursor.fetchall()]
        if 'teaching_hours' not in subject_columns:
            cursor.execute('ALTER TABLE subjects ADD COLUMN teaching_hours INTEGER DEFAULT 0')
            conn.commit()
        if 'delivery_mode' not in subject_columns:
            cursor.execute("ALTER TABLE subjects ADD COLUMN delivery_mode TEXT DEFAULT 'theory'")
            cursor.execute("UPDATE subjects SET delivery_mode = 'theory' WHERE delivery_mode IS NULL OR delivery_mode = ''")
            conn.commit()
        requirement_alters = [
            ('required_majors', 'ALTER TABLE subjects ADD COLUMN required_majors TEXT'),
            ('min_proficiency', 'ALTER TABLE subjects ADD COLUMN min_proficiency INTEGER'),
            ('min_experience', 'ALTER TABLE subjects ADD COLUMN min_experience INTEGER'),
            ('min_value', 'ALTER TABLE subjects ADD COLUMN min_value INTEGER')
        ]
        for col_name, alter_sql in requirement_alters:
            if col_name not in subject_columns:
                cursor.execute(alter_sql)
        cursor.execute("PRAGMA table_info(subjects)")
        subject_columns = [col[1] for col in cursor.fetchall()]

        component_alters = [
            ('has_theory_component', 'ALTER TABLE subjects ADD COLUMN has_theory_component INTEGER DEFAULT 1'),
            ('has_practical_component', 'ALTER TABLE subjects ADD COLUMN has_practical_component INTEGER DEFAULT 0'),
            ('theory_hours', 'ALTER TABLE subjects ADD COLUMN theory_hours INTEGER DEFAULT 0'),
            ('practical_hours', 'ALTER TABLE subjects ADD COLUMN practical_hours INTEGER DEFAULT 0'),
            ('requires_lab', 'ALTER TABLE subjects ADD COLUMN requires_lab INTEGER DEFAULT 0')
        ]
        added_component_columns = False
        for col_name, alter_sql in component_alters:
            if col_name not in subject_columns:
                cursor.execute(alter_sql)
                added_component_columns = True

        if added_component_columns:
            cursor.execute('''
                UPDATE subjects
                SET has_theory_component = CASE
                    WHEN delivery_mode = 'practical' THEN 0
                    ELSE 1
                END
                WHERE has_theory_component IS NULL
            ''')
            cursor.execute('''
                UPDATE subjects
                SET has_practical_component = CASE
                    WHEN delivery_mode = 'practical' THEN 1
                    ELSE 0
                END
                WHERE has_practical_component IS NULL
            ''')
            cursor.execute('''
                UPDATE subjects
                SET theory_hours = CASE
                    WHEN delivery_mode = 'practical' THEN 0
                    ELSE COALESCE(teaching_hours, 0)
                END
                WHERE theory_hours IS NULL OR theory_hours = 0
            ''')
            cursor.execute('''
                UPDATE subjects
                SET practical_hours = CASE
                    WHEN delivery_mode = 'practical' THEN COALESCE(teaching_hours, 0)
                    ELSE 0
                END
                WHERE practical_hours IS NULL OR practical_hours = 0
            ''')
            cursor.execute('''
                UPDATE subjects
                SET requires_lab = CASE
                    WHEN has_practical_component = 1 THEN 1
                    ELSE 0
                END
                WHERE requires_lab IS NULL
            ''')
        conn.commit()

    # Ensure timetable tables exist for scheduling prototype
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS timetable_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                institution_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                targeting_mode TEXT NOT NULL CHECK(targeting_mode IN ('strict','moderate','loose')) DEFAULT 'strict',
                margin_proficiency INTEGER DEFAULT 0,
                margin_experience INTEGER DEFAULT 0,
                focus_mode TEXT NOT NULL CHECK(focus_mode IN ('balanced','focus')) DEFAULT 'balanced',
                focus_branches TEXT,
                focus_semesters TEXT,
                focus_classes TEXT,
                slots_per_day INTEGER NOT NULL DEFAULT 6,
                slot_duration_minutes INTEGER NOT NULL DEFAULT 60,
                days_per_week INTEGER NOT NULL DEFAULT 5,
                term_weeks INTEGER NOT NULL DEFAULT 20,
                first_slot_start TEXT,
                breaks_json TEXT,
                lab_multi_slot INTEGER NOT NULL DEFAULT 1,
                config_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute("PRAGMA table_info(timetable_runs)")
        timetable_run_columns = [col[1] for col in cursor.fetchall()]
        if 'term_weeks' not in timetable_run_columns:
            cursor.execute('ALTER TABLE timetable_runs ADD COLUMN term_weeks INTEGER NOT NULL DEFAULT 20')
            conn.commit()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS timetable_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                institution_id TEXT NOT NULL,
                class_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                faculty_id INTEGER NOT NULL,
                room_id INTEGER,
                day_index INTEGER NOT NULL,
                slot_index INTEGER NOT NULL,
                slot_span INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (run_id) REFERENCES timetable_runs(id) ON DELETE CASCADE
            )
        ''')
        conn.commit()

def _init_master_admin_db(institution_id):
    """Initialize Master_Admin database - manages admin access control"""
    with get_db_connection(institution_id, 'master') as conn:
        cursor = conn.cursor()
        
        # Create institutions table (master list)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS institutions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                city TEXT,
                country TEXT,
                founded INTEGER,
                students INTEGER,
                faculty INTEGER
            )
        ''')
        
        # Create admin roles table (defines which admins can do what)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                password TEXT NOT NULL,
                role_type TEXT NOT NULL,
                institution_id TEXT NOT NULL,
                can_create_admins BOOLEAN DEFAULT 0,
                can_create_students BOOLEAN DEFAULT 0,
                can_create_faculty BOOLEAN DEFAULT 0,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (institution_id) REFERENCES institutions(id)
            )
        ''')
        
        # Insert institution if not exists
        cursor.execute('SELECT COUNT(*) FROM institutions')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO institutions (id, name, city, country, founded, students, faculty)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (institution_id, 'IIT Delhi Engineering Campus', 'Delhi', 'India', 1961, 3500, 320))
        
        # Insert principal (super admin) if not exists
        cursor.execute('SELECT COUNT(*) FROM admin_roles WHERE role_type = ?', ('principal',))
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO admin_roles (admin_id, name, email, password, role_type, institution_id, 
                                        can_create_admins, can_create_students, can_create_faculty)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', ('PRI001', 'Dr. Meera Sharma', 'meera@iitdelhi.ac.in', 'principal123', 'principal', 
                  institution_id, 1, 1, 1))
        
        conn.commit()

def _init_student_db(institution_id, load_samples=True):
    """Initialize Student database"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        
        # Drop old tables if they exist (for migration)
        cursor.execute('DROP TABLE IF EXISTS students')
        cursor.execute('DROP TABLE IF EXISTS classes')
        cursor.execute('DROP TABLE IF EXISTS semesters')
        cursor.execute('DROP TABLE IF EXISTS programs')
        cursor.execute('DROP TABLE IF EXISTS faculty_classes')
        cursor.execute('DROP TABLE IF EXISTS faculty')
        
        # Create programs/branches table (CSE, ECE, ME, CE, etc.)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS programs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_id TEXT UNIQUE NOT NULL,
                program_name TEXT NOT NULL,
                code TEXT NOT NULL,
                institution_id TEXT NOT NULL
            )
        ''')
        
        # Create semesters table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS semesters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                semester_id TEXT NOT NULL,
                semester_number INTEGER NOT NULL,
                program_id INTEGER NOT NULL,
                institution_id TEXT NOT NULL,
                FOREIGN KEY (program_id) REFERENCES programs(id),
                UNIQUE(semester_id, program_id)
            )
        ''')
        
        # Create classes/sections table (CSE-A, ECE-B, etc.)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id TEXT UNIQUE NOT NULL,
                class_name TEXT NOT NULL,
                program_id INTEGER NOT NULL,
                semester_id INTEGER,
                section TEXT NOT NULL,
                room_number TEXT,
                total_students INTEGER DEFAULT 0,
                institution_id TEXT NOT NULL,
                FOREIGN KEY (program_id) REFERENCES programs(id),
                FOREIGN KEY (semester_id) REFERENCES semesters(id)
            )
        ''')
        
        # Create faculty table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS faculty (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faculty_id TEXT UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                middle_name TEXT,
                last_name TEXT NOT NULL,
                email TEXT,
                phone_number TEXT,
                gender TEXT,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'faculty',
                institution_id TEXT NOT NULL,
                extra_notes TEXT,
                time_preference TEXT,
                is_teaching_staff INTEGER DEFAULT 0,
                majors TEXT,
                proficiency_score INTEGER,
                experience_years INTEGER,
                value_score INTEGER
            )
        ''')
        
        # Create faculty_classes mapping table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS faculty_classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faculty_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                subject TEXT,
                subject_ref_id INTEGER,
                institution_id TEXT NOT NULL,
                FOREIGN KEY (faculty_id) REFERENCES faculty(id),
                FOREIGN KEY (class_id) REFERENCES classes(id),
                UNIQUE(class_id, subject_ref_id, institution_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS class_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                batch_code TEXT NOT NULL,
                sequence_index INTEGER NOT NULL,
                start_position INTEGER NOT NULL,
                end_position INTEGER NOT NULL,
                student_count INTEGER NOT NULL,
                first_roll_label TEXT,
                last_roll_label TEXT,
                institution_id TEXT NOT NULL,
                UNIQUE(class_id, batch_code, institution_id),
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS faculty_subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faculty_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                institution_id TEXT NOT NULL,
                UNIQUE(faculty_id, subject_id, institution_id),
                FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            )
        ''')
        
        # Create students table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                middle_name TEXT,
                last_name TEXT NOT NULL,
                name TEXT,
                email TEXT,
                phone_number TEXT,
                gender TEXT,
                password TEXT NOT NULL,
                roll_no TEXT,
                program_id INTEGER NOT NULL,
                semester_id INTEGER,
                class_id INTEGER NOT NULL,
                gpa REAL,
                institution_id TEXT NOT NULL,
                FOREIGN KEY (program_id) REFERENCES programs(id),
                FOREIGN KEY (semester_id) REFERENCES semesters(id),
                FOREIGN KEY (class_id) REFERENCES classes(id)
            )
        ''')

        # Create subjects table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                teaching_hours INTEGER DEFAULT 0,
                delivery_mode TEXT NOT NULL CHECK(delivery_mode IN ('theory','practical')) DEFAULT 'theory',
                subject_type TEXT NOT NULL CHECK(subject_type IN ('semester', 'student', 'general')),
                semester_id INTEGER,
                institution_id TEXT NOT NULL,
                required_majors TEXT,
                min_proficiency INTEGER,
                min_experience INTEGER,
                min_value INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (semester_id) REFERENCES semesters(id)
            )
        ''')

        # Mapping table for subjects -> students (for direct assignments)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subject_students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                institution_id TEXT NOT NULL,
                UNIQUE(subject_id, student_id),
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            )
        ''')

        # Subject chapters for organizing resources
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subject_chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                chapter_name TEXT NOT NULL,
                chapter_number INTEGER,
                description TEXT,
                created_by TEXT,
                institution_id TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(subject_id, chapter_number),
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            )
        ''')

        # Subject resources metadata
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subject_resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                chapter_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                uploaded_by TEXT,
                uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                institution_id TEXT NOT NULL,
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (chapter_id) REFERENCES subject_chapters(id) ON DELETE SET NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subject_semesters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL,
                semester_id INTEGER NOT NULL,
                institution_id TEXT NOT NULL,
                UNIQUE(subject_id, semester_id, institution_id),
                FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                FOREIGN KEY (semester_id) REFERENCES semesters(id) ON DELETE CASCADE
            )
        ''')
        
        if load_samples:
            # Insert sample data only when requested (used during initial setup)
            programs = [
                ('CSE-UG', 'Computer Science & Engineering', 'CSE'),
                ('ECE-UG', 'Electronics & Communication Engineering', 'ECE'),
                ('ME-UG', 'Mechanical Engineering', 'ME'),
                ('CE-UG', 'Civil Engineering', 'CE'),
            ]
            program_ids = {}
            for prog_id, prog_name, code in programs:
                cursor.execute('''
                    INSERT INTO programs (program_id, program_name, code, institution_id)
                    VALUES (?, ?, ?, ?)
                ''', (prog_id, prog_name, code, institution_id))
                cursor.execute('SELECT id FROM programs WHERE program_id = ?', (prog_id,))
                program_ids[prog_id] = cursor.fetchone()[0]
            for prog_id in program_ids:
                for sem_num in range(1, 9):
                    sem_id = f"{prog_id}-SEM{sem_num}"
                    cursor.execute('''
                        INSERT INTO semesters (semester_id, semester_number, program_id, institution_id)
                        VALUES (?, ?, ?, ?)
                    ''', (sem_id, sem_num, program_ids[prog_id], institution_id))
            cursor.execute('SELECT id FROM semesters LIMIT 4')
            semester_ids = [row[0] for row in cursor.fetchall()]
            classes_data = [
                ('CSE-1A', 'CSE - Section A', program_ids['CSE-UG'], semester_ids[0] if len(semester_ids) > 0 else None, 'A', '101', 60),
                ('CSE-1B', 'CSE - Section B', program_ids['CSE-UG'], semester_ids[0] if len(semester_ids) > 0 else None, 'B', '102', 60),
                ('ECE-1A', 'ECE - Section A', program_ids['ECE-UG'], semester_ids[1] if len(semester_ids) > 1 else None, 'A', '201', 55),
                ('ME-1A', 'ME - Section A', program_ids['ME-UG'], semester_ids[2] if len(semester_ids) > 2 else None, 'A', '301', 50),
                ('CE-1A', 'CE - Section A', program_ids['CE-UG'], semester_ids[3] if len(semester_ids) > 3 else None, 'A', '401', 50),
            ]
            class_ids = {}
            for class_id, class_name, prog_id, sem_id, section, room, total in classes_data:
                cursor.execute('''
                    INSERT INTO classes (class_id, class_name, program_id, semester_id, section, room_number, total_students, institution_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (class_id, class_name, prog_id, sem_id, section, room, total, institution_id))
                cursor.execute('SELECT id FROM classes WHERE class_id = ?', (class_id,))
                class_ids[class_id] = cursor.fetchone()[0]
            students = [
                ('STD001', 'Arjun', '', 'Sharma', 'arjun@iitdelhi.ac.in', 'password123', '001', program_ids['CSE-UG'], semester_ids[0] if len(semester_ids) > 0 else None, class_ids['CSE-1A'], 3.8),
                ('STD002', 'Priya', '', 'Patel', 'priya@iitdelhi.ac.in', 'password123', '002', program_ids['CSE-UG'], semester_ids[0] if len(semester_ids) > 0 else None, class_ids['CSE-1A'], 3.9),
                ('STD003', 'Rohan', '', 'Singh', 'rohan@iitdelhi.ac.in', 'password123', '003', program_ids['CSE-UG'], semester_ids[0] if len(semester_ids) > 0 else None, class_ids['CSE-1B'], 3.7),
                ('STD004', 'Neha', '', 'Gupta', 'neha@iitdelhi.ac.in', 'password123', '004', program_ids['ECE-UG'], semester_ids[1] if len(semester_ids) > 1 else None, class_ids['ECE-1A'], 3.6),
                ('STD005', 'Vikram', '', 'Kumar', 'vikram@iitdelhi.ac.in', 'password123', '005', program_ids['ME-UG'], semester_ids[2] if len(semester_ids) > 2 else None, class_ids['ME-1A'], 3.5),
            ]
            for sid, fname, mname, lname, email, pwd, roll, prog_id, sem_id, class_id, gpa in students:
                cursor.execute('''
                    INSERT INTO students (student_id, first_name, middle_name, last_name, name, email, password, roll_no, program_id, semester_id, class_id, gpa, institution_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (sid, fname, mname, lname, f'{fname} {lname}', email, pwd, roll, prog_id, sem_id, class_id, gpa, institution_id))

            cursor.execute('''
                UPDATE classes
                SET total_students = (
                    SELECT COUNT(*) FROM students st
                    WHERE st.class_id = classes.id AND st.institution_id = classes.institution_id
                )
                WHERE institution_id = ?
            ''', (institution_id,))

            cursor.execute('SELECT id FROM classes WHERE institution_id = ?', (institution_id,))
            seed_class_ids = [row['id'] for row in cursor.fetchall()]
            for class_row_id in seed_class_ids:
                _recalculate_class_batches(cursor, class_row_id, institution_id)
        conn.commit()

def _init_faculty_db(institution_id):
    """Initialize Faculty database"""
    with get_db_connection(institution_id, 'faculty') as conn:
        cursor = conn.cursor()
        
        # Create faculties table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS faculties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faculty_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                password TEXT NOT NULL,
                department TEXT,
                specialization TEXT,
                experience INTEGER,
                extra_notes TEXT,
                institution_id TEXT NOT NULL
            )
        ''')
        
        # Create class-faculty mapping (which faculty teaches which class)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS class_faculty (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                faculty_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                semester INTEGER,
                FOREIGN KEY (faculty_id) REFERENCES faculties(id),
                UNIQUE(class_id, faculty_id, subject)
            )
        ''')
        
        # Create assignments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id TEXT UNIQUE NOT NULL,
                class_faculty_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                due_date DATETIME NOT NULL,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (class_faculty_id) REFERENCES class_faculty(id)
            )
        ''')
        
        # Create resources/notes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_id TEXT UNIQUE NOT NULL,
                class_faculty_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                file_path TEXT,
                resource_type TEXT,
                uploaded_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (class_faculty_id) REFERENCES class_faculty(id)
            )
        ''')
        
        # Insert sample data if not exists
        cursor.execute('SELECT COUNT(*) FROM faculties')
        if cursor.fetchone()[0] == 0:
            faculties = [
                ('FAC001', 'Dr. Rajesh Kumar', 'rajesh@iitdelhi.ac.in', 'faculty123', 'Computer Science', 'Machine Learning', 15),
                ('FAC002', 'Prof. Sneha Desai', 'sneha@iitdelhi.ac.in', 'faculty123', 'Electronics', 'Signal Processing', 12),
                ('FAC003', 'Dr. Anil Verma', 'anil@iitdelhi.ac.in', 'faculty123', 'Mechanical', 'Thermodynamics', 20),
            ]
            for faculty in faculties:
                cursor.execute('''
                    INSERT INTO faculties (faculty_id, name, email, password, department, specialization, experience, institution_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (*faculty, institution_id))
        
        conn.commit()

def _init_admin_db(institution_id):
    """Initialize Admin database"""
    with get_db_connection(institution_id, 'admin') as conn:
        cursor = conn.cursor()
        
        # Create admins table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                department TEXT,
                institution_id TEXT NOT NULL
            )
        ''')
        
        # Insert sample admin if not exists
        cursor.execute('SELECT COUNT(*) FROM admins')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO admins (admin_id, name, email, password, role, department, institution_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('ADM001', 'Mr. Vikram Patel', 'vikram@iitdelhi.ac.in', 'admin123', 'admin', 'Administration', institution_id))
        
        conn.commit()

# ============ Query Functions ============

def get_institution(institution_id):
    """Get institution by ID"""
    with get_db_connection(institution_id, 'master') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM institutions WHERE id = ?', (institution_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def get_all_institutions():
    """Get all institutions - reads from Master_Admin database"""
    with get_db_connection('iit_delhi', 'master') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM institutions')
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def verify_student(student_id, password, institution_id):
    """Verify student credentials"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM students 
            WHERE student_id = ? AND password = ? AND institution_id = ?
        ''', (student_id, password, institution_id))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def verify_faculty(faculty_id, password, institution_id):
    """Verify faculty credentials"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM faculty 
            WHERE faculty_id = ? AND password = ? AND institution_id = ?
        ''', (faculty_id, password, institution_id))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def verify_admin(admin_id, password, institution_id):
    """Verify admin credentials from Master_Admin.db"""
    with get_db_connection(institution_id, 'master') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT admin_id, name, email, role_type, can_create_admins, 
                   can_create_students, can_create_faculty
            FROM admin_roles 
            WHERE admin_id = ? AND password = ? AND institution_id = ? AND role_type = ?
        ''', (admin_id, password, institution_id, 'admin'))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def get_admin_info(admin_id, institution_id):
    """Get admin information for dashboard"""
    with get_db_connection(institution_id, 'master') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT admin_id, name, email, role_type, can_create_admins, 
                   can_create_students, can_create_faculty, created_date
            FROM admin_roles 
            WHERE admin_id = ? AND institution_id = ? AND role_type = ?
        ''', (admin_id, institution_id, 'admin'))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def get_student_info(student_id, institution_id):
    """Get student information"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM students 
            WHERE student_id = ? AND institution_id = ?
        ''', (student_id, institution_id))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def get_faculty_info(faculty_id, institution_id):
    """Get faculty information"""
    with get_db_connection(institution_id, 'faculty') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM faculties 
            WHERE faculty_id = ? AND institution_id = ?
        ''', (faculty_id, institution_id))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def get_faculty_classes(faculty_id, institution_id):
    """Get all classes taught by a faculty member"""
    with get_db_connection(institution_id, 'faculty') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT cf.id as class_faculty_id, cf.class_id, cf.subject, cf.semester
            FROM class_faculty cf
            JOIN faculties f ON cf.faculty_id = f.id
            WHERE f.faculty_id = ?
            ORDER BY cf.class_id
        ''', (faculty_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_class_faculty_record(class_faculty_id, institution_id):
    """Return class-faculty assignment with linked subject details."""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                fc.*, 
                c.class_name,
                c.class_id,
                subj.id AS subject_db_id,
                subj.subject_id AS subject_code,
                subj.name AS subject_name,
                subj.subject_type,
                subj.description AS subject_description
            FROM faculty_classes fc
            JOIN classes c ON fc.class_id = c.id
            LEFT JOIN subjects subj ON fc.subject_ref_id = subj.id
            WHERE fc.id = ? AND fc.institution_id = ?
        ''', (class_faculty_id, institution_id))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_class_students(class_id, institution_id):
    """Get all students in a class"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM students WHERE class_id = ?
            ORDER BY name
        ''', (class_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def create_assignment(class_faculty_id, title, description, due_date, institution_id):
    """Create a new assignment"""
    from datetime import datetime
    assignment_id = f"ASSIGN_{datetime.now().timestamp()}"
    with get_db_connection(institution_id, 'faculty') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO assignments (assignment_id, class_faculty_id, title, description, due_date, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (assignment_id, class_faculty_id, title, description, due_date, 'active'))
        
        conn.commit()
        return assignment_id

def get_class_faculty_assignments(class_faculty_id, institution_id):
    """Get all assignments for a class-faculty pair"""
    with get_db_connection(institution_id, 'faculty') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT a.id, a.assignment_id, a.title, a.description, a.due_date, a.status
            FROM assignments a
            WHERE a.class_faculty_id = ?
            ORDER BY a.due_date DESC
        ''', (class_faculty_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_assignment_students(assignment_id, institution_id):
    """Get assignment details"""
    with get_db_connection(institution_id, 'faculty') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM assignments WHERE id = ?
        ''', (assignment_id,))
        assignment = cursor.fetchone()
        if assignment:
            return dict(assignment)
        return None

def update_student_assignment_status(student_id, assignment_id, submission_status=None, verification_status=None, institution_id=None):
    """Update student assignment status"""
    # This can be implemented when student submission tracking is added
    pass

def get_student_class_assignments(student_id, institution_id):
    """Get all assignments for a student's class"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM students WHERE student_id = ?
        ''', (student_id,))
        student = cursor.fetchone()
        if not student:
            return []
        return [dict(student)]

def get_student_subjects(student_id, institution_id):
    """Return unified list of subjects visible to a student"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT 
                st.id AS student_db_id,
                st.student_id,
                st.class_id,
                st.semester_id,
                c.class_name,
                sem.semester_number,
                sem.semester_id AS semester_code,
                p.program_name
            FROM students st
            LEFT JOIN classes c ON st.class_id = c.id
            LEFT JOIN semesters sem ON st.semester_id = sem.id
            LEFT JOIN programs p ON sem.program_id = p.id
            WHERE st.student_id = ? AND st.institution_id = ?
        ''', (student_id, institution_id))
        student_row = cursor.fetchone()
        if not student_row:
            return []

        subjects_map = {}
        seen_subject_ids = set()

        def _normalize_identity(value):
            return value.strip().lower() if value else ''

        def find_subject_key(subject_code, subject_name):
            code_norm = _normalize_identity(subject_code)
            name_norm = _normalize_identity(subject_name)
            if not subjects_map:
                return None
            for key, payload in subjects_map.items():
                existing_code = _normalize_identity(payload.get('subject_code'))
                existing_name = _normalize_identity(payload.get('subject'))
                if code_norm and existing_code and code_norm == existing_code:
                    return key
                if name_norm and existing_name and name_norm == existing_name:
                    return key
            return None

        def upsert_subject(key, data):
            existing = subjects_map.get(key)
            if existing:
                for field, value in data.items():
                    if value is None or value == '':
                        continue
                    if field == 'resource_count':
                        existing[field] = max(existing.get(field, 0) or 0, value)
                    else:
                        existing[field] = value
            else:
                subjects_map[key] = data.copy()
            if data.get('subject_db_id'):
                seen_subject_ids.add(data['subject_db_id'])

        # Class-level subjects with faculty assignments
        if student_row['class_id']:
            cursor.execute('''
                SELECT 
                    fc.id AS class_faculty_id,
                    fc.subject AS subject_name,
                    fc.subject_ref_id,
                    c.class_name,
                    f.first_name || ' ' || f.last_name AS faculty_name,
                    f.faculty_id,
                    subj.id AS subject_db_id,
                    subj.subject_id AS subject_code,
                    subj.name AS subject_title,
                    subj.description AS subject_description,
                    subj.subject_type AS subject_type,
                    subj.teaching_hours,
                    subj.delivery_mode,
                    subj.has_theory_component,
                    subj.has_practical_component,
                    subj.theory_hours,
                    subj.practical_hours,
                    subj.requires_lab,
                    sem.semester_number,
                    p.program_name,
                    (SELECT COUNT(*) FROM subject_resources sr WHERE sr.subject_id = subj.id) AS resource_count
                FROM faculty_classes fc
                JOIN classes c ON fc.class_id = c.id
                JOIN faculty f ON fc.faculty_id = f.id
                LEFT JOIN subjects subj ON fc.subject_ref_id = subj.id
                LEFT JOIN semesters sem ON subj.semester_id = sem.id
                LEFT JOIN programs p ON sem.program_id = p.id
                WHERE fc.class_id = ? AND fc.institution_id = ?
            ''', (student_row['class_id'], institution_id))

            for row in cursor.fetchall():
                subject_name = row['subject_title'] or row['subject_name'] or 'Unassigned Subject'
                subject_key = row['subject_db_id'] or find_subject_key(row['subject_code'], subject_name) or f"class-{row['class_faculty_id']}"
                subject_type = row['subject_type'] or 'class'
                scope_label = subject_type == 'semester' and (row['program_name'] or student_row['program_name'])
                if scope_label:
                    scope_label = f"{scope_label} • Semester {row['semester_number'] or student_row['semester_number'] or '-'}"
                else:
                    scope_label = row['class_name'] or 'Classroom Subject'

                upsert_subject(subject_key, {
                    'origin': 'class_faculty',
                    'class_faculty_id': row['class_faculty_id'],
                    'subject_db_id': row['subject_db_id'],
                    'subject': subject_name,
                    'subject_code': row['subject_code'],
                    'subject_type': subject_type,
                    'scope_label': scope_label,
                    'faculty_name': row['faculty_name'],
                    'faculty_id': row['faculty_id'],
                    'class_name': row['class_name'],
                    'program_name': row['program_name'] or student_row['program_name'],
                    'semester_number': row['semester_number'] or student_row['semester_number'],
                    'resource_count': row['resource_count'] or 0,
                    'description': row['subject_description'] or '',
                    'teaching_hours': row['teaching_hours'] or 0,
                    'delivery_mode': row['delivery_mode'] or 'theory',
                    'has_theory_component': bool(row['has_theory_component']),
                    'has_practical_component': bool(row['has_practical_component']),
                    'theory_hours': row['theory_hours'] or 0,
                    'practical_hours': row['practical_hours'] or 0,
                    'requires_lab': bool(row['requires_lab'])
                })

        # Semester subjects (syllabus)
        if student_row['semester_id']:
            cursor.execute('''
                SELECT DISTINCT
                    s.id,
                    s.subject_id,
                    s.name,
                    s.description,
                    s.subject_type,
                    s.teaching_hours,
                    s.delivery_mode,
                    s.has_theory_component,
                    s.has_practical_component,
                    s.theory_hours,
                    s.practical_hours,
                    s.requires_lab,
                    COALESCE(sem_map.semester_number, sem.semester_number) AS semester_number,
                    COALESCE(prog_map.program_name, prog.program_name) AS program_name,
                    (SELECT COUNT(*) FROM subject_resources sr WHERE sr.subject_id = s.id) AS resource_count
                FROM subjects s
                LEFT JOIN subject_semesters ss ON s.id = ss.subject_id
                LEFT JOIN semesters sem_map ON ss.semester_id = sem_map.id
                LEFT JOIN programs prog_map ON sem_map.program_id = prog_map.id
                LEFT JOIN semesters sem ON s.semester_id = sem.id
                LEFT JOIN programs p ON sem.program_id = p.id
                WHERE s.subject_type = 'semester' 
                  AND ((ss.semester_id = ?) OR (ss.semester_id IS NULL AND s.semester_id = ?))
                  AND s.institution_id = ?
                ORDER BY s.name
            ''', (student_row['semester_id'], student_row['semester_id'], institution_id))

            for row in cursor.fetchall():
                key = find_subject_key(row['subject_id'], row['name']) or row['id']
                scope_label = f"{row['program_name'] or student_row['program_name'] or 'Program'} • Semester {row['semester_number'] or student_row['semester_number'] or '-'}"
                upsert_subject(key, {
                    'origin': 'semester',
                    'subject_db_id': row['id'],
                    'subject': row['name'],
                    'subject_code': row['subject_id'],
                    'subject_type': 'semester',
                    'scope_label': scope_label,
                    'program_name': row['program_name'] or student_row['program_name'],
                    'semester_number': row['semester_number'] or student_row['semester_number'],
                    'resource_count': row['resource_count'] or 0,
                    'description': row['description'] or '',
                    'teaching_hours': row['teaching_hours'] or 0,
                    'delivery_mode': row['delivery_mode'] or 'theory',
                    'has_theory_component': bool(row['has_theory_component']),
                    'has_practical_component': bool(row['has_practical_component']),
                    'theory_hours': row['theory_hours'] or 0,
                    'practical_hours': row['practical_hours'] or 0,
                    'requires_lab': bool(row['requires_lab'])
                })

        # Direct enrollment subjects
        cursor.execute('''
            SELECT 
                s.id,
                s.subject_id,
                s.name,
                s.description,
                s.subject_type,
                s.teaching_hours,
                s.delivery_mode,
                s.has_theory_component,
                s.has_practical_component,
                s.theory_hours,
                s.practical_hours,
                s.requires_lab,
                (SELECT COUNT(*) FROM subject_resources sr WHERE sr.subject_id = s.id) AS resource_count
            FROM subject_students ss
            JOIN subjects s ON ss.subject_id = s.id
            WHERE ss.student_id = ? AND ss.institution_id = ?
            ORDER BY s.name
        ''', (student_row['student_db_id'], institution_id))

        for row in cursor.fetchall():
            existing_key = find_subject_key(row['subject_id'], row['name'])
            if row['id'] in seen_subject_ids and not existing_key:
                continue
            upsert_subject(existing_key or row['id'], {
                'origin': 'direct',
                'subject_db_id': row['id'],
                'subject': row['name'],
                'subject_code': row['subject_id'],
                'subject_type': row['subject_type'],
                'scope_label': 'Direct Enrollment',
                'resource_count': row['resource_count'] or 0,
                'description': row['description'] or '',
                'teaching_hours': row['teaching_hours'] or 0,
                'delivery_mode': row['delivery_mode'] or 'theory',
                'has_theory_component': bool(row['has_theory_component']),
                'has_practical_component': bool(row['has_practical_component']),
                'theory_hours': row['theory_hours'] or 0,
                'practical_hours': row['practical_hours'] or 0,
                'requires_lab': bool(row['requires_lab'])
            })

        # Default fallbacks
        for subject in subjects_map.values():
            if not subject.get('faculty_name') and subject.get('subject_type') == 'semester':
                subject['faculty_name'] = 'Semester faculty not assigned yet'
            elif not subject.get('faculty_name'):
                subject['faculty_name'] = 'Faculty not assigned'
            if not subject.get('scope_label'):
                subject['scope_label'] = student_row['class_name'] or student_row['program_name'] or 'Subject'
            subject.setdefault('class_name', student_row['class_name'])

        return list(subjects_map.values())


def is_subject_accessible_to_student(student_id, subject_db_id, institution_id):
    """Check if a subject (and therefore its chapters/resources) is visible to a student."""
    if not subject_db_id:
        return False
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, class_id, semester_id
            FROM students
            WHERE student_id = ? AND institution_id = ?
        ''', (student_id, institution_id))
        student_row = cursor.fetchone()
        if not student_row:
            return False

        cursor.execute('''
            SELECT id, subject_type, semester_id
            FROM subjects
            WHERE id = ? AND institution_id = ?
        ''', (subject_db_id, institution_id))
        subject_row = cursor.fetchone()
        if not subject_row:
            return False

        if subject_row['subject_type'] == 'general':
            return True

        if subject_row['subject_type'] == 'semester':
            if subject_row['semester_id'] == student_row['semester_id']:
                return True
            cursor.execute('''
                SELECT 1 FROM subject_semesters
                WHERE subject_id = ? AND semester_id = ? AND institution_id = ?
            ''', (subject_db_id, student_row['semester_id'], institution_id))
            if cursor.fetchone():
                return True

        cursor.execute('''
            SELECT 1 FROM subject_students
            WHERE subject_id = ? AND student_id = ? AND institution_id = ?
        ''', (subject_db_id, student_row['id'], institution_id))
        if cursor.fetchone():
            return True

        cursor.execute('''
            SELECT 1 FROM faculty_classes
            WHERE subject_ref_id = ? AND class_id = ? AND institution_id = ?
        ''', (subject_db_id, student_row['class_id'], institution_id))
        return cursor.fetchone() is not None

def get_subject_assignments(class_faculty_id, institution_id):
    """Get all assignments for a specific subject/class-faculty pair"""
    with get_db_connection(institution_id, 'faculty') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM assignments WHERE class_faculty_id = ?
            ORDER BY due_date DESC
        ''', (class_faculty_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

# ============ Principal & Admin Management Functions ============

def verify_principal(admin_id, password, institution_id):
    """Verify principal credentials - only principal can verify from Master_Admin.db"""
    with get_db_connection(institution_id, 'master') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM admin_roles 
            WHERE admin_id = ? AND password = ? AND role_type = ? AND institution_id = ?
        ''', (admin_id, password, 'principal', institution_id))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def create_admin(admin_id, name, email, password, role_type, institution_id, can_create_students=False, can_create_faculty=False, can_create_admins=False):
    """Create a new admin account (only master_admin can call this)"""
    
    with get_db_connection(institution_id, 'master') as conn:
        cursor = conn.cursor()
        
        # Check if admin already exists
        cursor.execute('SELECT COUNT(*) FROM admin_roles WHERE email = ?', (email,))
        if cursor.fetchone()[0] > 0:
            return {'status': 'error', 'message': 'Email already exists'}
        
        cursor.execute('SELECT COUNT(*) FROM admin_roles WHERE admin_id = ?', (admin_id,))
        if cursor.fetchone()[0] > 0:
            return {'status': 'error', 'message': 'Admin ID already exists'}
        
        cursor.execute('''
            INSERT INTO admin_roles (admin_id, name, email, password, role_type, institution_id, 
                                    can_create_students, can_create_faculty, can_create_admins)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (admin_id, name, email, password, role_type, institution_id, 
              can_create_students, can_create_faculty, can_create_admins))
        
        conn.commit()
        return {'status': 'success', 'admin_id': admin_id, 'message': f'Admin {name} created successfully'}

def get_all_admins(institution_id):
    """Get all admins for an institution (without passwords)"""
    with get_db_connection(institution_id, 'master') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, admin_id, name, email, role_type, can_create_admins, 
                   can_create_students, can_create_faculty, created_date
            FROM admin_roles
            WHERE institution_id = ?
            ORDER BY created_date DESC
        ''', (institution_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_admin_by_id(admin_id, institution_id):
    """Get admin details by admin_id (without password)"""
    with get_db_connection(institution_id, 'master') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, admin_id, name, email, role_type, can_create_admins, 
                   can_create_students, can_create_faculty, created_date
            FROM admin_roles
            WHERE admin_id = ? AND institution_id = ?
        ''', (admin_id, institution_id))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

def update_admin_permissions(admin_id, institution_id, can_create_students=None, can_create_faculty=None, can_create_admins=None):
    """Update admin permissions"""
    with get_db_connection(institution_id, 'master') as conn:
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if can_create_students is not None:
            updates.append('can_create_students = ?')
            params.append(can_create_students)
        if can_create_faculty is not None:
            updates.append('can_create_faculty = ?')
            params.append(can_create_faculty)
        if can_create_admins is not None:
            updates.append('can_create_admins = ?')
            params.append(can_create_admins)
        
        if not updates:
            return {'status': 'error', 'message': 'No updates provided'}
        
        params.append(admin_id)
        params.append(institution_id)
        
        query = f"UPDATE admin_roles SET {', '.join(updates)} WHERE admin_id = ? AND institution_id = ?"
        cursor.execute(query, params)
        conn.commit()
        
        return {'status': 'success', 'message': 'Admin permissions updated'}

def reset_admin_password(admin_id, new_password, institution_id):
    """Reset admin password (principal only)"""
    with get_db_connection(institution_id, 'master') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE admin_roles
            SET password = ?
            WHERE admin_id = ? AND institution_id = ?
        ''', (new_password, admin_id, institution_id))
        
        if cursor.rowcount == 0:
            conn.commit()
            return {'status': 'error', 'message': 'Admin not found'}
        
        conn.commit()
        return {'status': 'success', 'message': 'Password reset successfully'}

def delete_admin(admin_id, institution_id):
    """Delete an admin account (principal only)"""
    with get_db_connection(institution_id, 'master') as conn:
        cursor = conn.cursor()
        
        # Prevent deleting principal
        cursor.execute('SELECT role_type FROM admin_roles WHERE admin_id = ? AND institution_id = ?', 
                      (admin_id, institution_id))
        row = cursor.fetchone()
        
        if not row:
            return {'status': 'error', 'message': 'Admin not found'}
        
        if dict(row)['role_type'] == 'principal':
            return {'status': 'error', 'message': 'Cannot delete principal account'}
        
        cursor.execute('''
            DELETE FROM admin_roles
            WHERE admin_id = ? AND institution_id = ? AND role_type != ?
        ''', (admin_id, institution_id, 'principal'))
        
        conn.commit()
        return {'status': 'success', 'message': 'Admin deleted successfully'}

def get_admin_stats(institution_id):
    """Get admin statistics for principal dashboard"""
    with get_db_connection(institution_id, 'master') as conn:
        cursor = conn.cursor()
        
        # Total admins
        cursor.execute('SELECT COUNT(*) as total FROM admin_roles WHERE institution_id = ?', 
                      (institution_id,))
        total_admins = cursor.fetchone()[0]
        
        # Admins by role type
        cursor.execute('''
            SELECT role_type, COUNT(*) as count 
            FROM admin_roles 
            WHERE institution_id = ? 
            GROUP BY role_type
        ''', (institution_id,))
        role_stats = {dict(row)['role_type']: dict(row)['count'] for row in cursor.fetchall()}
        
        # Admins with specific permissions
        cursor.execute('SELECT COUNT(*) as count FROM admin_roles WHERE can_create_students = 1 AND institution_id = ?', 
                      (institution_id,))
        can_create_students = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) as count FROM admin_roles WHERE can_create_faculty = 1 AND institution_id = ?', 
                      (institution_id,))
        can_create_faculty = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) as count FROM admin_roles WHERE can_create_admins = 1 AND institution_id = ?', 
                      (institution_id,))
        can_create_admins = cursor.fetchone()[0]
        
        return {
            'total_admins': total_admins,
            'role_stats': role_stats,
            'can_create_students': can_create_students,
            'can_create_faculty': can_create_faculty,
            'can_create_admins': can_create_admins
        }

# ============ BRANCH/PROGRAM MANAGEMENT ============

def create_program(program_id, program_name, code, institution_id):
    """Create a new branch/program"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO programs (program_id, program_name, code, institution_id)
                VALUES (?, ?, ?, ?)
            ''', (program_id, program_name, code, institution_id))
            conn.commit()
            return {'status': 'success', 'message': f'Branch {program_name} created'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

def get_all_programs(institution_id):
    """Get all branches/programs"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, program_id, program_name, code FROM programs WHERE institution_id = ? ORDER BY program_name', 
                      (institution_id,))
        return [dict(row) for row in cursor.fetchall()]

# ============ SEMESTER MANAGEMENT ============

def create_semester(semester_id, semester_number, program_id, institution_id):
    """Create a new semester for a program"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO semesters (semester_id, semester_number, program_id, institution_id)
                VALUES (?, ?, ?, ?)
            ''', (semester_id, semester_number, program_id, institution_id))
            conn.commit()
            return {'status': 'success', 'message': f'Semester {semester_number} created'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

def get_semesters_by_program(program_id, institution_id):
    """Get all semesters for a program"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, semester_id, semester_number, program_id
            FROM semesters 
            WHERE program_id = ? AND institution_id = ? 
            ORDER BY semester_number
        ''', (program_id, institution_id))
        return [dict(row) for row in cursor.fetchall()]

# ============ CLASS MANAGEMENT ============

def create_class(class_id, class_name, semester_id, program_id, section, institution_id, room_number=None, home_room_id=None):
    """Create a new class"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        try:
            if home_room_id:
                conflict = get_class_using_home_room(home_room_id, institution_id)
                if conflict:
                    return {
                        'status': 'error',
                        'message': f"Home room already assigned to {conflict['class_name']} ({conflict['section']})"
                    }
            cursor.execute('''
                INSERT INTO classes (class_id, class_name, semester_id, program_id, section, room_number, home_room_id, institution_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (class_id, class_name, semester_id, program_id, section, room_number or '', home_room_id, institution_id))
            conn.commit()
            return {'status': 'success', 'message': f'Class {class_name} created'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}


def get_class_using_home_room(home_room_id, institution_id, exclude_class_id=None):
    if not home_room_id:
        return None
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        query = '''
            SELECT id, class_name, section
            FROM classes
            WHERE institution_id = ? AND home_room_id = ?
        '''
        params = [institution_id, home_room_id]
        if exclude_class_id:
            query += ' AND id != ?'
            params.append(exclude_class_id)
        cursor.execute(query, tuple(params))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_class_by_id(class_db_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, class_id, class_name, program_id, semester_id, section,
                   room_number, home_room_id
            FROM classes
            WHERE id = ? AND institution_id = ?
        ''', (class_db_id, institution_id))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_class_record(class_db_id, institution_id, **fields):
    allowed = {
        'class_name', 'section', 'room_number', 'home_room_id'
    }
    updates = []
    params = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key == 'home_room_id' and value in (None, '', 0):
            updates.append('home_room_id = NULL')
        elif key == 'room_number' and value in (None, ''):
            updates.append('room_number = NULL')
        elif key == 'home_room_id':
            conflict = get_class_using_home_room(int(value), institution_id, exclude_class_id=class_db_id)
            if conflict:
                return {
                    'status': 'error',
                    'message': f"Home room already assigned to {conflict['class_name']} ({conflict['section']})"
                }
            updates.append('home_room_id = ?')
            params.append(int(value))
        else:
            updates.append(f'{key} = ?')
            params.append(value)
    if not updates:
        return {'status': 'success'}
    params.extend([class_db_id, institution_id])
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(f'''
                UPDATE classes SET {', '.join(updates)}
                WHERE id = ? AND institution_id = ?
            ''', tuple(params))
            conn.commit()
            return {'status': 'success'}
        except Exception as exc:
            return {'status': 'error', 'message': str(exc)}

def get_classes_by_semester(semester_id, institution_id):
    """Get all classes for a semester"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, class_id, class_name, program_id, semester_id, section,
                   total_students, home_room_id, room_number
            FROM classes 
            WHERE semester_id = ? AND institution_id = ?
            ORDER BY section
        ''', (semester_id, institution_id))
        return [dict(row) for row in cursor.fetchall()]


def get_all_classes(institution_id):
    """Get all classes for an institution"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, class_id, class_name, section, total_students, semester_id, program_id
            FROM classes
            WHERE institution_id = ?
            ORDER BY class_name
        ''', (institution_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_classes_without_home_room(institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, class_name, section, program_id, semester_id
            FROM classes
            WHERE institution_id = ? AND (home_room_id IS NULL OR home_room_id = 0)
        ''', (institution_id,))
        return [dict(row) for row in cursor.fetchall()]


def _parse_roll_number(raw_value):
    try:
        text_value = str(raw_value).strip()
    except (TypeError, ValueError):
        return None
    if not text_value:
        return None
    try:
        return int(text_value.lstrip('0') or '0')
    except ValueError:
        return None


def _fetch_class_students_for_batches(cursor, class_id, institution_id):
    cursor.execute('''
        SELECT id, student_id, first_name, last_name, roll_no
        FROM students
        WHERE class_id = ? AND institution_id = ?
    ''', (class_id, institution_id))
    rows = [dict(row) for row in cursor.fetchall()]
    if not rows:
        return []

    def sort_key(row):
        parsed_roll = _parse_roll_number(row.get('roll_no'))
        fallback = (row.get('student_id') or '').strip().upper()
        return (0, parsed_roll, row.get('id')) if parsed_roll is not None else (1, fallback, row.get('id'))

    return sorted(rows, key=sort_key)


def _refresh_class_enrollment_metadata(cursor, class_id, institution_id):
    cursor.execute('''
        SELECT COUNT(*) AS total
        FROM students
        WHERE class_id = ? AND institution_id = ?
    ''', (class_id, institution_id))
    total = cursor.fetchone()[0]
    cursor.execute('''
        UPDATE classes
        SET total_students = ?
        WHERE id = ? AND institution_id = ?
    ''', (total, class_id, institution_id))
    _recalculate_class_batches(cursor, class_id, institution_id)
    return total


def _recalculate_class_batches(cursor, class_id, institution_id):
    students = _fetch_class_students_for_batches(cursor, class_id, institution_id)
    cursor.execute('DELETE FROM class_batches WHERE class_id = ? AND institution_id = ?', (class_id, institution_id))
    if not students:
        return []

    payloads = []
    total = len(students)
    for index, start in enumerate(range(0, total, MAX_LAB_BATCH_SIZE)):
        segment = students[start:start + MAX_LAB_BATCH_SIZE]
        if not segment:
            continue
        batch_code = f"B{index + 1}"
        start_position = start + 1
        end_position = start + len(segment)
        payloads.append((
            class_id,
            batch_code,
            index + 1,
            start_position,
            end_position,
            len(segment),
            segment[0].get('roll_no') or segment[0].get('student_id'),
            segment[-1].get('roll_no') or segment[-1].get('student_id'),
            institution_id
        ))

    cursor.executemany('''
        INSERT INTO class_batches (
            class_id,
            batch_code,
            sequence_index,
            start_position,
            end_position,
            student_count,
            first_roll_label,
            last_roll_label,
            institution_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', payloads)
    return payloads


def recalculate_class_batches(class_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        return _recalculate_class_batches(cursor, class_id, institution_id)


def refresh_class_enrollment_metadata(class_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        return _refresh_class_enrollment_metadata(cursor, class_id, institution_id)


def _fetch_class_batches(cursor, class_id, institution_id):
    cursor.execute('''
        SELECT id, batch_code, sequence_index, start_position, end_position,
               student_count, first_roll_label, last_roll_label
        FROM class_batches
        WHERE class_id = ? AND institution_id = ?
        ORDER BY sequence_index
    ''', (class_id, institution_id))
    return [dict(row) for row in cursor.fetchall()]


def get_class_batches(class_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        return _fetch_class_batches(cursor, class_id, institution_id)


def get_class_practical_subjects(class_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT
                subj.id AS subject_db_id,
                subj.subject_id AS subject_code,
                subj.name AS subject_name,
                subj.delivery_mode
            FROM faculty_classes fc
            JOIN subjects subj ON fc.subject_ref_id = subj.id
            WHERE fc.class_id = ? AND fc.institution_id = ? AND subj.delivery_mode = 'practical'
            ORDER BY subj.name
        ''', (class_id, institution_id))
        return [dict(row) for row in cursor.fetchall()]


def get_parallel_practical_status(class_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT total_students FROM classes
            WHERE id = ? AND institution_id = ?
        ''', (class_id, institution_id))
        class_row = cursor.fetchone()
        total_students = class_row['total_students'] if class_row else 0

        batches = _fetch_class_batches(cursor, class_id, institution_id)
        if not batches and total_students:
            _recalculate_class_batches(cursor, class_id, institution_id)
            batches = _fetch_class_batches(cursor, class_id, institution_id)

        batch_count = len(batches)
        if not batch_count and total_students:
            batch_count = (total_students + MAX_LAB_BATCH_SIZE - 1) // MAX_LAB_BATCH_SIZE

        cursor.execute('''
            SELECT DISTINCT
                subj.id AS subject_db_id,
                subj.subject_id AS subject_code,
                subj.name AS subject_name
            FROM faculty_classes fc
            JOIN subjects subj ON fc.subject_ref_id = subj.id
            WHERE fc.class_id = ? AND fc.institution_id = ? AND subj.delivery_mode = 'practical'
        ''', (class_id, institution_id))
        practical_subjects = [dict(row) for row in cursor.fetchall()]

        required_parallel = 0
        if total_students:
            required_parallel = max(1, batch_count)

        ready = len(practical_subjects) >= required_parallel if required_parallel else False
        missing = max(0, required_parallel - len(practical_subjects)) if required_parallel else 0

        return {
            'class_id': class_id,
            'total_students': total_students,
            'batch_count': batch_count,
            'required_parallel_sessions': required_parallel,
            'lab_batch_size': MAX_LAB_BATCH_SIZE,
            'practical_subjects': practical_subjects,
            'ready': ready,
            'missing_subjects': missing
        }

# ============ CAMPUS RESOURCE MANAGEMENT ============

def ensure_campus_floors(max_floor, institution_id):
    """Ensure floors from 0..max_floor exist."""
    max_floor = max(0, int(max_floor))
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        for number in range(0, max_floor + 1):
            cursor.execute('''
                INSERT OR IGNORE INTO campus_floors (institution_id, floor_number)
                VALUES (?, ?)
            ''', (institution_id, number))
        conn.commit()
    return get_campus_floors(institution_id)


def update_floor_label(floor_id, label, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE campus_floors SET label = ?
            WHERE id = ? AND institution_id = ?
        ''', (label or '', floor_id, institution_id))
        conn.commit()
        return cursor.rowcount > 0


def update_subject(subject_db_id, data, institution_id):
    """Update subject metadata, semester assignments, and direct-student links."""
    allowed_fields = {'subject_id', 'name', 'description', 'subject_type'}
    updates = {key: data.get(key) for key in allowed_fields if key in data}

    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM subjects WHERE id = ? AND institution_id = ?', (subject_db_id, institution_id))
        subject_row = cursor.fetchone()
        if not subject_row:
            return {'status': 'error', 'message': 'Subject not found'}

        subject_type = updates.get('subject_type', subject_row['subject_type'])
        if subject_type not in ('semester', 'student', 'general'):
            subject_type = subject_row['subject_type']

        existing_theory_flag = bool(subject_row.get('has_theory_component'))
        existing_practical_flag = bool(subject_row.get('has_practical_component'))
        existing_theory_hours = subject_row.get('theory_hours') or 0
        existing_practical_hours = subject_row.get('practical_hours') or 0
        existing_requires_lab = bool(subject_row.get('requires_lab'))

        theory_flag = existing_theory_flag
        practical_flag = existing_practical_flag
        if 'has_theory_component' in data:
            parsed = _parse_bool_flag(data.get('has_theory_component'))
            theory_flag = bool(parsed)
        if 'has_practical_component' in data:
            parsed = _parse_bool_flag(data.get('has_practical_component'))
            practical_flag = bool(parsed)

        if not theory_flag and not practical_flag:
            return {'status': 'error', 'message': 'Select at least one delivery component'}

        theory_hours_value = existing_theory_hours
        practical_hours_value = existing_practical_hours
        if 'theory_hours' in data:
            coerced = _coerce_non_negative_int(data.get('theory_hours'))
            theory_hours_value = coerced if coerced is not None else 0
        if 'practical_hours' in data:
            coerced = _coerce_non_negative_int(data.get('practical_hours'))
            practical_hours_value = coerced if coerced is not None else 0

        hours_override = None
        if 'teaching_hours' in data:
            override_value = _coerce_non_negative_int(data.get('teaching_hours'))
            hours_override = override_value if override_value is not None else 0

        if hours_override is not None and 'theory_hours' not in data and 'practical_hours' not in data:
            if theory_flag and not practical_flag:
                theory_hours_value = hours_override
                practical_hours_value = 0
            elif practical_flag and not theory_flag:
                practical_hours_value = hours_override
                theory_hours_value = 0
            elif theory_flag and practical_flag:
                theory_hours_value = hours_override // 2
                practical_hours_value = hours_override - theory_hours_value

        if not theory_flag:
            theory_hours_value = 0
        if not practical_flag:
            practical_hours_value = 0

        requires_lab_flag = existing_requires_lab
        if 'requires_lab' in data:
            parsed = _parse_bool_flag(data.get('requires_lab'))
            requires_lab_flag = bool(parsed)
        if not practical_flag:
            requires_lab_flag = False

        delivery_mode = 'practical' if practical_flag else 'theory'
        total_hours = 0
        if theory_flag:
            total_hours += theory_hours_value
        if practical_flag:
            total_hours += practical_hours_value

        semester_ids = data.get('semester_ids')
        normalized_semesters = None
        primary_semester_id = subject_row['semester_id']
        if semester_ids is not None:
            normalized_semesters = []
            for sem_value in semester_ids:
                try:
                    sem_int = int(sem_value)
                except (TypeError, ValueError):
                    continue
                if sem_int not in normalized_semesters:
                    normalized_semesters.append(sem_int)
            primary_semester_id = normalized_semesters[0] if normalized_semesters else None
            if subject_type == 'semester' and not primary_semester_id:
                return {'status': 'error', 'message': 'Semester subjects require at least one semester'}

        student_ids_payload = data.get('student_ids') if 'student_ids' in data else None
        normalized_student_inputs = None
        resolved_student_ids = []
        missing_students = []
        if student_ids_payload is not None:
            normalized_student_inputs = []
            if isinstance(student_ids_payload, str):
                normalized_student_inputs = [item.strip() for item in student_ids_payload.split(',') if item.strip()]
            elif isinstance(student_ids_payload, (list, tuple, set)):
                for value in student_ids_payload:
                    if value is None:
                        continue
                    normalized_student_inputs.append(str(value).strip())
                normalized_student_inputs = [val for val in normalized_student_inputs if val]
            else:
                normalized_student_inputs = []

            resolved_student_ids, missing_students = _resolve_student_ids(cursor, normalized_student_inputs, institution_id)

        update_fields = []
        params = []
        if 'subject_id' in updates and updates['subject_id']:
            update_fields.append('subject_id = ?')
            params.append(str(updates['subject_id']).strip())
        if 'name' in updates and updates['name']:
            update_fields.append('name = ?')
            params.append(updates['name'].strip())
        if 'description' in updates:
            update_fields.append('description = ?')
            params.append((updates['description'] or '').strip())
        if 'subject_type' in updates:
            update_fields.append('subject_type = ?')
            params.append(subject_type)
        update_fields.append('teaching_hours = ?')
        params.append(total_hours)
        update_fields.append('delivery_mode = ?')
        params.append(delivery_mode)
        update_fields.append('has_theory_component = ?')
        params.append(1 if theory_flag else 0)
        update_fields.append('has_practical_component = ?')
        params.append(1 if practical_flag else 0)
        update_fields.append('theory_hours = ?')
        params.append(theory_hours_value)
        update_fields.append('practical_hours = ?')
        params.append(practical_hours_value)
        update_fields.append('requires_lab = ?')
        params.append(1 if requires_lab_flag else 0)

        if semester_ids is not None:
            update_fields.append('semester_id = ?')
            params.append(primary_semester_id)

        if update_fields:
            cursor.execute(f'''
                UPDATE subjects
                SET {', '.join(update_fields)}
                WHERE id = ? AND institution_id = ?
            ''', (*params, subject_db_id, institution_id))

        if semester_ids is not None:
            cursor.execute('DELETE FROM subject_semesters WHERE subject_id = ? AND institution_id = ?', (subject_db_id, institution_id))
            if normalized_semesters:
                cursor.executemany('''
                    INSERT OR IGNORE INTO subject_semesters (subject_id, semester_id, institution_id)
                    VALUES (?, ?, ?)
                ''', [(subject_db_id, sem_id, institution_id) for sem_id in normalized_semesters])

        replace_students = normalized_student_inputs is not None
        students_payload = []
        if subject_type != 'student':
            cursor.execute('DELETE FROM subject_students WHERE subject_id = ? AND institution_id = ?', (subject_db_id, institution_id))
        elif replace_students:
            cursor.execute('DELETE FROM subject_students WHERE subject_id = ? AND institution_id = ?', (subject_db_id, institution_id))
            if resolved_student_ids:
                cursor.executemany('''
                    INSERT OR IGNORE INTO subject_students (subject_id, student_id, institution_id)
                    VALUES (?, ?, ?)
                ''', [(subject_db_id, sid, institution_id) for sid in resolved_student_ids])

        if subject_type == 'student':
            cursor.execute('''
                SELECT st.student_id, st.first_name, st.last_name
                FROM subject_students ss
                JOIN students st ON ss.student_id = st.id
                WHERE ss.subject_id = ? AND ss.institution_id = ?
                ORDER BY st.student_id
            ''', (subject_db_id, institution_id))
            students_payload = [dict(row) for row in cursor.fetchall()]

        conn.commit()
        response = {
            'status': 'success',
            'students': students_payload,
            'missing_students': missing_students
        }
        return response


def get_campus_floors(institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT f.id, f.floor_number, COALESCE(f.label, '') AS label,
                   (SELECT COUNT(*) FROM campus_sections s WHERE s.floor_id = f.id) AS section_count,
                   (SELECT COUNT(*) FROM campus_rooms r WHERE r.floor_id = f.id) AS room_count
            FROM campus_floors f
            WHERE f.institution_id = ?
            ORDER BY f.floor_number
        ''', (institution_id,))
        return [dict(row) for row in cursor.fetchall()]


def create_campus_sections(name, floor_ids, institution_id):
    if not name:
        return {'status': 'error', 'message': 'Section name required'}
    if not floor_ids:
        return {'status': 'error', 'message': 'Pick at least one floor'}
    created = 0
    skipped = []
    unique_floor_ids = []
    for fid in floor_ids:
        if fid not in unique_floor_ids:
            unique_floor_ids.append(fid)
    skipped_labels = []
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        for floor_id in unique_floor_ids:
            cursor.execute('''
                SELECT id FROM campus_floors WHERE id = ? AND institution_id = ?
            ''', (floor_id, institution_id))
            if not cursor.fetchone():
                continue
            cursor.execute('''
                SELECT id FROM campus_sections
                WHERE institution_id = ? AND floor_id = ? AND LOWER(name) = LOWER(?)
            ''', (institution_id, floor_id, name.strip()))
            if cursor.fetchone():
                skipped.append(floor_id)
                continue
            cursor.execute('''
                INSERT INTO campus_sections (institution_id, floor_id, name)
                VALUES (?, ?, ?)
            ''', (institution_id, floor_id, name.strip()))
            created += 1
        conn.commit()
        if skipped:
            placeholders = ','.join(['?'] * len(skipped))
            cursor.execute(f'''
                SELECT id, floor_number, COALESCE(label, '') AS label
                FROM campus_floors
                WHERE institution_id = ? AND id IN ({placeholders})
            ''', tuple([institution_id] + skipped))
            for row in cursor.fetchall():
                skipped_labels.append(row['label'] or f"Floor {row['floor_number']}")
    if not created:
        message = 'Section already exists on selected floors' if skipped else 'No sections created'
        return {'status': 'error', 'message': message, 'skipped': skipped}
    response = {'status': 'success', 'created': created}
    if skipped:
        response['skipped'] = skipped
        response['message'] = f"Skipped existing sections on: {', '.join(skipped_labels)}"
    return response


def get_campus_sections(institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.id, s.floor_id, s.name
            FROM campus_sections s
            JOIN campus_floors f ON f.id = s.floor_id
            WHERE s.institution_id = ?
            ORDER BY f.floor_number, s.name
        ''', (institution_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_campus_room_by_id(room_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.*, f.floor_number, s.name AS section_name
            FROM campus_rooms r
            JOIN campus_floors f ON r.floor_id = f.id
            LEFT JOIN campus_sections s ON r.section_id = s.id
            WHERE r.id = ? AND r.institution_id = ?
        ''', (room_id, institution_id))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_campus_rooms_flat(institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.id, r.room_number, r.room_type, r.capacity,
                   r.assigned_subject_id, r.custom_title, r.custom_function,
                   COALESCE(f.label, '') AS floor_label, f.floor_number,
                   COALESCE(s.name, '') AS section_name,
                   COALESCE(sub.subject_id, '') AS subject_code
            FROM campus_rooms r
            JOIN campus_floors f ON f.id = r.floor_id
            LEFT JOIN campus_sections s ON s.id = r.section_id
            LEFT JOIN subjects sub ON sub.id = r.assigned_subject_id
            WHERE r.institution_id = ?
            ORDER BY f.floor_number, r.room_number
        ''', (institution_id,))
        return [dict(row) for row in cursor.fetchall()]


def import_campus_rooms_from_rows(rows, institution_id):
    if not rows:
        return {'status': 'error', 'message': 'No rows to import'}

    created = 0
    skipped = []

    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        floor_cache = {}
        section_cache = {}
        subject_cache = {}

        def _get_or_create_floor(floor_number, label):
            key = int(floor_number)
            if key in floor_cache:
                if label and not floor_cache[key]['label'] and label:
                    cursor.execute('UPDATE campus_floors SET label = ? WHERE id = ? AND institution_id = ?', (label, floor_cache[key]['id'], institution_id))
                    floor_cache[key]['label'] = label
                return floor_cache[key]['id']
            cursor.execute('SELECT id, COALESCE(label, "") AS label FROM campus_floors WHERE institution_id = ? AND floor_number = ?', (institution_id, key))
            existing = cursor.fetchone()
            if existing:
                if label and not existing['label']:
                    cursor.execute('UPDATE campus_floors SET label = ? WHERE id = ? AND institution_id = ?', (label, existing['id'], institution_id))
                floor_cache[key] = {'id': existing['id'], 'label': label or existing['label']}
                return existing['id']
            cursor.execute('INSERT INTO campus_floors (institution_id, floor_number, label) VALUES (?, ?, ?)', (institution_id, key, label or None))
            floor_id = cursor.lastrowid
            floor_cache[key] = {'id': floor_id, 'label': label or ''}
            return floor_id

        def _get_or_create_section(floor_id, name):
            if not name:
                return None
            key = (floor_id, name.lower())
            if key in section_cache:
                return section_cache[key]
            cursor.execute('''
                SELECT id FROM campus_sections
                WHERE institution_id = ? AND floor_id = ? AND LOWER(name) = LOWER(?)
            ''', (institution_id, floor_id, name))
            row = cursor.fetchone()
            if row:
                section_cache[key] = row['id']
                return row['id']
            cursor.execute('INSERT INTO campus_sections (institution_id, floor_id, name) VALUES (?, ?, ?)', (institution_id, floor_id, name))
            section_id = cursor.lastrowid
            section_cache[key] = section_id
            return section_id

        def _resolve_subject(code):
            if not code:
                return None
            lookup = code.strip().lower()
            if lookup in subject_cache:
                return subject_cache[lookup]
            cursor.execute('SELECT id FROM subjects WHERE institution_id = ? AND LOWER(subject_id) = ?', (institution_id, lookup))
            row = cursor.fetchone()
            subject_cache[lookup] = row['id'] if row else None
            return subject_cache[lookup]

        for index, raw in enumerate(rows, start=2):  # header is line 1
            try:
                room_number = (raw.get('room_number') or '').strip()
                if not room_number:
                    skipped.append({'line': index, 'reason': 'Missing room_number'})
                    continue
                floor_number_value = raw.get('floor_number')
                if floor_number_value in (None, ''):
                    skipped.append({'line': index, 'reason': 'Missing floor_number'})
                    continue
                floor_number = int(str(floor_number_value).strip())
            except ValueError:
                skipped.append({'line': index, 'reason': 'Invalid floor_number'})
                continue

            floor_label = (raw.get('floor_label') or '').strip()
            section_name = (raw.get('section_name') or '').strip()
            room_type = (raw.get('room_type') or 'classroom').strip().lower()
            if room_type not in ('classroom', 'lab', 'custom'):
                skipped.append({'line': index, 'reason': 'Invalid room_type'})
                continue
            capacity_value = raw.get('capacity')
            try:
                capacity = int(str(capacity_value).strip()) if capacity_value not in (None, '') else 0
            except ValueError:
                skipped.append({'line': index, 'reason': 'Invalid capacity'})
                continue

            subject_code = (raw.get('subject_code') or '').strip()
            custom_title = (raw.get('custom_title') or '').strip()
            custom_function = (raw.get('custom_function') or '').strip()

            floor_id = _get_or_create_floor(floor_number, floor_label)
            section_id = _get_or_create_section(floor_id, section_name) if section_name else None
            subject_id = _resolve_subject(subject_code)

            cursor.execute('''
                SELECT id FROM campus_rooms
                WHERE institution_id = ? AND floor_id = ? AND room_number = ?
            ''', (institution_id, floor_id, room_number))
            if cursor.fetchone():
                skipped.append({'line': index, 'reason': 'Duplicate room'})
                continue

            cursor.execute('''
                INSERT INTO campus_rooms (institution_id, floor_id, section_id, room_number, room_type, capacity,
                                          assigned_subject_id, custom_title, custom_function)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                institution_id,
                floor_id,
                section_id,
                room_number,
                room_type,
                capacity,
                subject_id,
                custom_title if room_type == 'custom' else '',
                custom_function if room_type == 'custom' else ''
            ))
            created += 1
        conn.commit()

    status = 'success' if created > 0 else 'warning'
    response = {
        'status': status,
        'created': created,
        'skipped': len(skipped)
    }
    if skipped:
        response['details'] = skipped[:10]
    return response


def create_campus_room(room_number, room_type, floor_id, institution_id, section_id=None,
                       capacity=None, subject_id=None, custom_title=None, custom_function=None):
    if not room_number or not room_type or floor_id is None:
        return {'status': 'error', 'message': 'Missing room information'}
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM campus_floors WHERE id = ? AND institution_id = ?', (floor_id, institution_id))
        if not cursor.fetchone():
            return {'status': 'error', 'message': 'Floor not found'}
        if section_id:
            cursor.execute('''
                SELECT id FROM campus_sections WHERE id = ? AND floor_id = ? AND institution_id = ?
            ''', (section_id, floor_id, institution_id))
            if not cursor.fetchone():
                return {'status': 'error', 'message': 'Section not found on floor'}
        try:
            cursor.execute('''
                INSERT INTO campus_rooms (institution_id, floor_id, section_id, room_number, room_type, capacity, assigned_subject_id, custom_title, custom_function)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (institution_id, floor_id, section_id, room_number.strip(), room_type, capacity or 0,
                  subject_id if subject_id else None, custom_title or '', custom_function or ''))
            conn.commit()
            return {'status': 'success', 'room_id': cursor.lastrowid}
        except Exception as exc:
            return {'status': 'error', 'message': str(exc)}


def update_campus_room(room_id, institution_id, **fields):
    allowed = {
        'room_number', 'capacity', 'section_id', 'assigned_subject_id',
        'custom_title', 'custom_function', 'room_type'
    }
    updates = []
    params = []
    room_type_changed = False
    new_room_type = None
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, floor_id, room_type FROM campus_rooms WHERE id = ? AND institution_id = ?', (room_id, institution_id))
        row = cursor.fetchone()
        if not row:
            return {'status': 'error', 'message': 'Room not found'}
        floor_id = row['floor_id']
        current_type = row['room_type']
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key == 'section_id':
                if value in (None, ''):
                    updates.append('section_id = NULL')
                else:
                    cursor.execute('''
                        SELECT id FROM campus_sections WHERE id = ? AND floor_id = ? AND institution_id = ?
                    ''', (int(value), floor_id, institution_id))
                    if not cursor.fetchone():
                        return {'status': 'error', 'message': 'Section not found on this floor'}
                    updates.append('section_id = ?')
                    params.append(int(value))
            elif key == 'assigned_subject_id':
                if value in (None, '', 0):
                    updates.append('assigned_subject_id = NULL')
                else:
                    updates.append('assigned_subject_id = ?')
                    params.append(int(value))
            elif key == 'capacity':
                updates.append('capacity = ?')
                params.append(int(value) if value not in (None, '') else 0)
            elif key == 'room_type':
                if not value:
                    return {'status': 'error', 'message': 'Room type is required'}
                normalized = value.strip().lower()
                if normalized not in ('classroom', 'lab', 'custom'):
                    return {'status': 'error', 'message': 'Invalid room type'}
                updates.append('room_type = ?')
                params.append(normalized)
                if normalized != current_type:
                    room_type_changed = True
                    new_room_type = normalized
            else:
                updates.append(f'{key} = ?')
                params.append(value.strip() if isinstance(value, str) else value)
        if not updates:
            return {'status': 'success'}
        params.extend([room_id, institution_id])
        try:
            cursor.execute(f'''
                UPDATE campus_rooms SET {', '.join(updates)}
                WHERE id = ? AND institution_id = ?
            ''', tuple(params))
            detached = 0
            if room_type_changed:
                detached = _clear_home_room_assignments([room_id], cursor, institution_id)
            conn.commit()
            response = {'status': 'success'}
            if room_type_changed:
                response['detached_classes'] = detached
                response['room_type'] = new_room_type
            return response
        except Exception as exc:
            return {'status': 'error', 'message': str(exc)}


def _clear_home_room_assignments(room_ids, cursor, institution_id):
    if not room_ids:
        return 0
    placeholders = ','.join(['?'] * len(room_ids))
    params = [institution_id] + room_ids
    cursor.execute(f'''
        UPDATE classes
        SET home_room_id = NULL, room_number = ''
        WHERE institution_id = ? AND home_room_id IN ({placeholders})
    ''', params)
    return cursor.rowcount


def delete_campus_room(room_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM campus_rooms WHERE id = ? AND institution_id = ?', (room_id, institution_id))
        if not cursor.fetchone():
            return {'status': 'error', 'message': 'Room not found'}
        _clear_home_room_assignments([room_id], cursor, institution_id)
        cursor.execute('DELETE FROM campus_rooms WHERE id = ? AND institution_id = ?', (room_id, institution_id))
        conn.commit()
    return {'status': 'success'}


def delete_campus_section(section_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM campus_sections WHERE id = ? AND institution_id = ?', (section_id, institution_id))
        if not cursor.fetchone():
            return {'status': 'error', 'message': 'Section not found'}
        cursor.execute('SELECT id FROM campus_rooms WHERE section_id = ? AND institution_id = ?', (section_id, institution_id))
        room_ids = [row['id'] for row in cursor.fetchall()]
        _clear_home_room_assignments(room_ids, cursor, institution_id)
        cursor.execute('DELETE FROM campus_rooms WHERE section_id = ? AND institution_id = ?', (section_id, institution_id))
        cursor.execute('DELETE FROM campus_sections WHERE id = ? AND institution_id = ?', (section_id, institution_id))
        conn.commit()
    return {'status': 'success'}


def delete_campus_floor(floor_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM campus_floors WHERE id = ? AND institution_id = ?', (floor_id, institution_id))
        if not cursor.fetchone():
            return {'status': 'error', 'message': 'Floor not found'}
        cursor.execute('SELECT id FROM campus_rooms WHERE floor_id = ? AND institution_id = ?', (floor_id, institution_id))
        room_ids = [row['id'] for row in cursor.fetchall()]
        _clear_home_room_assignments(room_ids, cursor, institution_id)
        cursor.execute('DELETE FROM campus_rooms WHERE floor_id = ? AND institution_id = ?', (floor_id, institution_id))
        cursor.execute('DELETE FROM campus_sections WHERE floor_id = ? AND institution_id = ?', (floor_id, institution_id))
        cursor.execute('DELETE FROM campus_floors WHERE id = ? AND institution_id = ?', (floor_id, institution_id))
        conn.commit()
    return {'status': 'success'}


def reset_campus_layout(institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM campus_rooms WHERE institution_id = ?', (institution_id,))
        room_ids = [row['id'] for row in cursor.fetchall()]
        _clear_home_room_assignments(room_ids, cursor, institution_id)
        cursor.execute('DELETE FROM campus_rooms WHERE institution_id = ?', (institution_id,))
        cursor.execute('DELETE FROM campus_sections WHERE institution_id = ?', (institution_id,))
        cursor.execute('DELETE FROM campus_floors WHERE institution_id = ?', (institution_id,))
        conn.commit()
    return {'status': 'success', 'message': 'Campus layout cleared'}


def get_floor_summary(floor_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, floor_number, COALESCE(label, "") AS label FROM campus_floors WHERE id = ? AND institution_id = ?', (floor_id, institution_id))
        floor = cursor.fetchone()
        if not floor:
            return None
        cursor.execute('SELECT COUNT(*) FROM campus_sections WHERE floor_id = ? AND institution_id = ?', (floor_id, institution_id))
        section_count = cursor.fetchone()[0]
        cursor.execute('SELECT id, room_type FROM campus_rooms WHERE floor_id = ? AND institution_id = ?', (floor_id, institution_id))
        rooms = cursor.fetchall()
        room_ids = [row['id'] for row in rooms]
        room_count = len(room_ids)
        counts_by_type = {'classroom': 0, 'lab': 0, 'custom': 0}
        for row in rooms:
            counts_by_type[row['room_type']] = counts_by_type.get(row['room_type'], 0) + 1
        class_count = 0
        if room_ids:
            placeholders = ','.join(['?'] * len(room_ids))
            params = [institution_id] + room_ids
            cursor.execute(f'''
                SELECT COUNT(*) FROM classes
                WHERE institution_id = ? AND home_room_id IN ({placeholders})
            ''', params)
            class_count = cursor.fetchone()[0]
        return {
            'id': floor['id'],
            'label': floor['label'],
            'floor_number': floor['floor_number'],
            'section_count': section_count,
            'room_count': room_count,
            'class_count': class_count,
            'rooms_by_type': counts_by_type
        }


def get_section_summary(section_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, floor_id FROM campus_sections WHERE id = ? AND institution_id = ?', (section_id, institution_id))
        section = cursor.fetchone()
        if not section:
            return None
        cursor.execute('SELECT id, room_type FROM campus_rooms WHERE section_id = ? AND institution_id = ?', (section_id, institution_id))
        rooms = cursor.fetchall()
        room_ids = [row['id'] for row in rooms]
        counts_by_type = {'classroom': 0, 'lab': 0, 'custom': 0}
        for row in rooms:
            counts_by_type[row['room_type']] = counts_by_type.get(row['room_type'], 0) + 1
        class_count = 0
        if room_ids:
            placeholders = ','.join(['?'] * len(room_ids))
            params = [institution_id] + room_ids
            cursor.execute(f'''
                SELECT COUNT(*) FROM classes
                WHERE institution_id = ? AND home_room_id IN ({placeholders})
            ''', params)
            class_count = cursor.fetchone()[0]
        return {
            'id': section['id'],
            'name': section['name'],
            'floor_id': section['floor_id'],
            'room_count': len(room_ids),
            'class_count': class_count,
            'rooms_by_type': counts_by_type
        }


def get_room_summary(room_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
                         SELECT r.id, r.room_number, r.room_type, r.capacity,
                             r.floor_id, r.section_id, r.assigned_subject_id,
                             r.custom_title, r.custom_function,
                   f.floor_number, COALESCE(f.label, '') AS floor_label,
                   s.name AS section_name
            FROM campus_rooms r
            JOIN campus_floors f ON r.floor_id = f.id
            LEFT JOIN campus_sections s ON r.section_id = s.id
            WHERE r.id = ? AND r.institution_id = ?
        ''', (room_id, institution_id))
        room = cursor.fetchone()
        if not room:
            return None
        cursor.execute('''
            SELECT id, class_name, section, semester_id, program_id
            FROM classes
            WHERE institution_id = ? AND home_room_id = ?
        ''', (institution_id, room_id))
        classes = [dict(row) for row in cursor.fetchall()]
        return {
            'room': dict(room),
            'classes': classes,
            'class_count': len(classes)
        }

def get_campus_rooms(institution_id, room_type=None):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        query = '''
            SELECT r.id, r.room_number, r.room_type, r.capacity, r.floor_id, r.section_id,
                   COALESCE(r.custom_title, '') AS custom_title,
                   COALESCE(r.custom_function, '') AS custom_function,
                   r.assigned_subject_id,
                   f.floor_number,
                   COALESCE(f.label, '') AS floor_label,
                   s.name AS section_name,
                   subj.name AS subject_name
            FROM campus_rooms r
            JOIN campus_floors f ON r.floor_id = f.id
            LEFT JOIN campus_sections s ON r.section_id = s.id
            LEFT JOIN subjects subj ON subj.id = r.assigned_subject_id
            WHERE r.institution_id = ?
        '''
        params = [institution_id]
        if room_type:
            query += ' AND r.room_type = ?'
            params.append(room_type)
        query += ' ORDER BY f.floor_number, r.room_number'
        cursor.execute(query, tuple(params))
        return [dict(row) for row in cursor.fetchall()]


def get_campus_layout(institution_id):
    floors = get_campus_floors(institution_id)
    sections = get_campus_sections(institution_id)
    rooms = get_campus_rooms(institution_id)
    section_map = {}
    for section in sections:
        section_map.setdefault(section['floor_id'], []).append(section)

    room_map = {}
    for room in rooms:
        room_map.setdefault(room['floor_id'], []).append(room)

    layout = []
    for floor in floors:
        layout.append({
            'id': floor['id'],
            'floor_number': floor['floor_number'],
            'label': floor['label'],
            'sections': section_map.get(floor['id'], []),
            'rooms': room_map.get(floor['id'], [])
        })
    return layout

def assign_home_room_to_class(class_id, room_id, institution_id):
    room = get_campus_room_by_id(room_id, institution_id)
    if not room:
        return {'status': 'error', 'message': 'Home room not found'}
    conflict = get_class_using_home_room(room_id, institution_id, exclude_class_id=class_id)
    if conflict:
        return {
            'status': 'error',
            'message': f"Home room already assigned to {conflict['class_name']} ({conflict['section']})"
        }
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE classes SET home_room_id = ?, room_number = ?
            WHERE id = ? AND institution_id = ?
        ''', (room_id, room['room_number'], class_id, institution_id))
        conn.commit()
        if cursor.rowcount == 0:
            return {'status': 'error', 'message': 'Class not found'}
    return {'status': 'success'}

# ============ STUDENT MANAGEMENT ============

def create_student(student_id, first_name, middle_name, last_name, email, roll_no, phone_number, gender, password, program_id, semester_id, class_id, institution_id):
    """Create a new student"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        try:
            if class_id:
                cursor.execute('''
                    SELECT id FROM classes
                    WHERE id = ? AND institution_id = ?
                ''', (class_id, institution_id))
                class_row = cursor.fetchone()
                if not class_row:
                    return {'status': 'error', 'message': 'Class not found'}
                cursor.execute('''
                    SELECT COUNT(*) FROM students
                    WHERE class_id = ? AND institution_id = ?
                ''', (class_id, institution_id))
                current_total = cursor.fetchone()[0]
                if current_total >= MAX_CLASS_SIZE:
                    return {
                        'status': 'error',
                        'message': f'Class capacity of {MAX_CLASS_SIZE} students reached'
                    }

            cursor.execute('''
                INSERT INTO students (student_id, first_name, middle_name, last_name, email, roll_no, phone_number, gender, password, 
                                     program_id, semester_id, class_id, institution_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, first_name, middle_name or '', last_name, email, roll_no or '', phone_number or '', gender or '', password, 
                  program_id, semester_id, class_id, institution_id))
            if class_id:
                _refresh_class_enrollment_metadata(cursor, class_id, institution_id)
            conn.commit()
            return {'status': 'success', 'message': f'Student {first_name} {last_name} created'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

def get_all_students_flat(institution_id):
    """Return every student with associated class and program context."""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                st.id,
                st.student_id,
                st.first_name,
                st.middle_name,
                st.last_name,
                st.email,
                st.phone_number,
                st.gender,
                st.roll_no,
                st.program_id,
                st.semester_id,
                st.class_id,
                st.gpa,
                c.class_name,
                c.class_id AS class_code,
                c.section,
                sem.semester_number,
                sem.semester_id AS semester_code,
                prog.program_name,
                prog.program_id AS program_code
            FROM students st
            LEFT JOIN classes c ON st.class_id = c.id
            LEFT JOIN semesters sem ON st.semester_id = sem.id
            LEFT JOIN programs prog ON st.program_id = prog.id
            WHERE st.institution_id = ?
            ORDER BY prog.program_name, sem.semester_number, c.class_name, st.last_name, st.first_name
        ''', (institution_id,))
        rows = []
        for row in cursor.fetchall():
            record = dict(row)
            full_name_parts = [record.get('first_name'), record.get('middle_name'), record.get('last_name')]
            record['full_name'] = ' '.join(part.strip() for part in full_name_parts if part)
            rows.append(record)
        return rows

def get_students_by_class(class_id, institution_id):
    """Get all students in a class"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, student_id, first_name, middle_name, last_name, email, roll_no
            FROM students
            WHERE class_id = ? AND institution_id = ?
            ORDER BY last_name
        ''', (class_id, institution_id))
        return [dict(row) for row in cursor.fetchall()]

def get_student_by_id(student_id, institution_id):
    """Get a single student by ID"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, student_id, first_name, middle_name, last_name, email, roll_no
            FROM students
            WHERE id = ? AND institution_id = ?
        ''', (student_id, institution_id))
        row = cursor.fetchone()
        return dict(row) if row else None

def update_student(student_id, student_id_str, first_name, middle_name, last_name, email, roll_no, phone_number, password_update, institution_id):
    """Update student information"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        try:
            if password_update:
                # Update with password
                cursor.execute('''
                    UPDATE students
                    SET student_id = ?, first_name = ?, middle_name = ?, last_name = ?, email = ?, roll_no = ?, phone_number = ?, password = ?
                    WHERE id = ? AND institution_id = ?
                ''', (student_id_str, first_name, middle_name, last_name, email, roll_no or '', phone_number or '', password_update, student_id, institution_id))
            else:
                # Update without password
                cursor.execute('''
                    UPDATE students
                    SET student_id = ?, first_name = ?, middle_name = ?, last_name = ?, email = ?, roll_no = ?, phone_number = ?
                    WHERE id = ? AND institution_id = ?
                ''', (student_id_str, first_name, middle_name, last_name, email, roll_no or '', phone_number or '', student_id, institution_id))
            conn.commit()
            return {'status': 'success', 'message': 'Student updated successfully'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

# ============ FACULTY MANAGEMENT ============

def create_faculty(faculty_id, first_name, middle_name, last_name, email, phone_number,
                   gender, password, role, institution_id, extra_notes='',
                   time_preference=None,
                   is_teaching_staff=False, majors=None, proficiency_score=None,
                   experience_years=None, value_score=None):
    """Create a new faculty member"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        try:
            majors_payload = []
            if isinstance(majors, str):
                majors_payload = [segment.strip() for segment in majors.split(',') if segment.strip()]
            elif isinstance(majors, (list, tuple, set)):
                majors_payload = [str(segment).strip() for segment in majors if str(segment).strip()]
            majors_serialized = ', '.join(majors_payload) if majors_payload else None

            cursor.execute('''
                INSERT INTO faculty (
                    faculty_id, first_name, middle_name, last_name, email, phone_number,
                    gender, password, role, extra_notes, institution_id,
                    time_preference,
                    is_teaching_staff, majors, proficiency_score, experience_years, value_score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                faculty_id,
                first_name,
                middle_name or '',
                last_name,
                email,
                phone_number or '',
                gender or '',
                password,
                role or 'faculty',
                extra_notes or '',
                institution_id,
                (time_preference or '').strip() or None,
                1 if is_teaching_staff else 0,
                majors_serialized,
                proficiency_score if proficiency_score is not None else None,
                experience_years if experience_years is not None else None,
                value_score if value_score is not None else None
            ))
            conn.commit()
            return {'status': 'success', 'message': f'Faculty {first_name} {last_name} created', 'faculty_id': faculty_id}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

def get_all_faculty(institution_id):
    """Get all faculty members"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
                 SELECT id, faculty_id, first_name, middle_name, last_name, email, phone_number, role,
                     time_preference,
                     is_teaching_staff, majors, proficiency_score, experience_years, value_score
            FROM faculty
            WHERE institution_id = ?
            ORDER BY last_name
        ''', (institution_id,))
        return [dict(row) for row in cursor.fetchall()]

def assign_faculty_to_class(faculty_id, class_id, institution_id, subject='', subject_ref_id=None):
    """Assign faculty to a class"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        try:
            ref_id = int(subject_ref_id) if subject_ref_id else None
            normalized_subject_name = (subject or '').strip()

            if ref_id:
                cursor.execute('''
                    SELECT faculty_id FROM faculty_classes
                    WHERE class_id = ? AND subject_ref_id = ? AND institution_id = ?
                ''', (class_id, ref_id, institution_id))
                subject_owner = cursor.fetchone()
                if subject_owner and subject_owner['faculty_id'] != faculty_id:
                    return {
                        'status': 'error',
                        'message': 'Another faculty member already owns this subject for the class'
                    }
            elif normalized_subject_name:
                cursor.execute('''
                    SELECT faculty_id FROM faculty_classes
                    WHERE class_id = ?
                      AND institution_id = ?
                      AND subject_ref_id IS NULL
                      AND LOWER(COALESCE(subject, '')) = LOWER(?)
                ''', (class_id, institution_id, normalized_subject_name))
                subject_owner = cursor.fetchone()
                if subject_owner and subject_owner['faculty_id'] != faculty_id:
                    return {
                        'status': 'error',
                        'message': 'Class already has a faculty assigned for this subject label'
                    }

            cursor.execute('''
                INSERT INTO faculty_classes (faculty_id, class_id, subject, subject_ref_id, institution_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(class_id, subject_ref_id, institution_id) DO UPDATE SET
                    faculty_id=excluded.faculty_id,
                    subject=excluded.subject
            ''', (faculty_id, class_id, subject or '', ref_id, institution_id))
            conn.commit()
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    parallel_status = get_parallel_practical_status(class_id, institution_id)
    response = {'status': 'success', 'message': 'Faculty assigned to class'}
    if parallel_status:
        response['parallel_practical_status'] = parallel_status
    return response

def assign_faculty_to_subjects(faculty_identifier, subject_ids, institution_id):
    """Assign a faculty member to the given subject database IDs."""
    subject_ids = subject_ids or []
    cleaned_subject_ids = []
    for subject_id in subject_ids:
        try:
            cleaned_subject_ids.append(int(subject_id))
        except (TypeError, ValueError):
            continue
    cleaned_subject_ids = list(dict.fromkeys(cleaned_subject_ids))

    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()

        faculty_db_id = None
        try:
            faculty_db_id = int(faculty_identifier)
            cursor.execute('SELECT id FROM faculty WHERE id = ? AND institution_id = ?', (faculty_db_id, institution_id))
            if not cursor.fetchone():
                faculty_db_id = None
        except (TypeError, ValueError):
            faculty_db_id = None

        if faculty_db_id is None:
            cursor.execute('SELECT id FROM faculty WHERE faculty_id = ? AND institution_id = ?', (str(faculty_identifier), institution_id))
            row = cursor.fetchone()
            if row:
                faculty_db_id = row['id']

        if faculty_db_id is None:
            return {'status': 'error', 'message': 'Faculty not found'}

        if not cleaned_subject_ids:
            cursor.execute('DELETE FROM faculty_subjects WHERE faculty_id = ? AND institution_id = ?', (faculty_db_id, institution_id))
            removed = cursor.rowcount
            conn.commit()
            return {'status': 'success', 'assigned_subjects': 0, 'removed': removed}

        placeholders = ','.join(['?'] * len(cleaned_subject_ids))
        cursor.execute(
            f'''SELECT id FROM subjects WHERE institution_id = ? AND id IN ({placeholders})''',
            [institution_id, *cleaned_subject_ids]
        )
        valid_ids = {row['id'] for row in cursor.fetchall()}
        if not valid_ids:
            return {'status': 'error', 'message': 'No valid subjects provided'}

        cursor.execute('DELETE FROM faculty_subjects WHERE faculty_id = ? AND institution_id = ?', (faculty_db_id, institution_id))
        removed = cursor.rowcount
        for subject_id in valid_ids:
            cursor.execute('''
                INSERT OR IGNORE INTO faculty_subjects (faculty_id, subject_id, institution_id)
                VALUES (?, ?, ?)
            ''', (faculty_db_id, subject_id, institution_id))
        conn.commit()
        return {
            'status': 'success',
            'assigned_subjects': len(valid_ids),
            'removed': removed
        }


def auto_assign_subject_faculty(institution_id, targeting_mode='strict'):
    """Automatically link faculty to subjects based on requirement tiers."""
    mode = (targeting_mode or 'strict').lower()
    targeting_profiles = {
        'strict': {'prof_margin': 0, 'exp_margin': 0},
        'moderate': {'prof_margin': 10, 'exp_margin': 2},
        'loose': {'prof_margin': 20, 'exp_margin': 4}
    }
    profile = targeting_profiles.get(mode, targeting_profiles['strict'])

    def _normalize_major_list(raw_value):
        if not raw_value:
            return []
        if isinstance(raw_value, (list, tuple, set)):
            iterable = raw_value
        else:
            iterable = str(raw_value).split(',')
        return [segment.strip().lower() for segment in iterable if segment and segment.strip()]

    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, subject_id, name, subject_type, semester_id,
                   required_majors, min_proficiency, min_experience
            FROM subjects
            WHERE institution_id = ?
        ''', (institution_id,))
        subject_rows = cursor.fetchall()

        subject_semester_map = {}
        for row in subject_rows:
            subject_semester_map[row['id']] = set()
            if row['semester_id']:
                subject_semester_map[row['id']].add(row['semester_id'])

        cursor.execute('''
            SELECT subject_id, semester_id
            FROM subject_semesters
            WHERE institution_id = ?
        ''', (institution_id,))
        for link in cursor.fetchall():
            subj_id = link['subject_id']
            sem_id = link['semester_id']
            if subj_id and sem_id:
                subject_semester_map.setdefault(subj_id, set()).add(sem_id)

        cursor.execute('''
            SELECT id, class_id, class_name, semester_id
            FROM classes
            WHERE institution_id = ?
        ''', (institution_id,))
        classes_by_semester = {}
        for class_row in cursor.fetchall():
            sem_id = class_row['semester_id']
            if not sem_id:
                continue
            classes_by_semester.setdefault(sem_id, []).append(dict(class_row))

        cursor.execute('''
            SELECT id, faculty_id, first_name, last_name, majors,
                   proficiency_score, experience_years, value_score, is_teaching_staff
            FROM faculty
            WHERE institution_id = ?
        ''', (institution_id,))
        faculty_rows = cursor.fetchall()

        if not subject_rows:
            return {'status': 'error', 'message': 'No subjects available to assign.'}

        teaching_faculty = []
        for row in faculty_rows:
            if not row['is_teaching_staff']:
                continue
            majors_set = set(_normalize_major_list(row['majors']))
            display_name = f"{(row['first_name'] or '').strip()} {(row['last_name'] or '').strip()}".strip()
            teaching_faculty.append({
                'db_id': row['id'],
                'faculty_code': row['faculty_id'],
                'name': display_name or row['faculty_id'],
                'majors_set': majors_set,
                'proficiency': row['proficiency_score'] or 0,
                'experience': row['experience_years'] or 0,
                'value': row['value_score'] or 0
            })

        faculty_lookup = {fac['db_id']: fac for fac in teaching_faculty}

        if not teaching_faculty:
            return {'status': 'error', 'message': 'No teaching staff available for assignments.'}

        def _pick_faculty(subject_payload):
            req_majors = subject_payload['majors']
            min_prof = subject_payload['min_prof']
            min_exp = subject_payload['min_exp']

            prof_margin = profile['prof_margin']
            if min_prof >= 80:
                prof_margin = min(prof_margin, 5)
            exp_margin = profile['exp_margin']
            relaxed_prof_threshold = max(0, min_prof - prof_margin)
            relaxed_exp_threshold = max(0, min_exp - exp_margin)

            candidate_pool = [fac for fac in teaching_faculty if not req_majors or fac['majors_set'].intersection(req_majors)]
            major_relaxed = False
            if not candidate_pool:
                candidate_pool = teaching_faculty[:]
                major_relaxed = True

            def _score_key(fac):
                return (fac['value'], fac['proficiency'], fac['experience'])

            def _sorted_candidates(pool):
                return sorted(pool, key=_score_key, reverse=True)

            primary = [fac for fac in candidate_pool if fac['proficiency'] >= min_prof and fac['experience'] >= min_exp]
            if primary:
                ranked = _sorted_candidates(primary)
                tier = 'ideal' if not major_relaxed else 'relaxed'
                return ranked[0], tier, ranked

            relaxed = [
                fac for fac in candidate_pool
                if fac['proficiency'] >= relaxed_prof_threshold and fac['experience'] >= relaxed_exp_threshold
            ]
            if relaxed:
                ranked = _sorted_candidates(relaxed)
                return ranked[0], 'relaxed', ranked

            def _gap_metric(fac):
                prof_gap = max(0, min_prof - fac['proficiency'])
                exp_gap = max(0, min_exp - fac['experience'])
                return (prof_gap * 2) + exp_gap

            fallback_sorted = sorted(
                candidate_pool,
                key=lambda fac: (_gap_metric(fac), -fac['value'], -fac['proficiency'], -fac['experience'])
            )
            if fallback_sorted:
                return fallback_sorted[0], 'fallback', fallback_sorted
            return None, None, []

        total_considered = 0
        perfect_matches = relaxed_matches = fallback_matches = 0
        assignments = []
        unmatched_subjects = []

        for row in subject_rows:
            if (row['subject_type'] or '').lower() == 'student':
                continue
            total_considered += 1
            subject_majors = set(_normalize_major_list(_deserialize_list(row['required_majors'])))
            min_prof = row['min_proficiency'] if row['min_proficiency'] is not None else 0
            min_exp = row['min_experience'] if row['min_experience'] is not None else 0
            payload = {
                'id': row['id'],
                'code': row['subject_id'],
                'name': row['name'] or row['subject_id'],
                'majors': subject_majors,
                'min_prof': max(0, min_prof),
                'min_exp': max(0, min_exp)
            }
            faculty_pick, tier, candidate_pool = _pick_faculty(payload)
            if faculty_pick and faculty_pick.get('db_id'):
                semester_ids = subject_semester_map.get(payload['id'], set())
                assignments.append({
                    'subject_id': payload['id'],
                    'subject_label': payload['code'],
                    'subject_name': payload['name'],
                    'faculty_db_id': faculty_pick['db_id'],
                    'faculty_code': faculty_pick['faculty_code'],
                    'faculty_name': faculty_pick['name'],
                    'tier': tier or 'fallback',
                    'semester_ids': sorted(semester_ids),
                    'candidate_pool': (candidate_pool[:8] if candidate_pool else [faculty_pick])
                })
                if tier == 'ideal':
                    perfect_matches += 1
                elif tier == 'relaxed':
                    relaxed_matches += 1
                else:
                    fallback_matches += 1
            else:
                unmatched_subjects.append(payload['name'])

        for mapping in assignments:
            cursor.execute(
                'DELETE FROM faculty_subjects WHERE subject_id = ? AND institution_id = ?',
                (mapping['subject_id'], institution_id)
            )
            cursor.execute('''
                INSERT OR IGNORE INTO faculty_subjects (faculty_id, subject_id, institution_id)
                VALUES (?, ?, ?)
            ''', (mapping['faculty_db_id'], mapping['subject_id'], institution_id))
        class_assignments = 0
        subjects_missing_classes = 0
        faculty_load = defaultdict(int)
        for mapping in assignments:
            semester_ids = mapping.get('semester_ids') or []
            target_classes = []
            for sem_id in semester_ids:
                target_classes.extend(classes_by_semester.get(sem_id, []))
            if not target_classes:
                subjects_missing_classes += 1
                continue

            unique_classes = {}
            for class_row in target_classes:
                class_id = class_row.get('id')
                if class_id is None or class_id in unique_classes:
                    continue
                unique_classes[class_id] = class_row

            candidate_pool = mapping.get('candidate_pool') or []
            if not candidate_pool:
                fallback_faculty = faculty_lookup.get(mapping['faculty_db_id'])
                if fallback_faculty:
                    candidate_pool = [fallback_faculty]
            subset_size = max(1, min(len(candidate_pool), 5))
            candidate_subset = candidate_pool[:subset_size]
            candidate_ranks = {fac['db_id']: idx for idx, fac in enumerate(candidate_subset)}

            for class_row in unique_classes.values():
                if not candidate_subset:
                    continue
                selected = min(
                    candidate_subset,
                    key=lambda fac: (faculty_load[fac['db_id']], candidate_ranks.get(fac['db_id'], 0))
                )
                cursor.execute('''
                    DELETE FROM faculty_classes
                    WHERE class_id = ? AND subject_ref_id = ? AND institution_id = ?
                ''', (class_row['id'], mapping['subject_id'], institution_id))
                cursor.execute('''
                    INSERT INTO faculty_classes (faculty_id, class_id, subject, subject_ref_id, institution_id)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(class_id, subject_ref_id, institution_id) DO UPDATE SET
                        faculty_id = excluded.faculty_id,
                        subject = excluded.subject
                ''', (
                    selected['db_id'],
                    class_row['id'],
                    mapping['subject_name'],
                    mapping['subject_id'],
                    institution_id
                ))
                faculty_load[selected['db_id']] += 1
                class_assignments += 1
        conn.commit()

        for mapping in assignments:
            mapping.pop('candidate_pool', None)

        summary = {
            'total_subjects': total_considered,
            'assigned_subjects': len(assignments),
            'perfect_matches': perfect_matches,
            'relaxed_matches': relaxed_matches,
            'fallback_matches': fallback_matches,
            'unmatched_subjects': len(unmatched_subjects),
            'unmatched_subject_names': unmatched_subjects[:5],
            'class_assignments': class_assignments,
            'subjects_missing_classes': subjects_missing_classes
        }

        status_message = 'Hotfix completed.' if assignments else 'No suitable faculty found for current requirements.'
        return {
            'status': 'success',
            'message': status_message,
            'targeting_mode': mode,
            'summary': summary,
            'assignments': assignments
        }


def remove_faculty_subject_assignment(faculty_db_id, subject_db_id, institution_id):
    """Remove a single faculty-subject mapping."""
    try:
        faculty_db_id = int(faculty_db_id)
        subject_db_id = int(subject_db_id)
    except (TypeError, ValueError):
        return False

    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM faculty_subjects
            WHERE faculty_id = ? AND subject_id = ? AND institution_id = ?
        ''', (faculty_db_id, subject_db_id, institution_id))
        conn.commit()
        return cursor.rowcount > 0

def get_faculty_classes(faculty_id, institution_id):
    """Get all classes assigned to a faculty - faculty_id can be TEXT or INTEGER"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        
        # If faculty_id is TEXT, join with faculty table to find the integer ID
        # If it's already an integer, use it directly
        base_query = '''
            SELECT 
                c.id,
                c.class_id,
                c.class_name,
                c.section,
                p.program_name,
                s.semester_number,
                COALESCE((SELECT COUNT(*) FROM students st WHERE st.class_id = c.id AND st.institution_id = c.institution_id), 0) AS student_count,
                fc.id AS class_faculty_id,
                fc.subject,
                fc.subject_ref_id
            FROM faculty_classes fc
            JOIN classes c ON fc.class_id = c.id
            JOIN programs p ON c.program_id = p.id
            JOIN semesters s ON c.semester_id = s.id
            {join_clause}
            WHERE {where_clause} AND fc.institution_id = ?
        '''

        if isinstance(faculty_id, str):
            # TEXT faculty_id (like "FAC001") - need to find the database ID
            query = base_query.format(
                join_clause='JOIN faculty f ON fc.faculty_id = f.id',
                where_clause='f.faculty_id = ?'
            )
            cursor.execute(query, (faculty_id, institution_id))
        else:
            # INTEGER database ID
            query = base_query.format(
                join_clause='',
                where_clause='fc.faculty_id = ?'
            )
            cursor.execute(query, (faculty_id, institution_id))
        
        # Fetch and return results
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_faculty_subjects(faculty_identifier, institution_id):
    """Return all subjects mapped to a faculty member."""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()

        faculty_db_id = None
        try:
            faculty_db_id = int(faculty_identifier)
            cursor.execute('SELECT id FROM faculty WHERE id = ? AND institution_id = ?', (faculty_db_id, institution_id))
            if not cursor.fetchone():
                faculty_db_id = None
        except (TypeError, ValueError):
            faculty_db_id = None

        if faculty_db_id is None:
            cursor.execute('SELECT id FROM faculty WHERE faculty_id = ? AND institution_id = ?', (str(faculty_identifier), institution_id))
            row = cursor.fetchone()
            if row:
                faculty_db_id = row['id']
        if faculty_db_id is None:
            return []

        cursor.execute('''
            SELECT
                fs.id,
                fs.subject_id AS subject_db_id,
                subj.subject_id AS subject_code,
                subj.name,
                subj.subject_type,
                subj.description,
                subj.semester_id,
                subj.teaching_hours,
                subj.delivery_mode,
                (SELECT COUNT(*) FROM subject_resources sr WHERE sr.subject_id = subj.id) AS resource_count,
                sem.semester_number,
                sem.semester_id AS semester_code,
                prog.program_name
            FROM faculty_subjects fs
            JOIN subjects subj ON fs.subject_id = subj.id
            LEFT JOIN semesters sem ON subj.semester_id = sem.id
            LEFT JOIN programs prog ON sem.program_id = prog.id
            WHERE fs.faculty_id = ? AND fs.institution_id = ?
            ORDER BY subj.name
        ''', (faculty_db_id, institution_id))
        rows = [dict(row) for row in cursor.fetchall()]

        subject_ids = [row['subject_db_id'] for row in rows if row.get('subject_db_id')]
        semester_map = _fetch_subject_semester_map(cursor, institution_id, subject_ids)
        fallback_ids = [row['semester_id'] for row in rows if row.get('semester_id')]
        fallback_map = _fetch_semester_metadata(cursor, fallback_ids)
        for row in rows:
            assigned = semester_map.get(row['subject_db_id'])
            if not assigned and row.get('semester_id'):
                fallback = fallback_map.get(row['semester_id'])
                if fallback:
                    assigned = [fallback]
            row['assigned_semesters'] = assigned or []
        return rows

def get_faculty_by_id(faculty_id, institution_id):
    """Get a single faculty member by ID"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
                 SELECT id, faculty_id, first_name, middle_name, last_name, email,
                     phone_number, role, extra_notes, time_preference, is_teaching_staff, majors,
                   proficiency_score, experience_years, value_score
            FROM faculty
            WHERE id = ? AND institution_id = ?
        ''', (faculty_id, institution_id))
        row = cursor.fetchone()
        return dict(row) if row else None

def update_faculty(faculty_id, faculty_id_str, first_name, middle_name, last_name, email,
                   phone_number, role, password_update, institution_id, time_preference=None):
    """Update faculty information"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        try:
            if password_update:
                # Update with password
                cursor.execute('''
                    UPDATE faculty
                    SET faculty_id = ?, first_name = ?, middle_name = ?, last_name = ?, email = ?, phone_number = ?, role = ?, time_preference = ?, password = ?
                    WHERE id = ? AND institution_id = ?
                ''', (faculty_id_str, first_name, middle_name, last_name, email, phone_number or '', role or 'faculty', (time_preference or '').strip() or None, password_update, faculty_id, institution_id))
            else:
                # Update without password
                cursor.execute('''
                    UPDATE faculty
                    SET faculty_id = ?, first_name = ?, middle_name = ?, last_name = ?, email = ?, phone_number = ?, role = ?, time_preference = ?
                    WHERE id = ? AND institution_id = ?
                ''', (faculty_id_str, first_name, middle_name, last_name, email, phone_number or '', role or 'faculty', (time_preference or '').strip() or None, faculty_id, institution_id))
            conn.commit()
            return {'status': 'success', 'message': 'Faculty updated successfully'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}


# ============ SUBJECT MANAGEMENT ============

def get_all_semesters_flat(institution_id):
    """Return all semesters with associated program info"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.id, s.semester_id, s.semester_number, p.program_name, p.program_id
            FROM semesters s
            JOIN programs p ON s.program_id = p.id
            WHERE s.institution_id = ?
            ORDER BY p.program_name, s.semester_number
        ''', (institution_id,))
        return [dict(row) for row in cursor.fetchall()]


def _resolve_student_ids(cursor, student_identifiers, institution_id):
    resolved = []
    missing = []
    if not student_identifiers:
        return resolved, missing
    for identifier in student_identifiers:
        clean_id = identifier.strip()
        if not clean_id:
            continue
        cursor.execute('''
            SELECT id FROM students
            WHERE student_id = ? AND institution_id = ?
        ''', (clean_id, institution_id))
        row = cursor.fetchone()
        if row:
            resolved.append(row['id'])
        else:
            missing.append(clean_id)
    return resolved, missing


def _fetch_subject_semester_map(cursor, institution_id, subject_ids=None):
    """Return mapping of subject_db_id -> list of assigned semester payloads."""
    params = [institution_id]
    query = '''
        SELECT 
            ss.subject_id AS subject_db_id,
            sem.id AS semester_db_id,
            sem.semester_number,
            sem.semester_id AS semester_code,
            prog.program_name
        FROM subject_semesters ss
        JOIN semesters sem ON ss.semester_id = sem.id
        JOIN programs prog ON sem.program_id = prog.id
        WHERE ss.institution_id = ?
    '''
    if subject_ids:
        placeholders = ','.join('?' for _ in subject_ids)
        query += f' AND ss.subject_id IN ({placeholders})'
        params.extend(subject_ids)
    cursor.execute(query, params)
    mapping = {}
    for row in cursor.fetchall():
        payload = {
            'semester_id': row['semester_db_id'],
            'semester_number': row['semester_number'],
            'semester_code': row['semester_code'],
            'program_name': row['program_name']
        }
        mapping.setdefault(row['subject_db_id'], []).append(payload)
    return mapping


def _fetch_semester_metadata(cursor, semester_ids):
    if not semester_ids:
        return {}
    placeholders = ','.join('?' for _ in semester_ids)
    cursor.execute(f'''
        SELECT sem.id, sem.semester_number, sem.semester_id AS semester_code, prog.program_name
        FROM semesters sem
        JOIN programs prog ON sem.program_id = prog.id
        WHERE sem.id IN ({placeholders})
    ''', tuple(semester_ids))
    return {
        row['id']: {
            'semester_id': row['id'],
            'semester_number': row['semester_number'],
            'semester_code': row['semester_code'],
            'program_name': row['program_name']
        }
        for row in cursor.fetchall()
    }


def _serialize_list(values):
    if not values:
        return None
    if isinstance(values, str):
        cleaned = [segment.strip() for segment in values.split(',') if segment.strip()]
        return ', '.join(cleaned) if cleaned else None
    cleaned = [str(segment).strip() for segment in values if str(segment).strip()]
    return ', '.join(cleaned) if cleaned else None


def _deserialize_list(raw_value):
    if not raw_value:
        return []
    return [segment.strip() for segment in str(raw_value).split(',') if segment.strip()]


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
    if text in ('1', 'true', 'yes', 'y', 'on', 'checked'):  # common truthy tokens
        return True
    if text in ('0', 'false', 'no', 'n', 'off', 'unchecked'):  # explicit falsy tokens
        return False
    return None


def _coerce_non_negative_int(value):
    if value in (None, ''):
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def create_subject(subject_id, name, description, subject_type, institution_id, semester_id=None,
                   student_identifiers=None, semester_ids=None, teaching_hours=None, delivery_mode=None,
                   required_majors=None, min_proficiency=None, min_experience=None, min_value=None,
                   has_theory_component=None, has_practical_component=None,
                   theory_hours=None, practical_hours=None, requires_lab=None):
    """Create a new subject and optionally assign students/semesters"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        try:
            hours = 0
            if teaching_hours is not None:
                try:
                    hours = max(0, int(teaching_hours))
                except (TypeError, ValueError):
                    hours = 0
            mode = (delivery_mode or 'theory').lower() if delivery_mode else 'theory'
            if mode not in ('theory', 'practical'):
                mode = 'theory'

            normalized_semester_ids = []
            combined_semesters = []
            if semester_ids and isinstance(semester_ids, (list, tuple)):
                combined_semesters.extend(semester_ids)
            if semester_id is not None:
                combined_semesters.append(semester_id)
            for sem_value in combined_semesters:
                try:
                    sem_int = int(sem_value)
                except (TypeError, ValueError):
                    continue
                if sem_int not in normalized_semester_ids:
                    normalized_semester_ids.append(sem_int)

            primary_semester_id = normalized_semester_ids[0] if normalized_semester_ids else None
            if subject_type == 'semester' and primary_semester_id is None:
                return {'status': 'error', 'message': 'Semester subjects require at least one semester'}

            majors_serialized = _serialize_list(required_majors)

            theory_flag = _parse_bool_flag(has_theory_component)
            practical_flag = _parse_bool_flag(has_practical_component)
            if theory_flag is None and practical_flag is None:
                theory_flag = mode != 'practical'
                practical_flag = mode == 'practical'
            else:
                theory_flag = bool(theory_flag)
                practical_flag = bool(practical_flag)

            if not theory_flag and not practical_flag:
                return {'status': 'error', 'message': 'Select at least one delivery component'}

            theory_hours_value = _coerce_non_negative_int(theory_hours)
            practical_hours_value = _coerce_non_negative_int(practical_hours)
            theory_hours_value = theory_hours_value if theory_hours_value is not None else 0
            practical_hours_value = practical_hours_value if practical_hours_value is not None else 0

            if hours and theory_hours_value == 0 and practical_hours_value == 0:
                if theory_flag and not practical_flag:
                    theory_hours_value = hours
                elif practical_flag and not theory_flag:
                    practical_hours_value = hours
                elif theory_flag and practical_flag:
                    theory_hours_value = hours // 2
                    practical_hours_value = hours - theory_hours_value

            if not theory_flag:
                theory_hours_value = 0
            if not practical_flag:
                practical_hours_value = 0

            total_hours = theory_hours_value + practical_hours_value
            if total_hours == 0 and hours:
                total_hours = hours

            mode = 'practical' if practical_flag else 'theory'
            requires_lab_flag = _parse_bool_flag(requires_lab)
            if requires_lab_flag is None:
                requires_lab_flag = practical_flag
            requires_lab_value = 1 if (practical_flag and requires_lab_flag) else 0

            def _coerce_int(value, minimum=None, maximum=None):
                if value in (None, ''):
                    return None
                try:
                    casted = int(value)
                except (TypeError, ValueError):
                    return None
                if minimum is not None and casted < minimum:
                    casted = minimum
                if maximum is not None and casted > maximum:
                    casted = maximum
                return casted

            min_prof = _coerce_int(min_proficiency, 0, 100)
            min_exp = _coerce_int(min_experience, 0, None)
            min_val = _coerce_int(min_value, 1, 10)

            cursor.execute('''
                INSERT INTO subjects (
                    subject_id, name, description, subject_type, semester_id, institution_id,
                    teaching_hours, delivery_mode, required_majors, min_proficiency, min_experience, min_value,
                    has_theory_component, has_practical_component, theory_hours, practical_hours, requires_lab
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                subject_id,
                name,
                description or '',
                subject_type,
                primary_semester_id,
                institution_id,
                total_hours,
                mode,
                majors_serialized,
                min_prof,
                min_exp,
                min_val,
                1 if theory_flag else 0,
                1 if practical_flag else 0,
                theory_hours_value,
                practical_hours_value,
                requires_lab_value
            ))
            subject_db_id = cursor.lastrowid

            if normalized_semester_ids:
                cursor.executemany('''
                    INSERT OR IGNORE INTO subject_semesters (subject_id, semester_id, institution_id)
                    VALUES (?, ?, ?)
                ''', [(subject_db_id, sem_id, institution_id) for sem_id in normalized_semester_ids])

            resolved_ids, missing = _resolve_student_ids(cursor, student_identifiers or [], institution_id)
            if subject_type == 'student' and resolved_ids:
                cursor.executemany('''
                    INSERT OR IGNORE INTO subject_students (subject_id, student_id, institution_id)
                    VALUES (?, ?, ?)
                ''', [(subject_db_id, sid, institution_id) for sid in resolved_ids])
            conn.commit()
            return {
                'status': 'success',
                'subject_id': subject_id,
                'missing_students': missing
            }
        except Exception as exc:
            conn.rollback()
            return {'status': 'error', 'message': str(exc)}


def delete_subject(subject_db_id, institution_id):
    """Delete subject with all mappings and resources"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT subject_id FROM subjects WHERE id = ? AND institution_id = ?', (subject_db_id, institution_id))
        row = cursor.fetchone()
        if not row:
            return {'status': 'error', 'message': 'Subject not found'}
        subject_code = row['subject_id']
        cursor.execute('DELETE FROM subject_resources WHERE subject_id = ?', (subject_db_id,))
        cursor.execute('DELETE FROM subject_students WHERE subject_id = ?', (subject_db_id,))
        cursor.execute('DELETE FROM subjects WHERE id = ? AND institution_id = ?', (subject_db_id, institution_id))
        conn.commit()

    subject_dir = os.path.join(INSTITUTIONS_DIR, institution_id, 'Subjects', subject_code)
    if os.path.isdir(subject_dir):
        shutil.rmtree(subject_dir, ignore_errors=True)
    return {'status': 'success'}


def get_all_subjects(institution_id):
    """Get all subjects with summary info"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                s.id, s.subject_id, s.name, s.description, s.subject_type, s.semester_id,
                s.teaching_hours, s.delivery_mode,
                s.has_theory_component, s.has_practical_component,
                s.theory_hours, s.practical_hours, s.requires_lab,
                s.required_majors, s.min_proficiency, s.min_experience, s.min_value,
                s.created_at,
                sem.semester_number, sem.semester_id AS semester_code,
                p.program_name,
                (SELECT COUNT(*) FROM subject_students ss WHERE ss.subject_id = s.id) AS student_count,
                (SELECT COUNT(*) FROM subject_resources sr WHERE sr.subject_id = s.id) AS resource_count
            FROM subjects s
            LEFT JOIN semesters sem ON s.semester_id = sem.id
            LEFT JOIN programs p ON sem.program_id = p.id
            WHERE s.institution_id = ?
            ORDER BY s.name
        ''', (institution_id,))
        subjects = [dict(row) for row in cursor.fetchall()]

        subject_ids = [row['id'] for row in subjects]
        semester_map = _fetch_subject_semester_map(cursor, institution_id, subject_ids)
        fallback_ids = [row['semester_id'] for row in subjects if row.get('semester_id')]
        fallback_map = _fetch_semester_metadata(cursor, fallback_ids)

        for subject in subjects:
            assigned = semester_map.get(subject['id'])
            if not assigned and subject.get('semester_id'):
                fallback = fallback_map.get(subject['semester_id'])
                if fallback:
                    assigned = [fallback]
            subject['assigned_semesters'] = assigned or []
            subject['delivery_mode'] = subject.get('delivery_mode') or 'theory'
            subject['required_majors'] = _deserialize_list(subject.get('required_majors'))
            subject['has_theory_component'] = bool(subject.get('has_theory_component'))
            subject['has_practical_component'] = bool(subject.get('has_practical_component'))
            subject['theory_hours'] = subject.get('theory_hours') or 0
            subject['practical_hours'] = subject.get('practical_hours') or 0
            subject['requires_lab'] = bool(subject.get('requires_lab'))

        # Attach student IDs for direct subjects
        for subject in subjects:
            if subject['subject_type'] == 'student':
                cursor.execute('''
                    SELECT st.student_id, st.first_name, st.last_name
                    FROM subject_students ss
                    JOIN students st ON ss.student_id = st.id
                    WHERE ss.subject_id = ?
                ''', (subject['id'],))
                subject['students'] = [dict(r) for r in cursor.fetchall()]
            else:
                subject['students'] = []
        return subjects


def get_subject_by_id(subject_db_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                s.*, 
                s.has_theory_component,
                s.has_practical_component,
                s.theory_hours,
                s.practical_hours,
                s.requires_lab,
                sem.semester_number,
                sem.semester_id AS semester_code,
                p.program_name,
                (SELECT COUNT(*) FROM subject_students ss WHERE ss.subject_id = s.id) AS student_count
            FROM subjects s
            LEFT JOIN semesters sem ON s.semester_id = sem.id
            LEFT JOIN programs p ON sem.program_id = p.id
            WHERE s.id = ? AND s.institution_id = ?
        ''', (subject_db_id, institution_id))
        row = cursor.fetchone()
        if not row:
            return None
        subject = dict(row)
        semester_map = _fetch_subject_semester_map(cursor, institution_id, [subject_db_id])
        assigned = semester_map.get(subject_db_id)
        if not assigned and subject.get('semester_id'):
            fallback = _fetch_semester_metadata(cursor, [subject['semester_id']]).get(subject['semester_id'])
            if fallback:
                assigned = [fallback]
        subject['assigned_semesters'] = assigned or []
        subject['teaching_hours'] = subject.get('teaching_hours') or 0
        subject['delivery_mode'] = subject.get('delivery_mode') or 'theory'
        subject['required_majors'] = _deserialize_list(subject.get('required_majors'))
        subject['has_theory_component'] = bool(subject.get('has_theory_component'))
        subject['has_practical_component'] = bool(subject.get('has_practical_component'))
        subject['theory_hours'] = subject.get('theory_hours') or 0
        subject['practical_hours'] = subject.get('practical_hours') or 0
        subject['requires_lab'] = bool(subject.get('requires_lab'))
        if subject.get('subject_type') == 'student':
            cursor.execute('''
                SELECT st.student_id, st.first_name, st.last_name
                FROM subject_students ss
                JOIN students st ON ss.student_id = st.id
                WHERE ss.subject_id = ?
            ''', (subject_db_id,))
            subject['students'] = [dict(student) for student in cursor.fetchall()]
        else:
            subject['students'] = []
        return subject


def add_subject_resource(subject_id, title, description, file_name, file_path, uploaded_by, institution_id, chapter_id=None):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO subject_resources (subject_id, chapter_id, title, description, file_name, file_path, uploaded_by, institution_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (subject_id, chapter_id, title, description or '', file_name, file_path, uploaded_by, institution_id))
        conn.commit()
        return cursor.lastrowid


def get_subject_resources(subject_id, institution_id, chapter_id=None):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        query = '''
            SELECT id, chapter_id, title, description, file_name, file_path, uploaded_by, uploaded_at
            FROM subject_resources
            WHERE subject_id = ? AND institution_id = ?
        '''
        params = [subject_id, institution_id]
        if chapter_id is not None:
            query += ' AND chapter_id = ?'
            params.append(chapter_id)
        query += ' ORDER BY uploaded_at DESC'
        cursor.execute(query, tuple(params))
        return [dict(row) for row in cursor.fetchall()]


def get_subject_resource(resource_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM subject_resources WHERE id = ? AND institution_id = ?
        ''', (resource_id, institution_id))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_subject_chapters(subject_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                c.id,
                c.subject_id,
                c.chapter_name,
                c.chapter_number,
                c.description,
                c.created_by,
                c.created_at,
                (SELECT COUNT(*) FROM subject_resources sr WHERE sr.chapter_id = c.id) AS resource_count
            FROM subject_chapters c
            WHERE c.subject_id = ? AND c.institution_id = ?
            ORDER BY CASE WHEN c.chapter_number IS NULL THEN 1 ELSE 0 END,
                     c.chapter_number,
                     c.chapter_name
        ''', (subject_id, institution_id))
        return [dict(row) for row in cursor.fetchall()]


def get_subject_chapter(chapter_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM subject_chapters WHERE id = ? AND institution_id = ?
        ''', (chapter_id, institution_id))
        row = cursor.fetchone()
        return dict(row) if row else None


# ============ TIMETABLE MANAGEMENT ============

def create_timetable_run(institution_id, config):
    """Persist a scheduling preference snapshot and mark it pending."""
    config = config or {}
    targeting_mode = (config.get('targeting_mode') or 'strict').lower()
    if targeting_mode not in ('strict', 'moderate', 'loose'):
        targeting_mode = 'strict'

    focus_mode = (config.get('focus_mode') or 'balanced').lower()
    if focus_mode not in ('balanced', 'focus'):
        focus_mode = 'balanced'

    def _safe_int(value, default=0):
        try:
            if value in (None, ''):
                return default
            return int(value)
        except (TypeError, ValueError):
            return default

    payload = {
        'targeting_mode': targeting_mode,
        'margin_proficiency': _safe_int(config.get('margin_proficiency'), 0),
        'margin_experience': _safe_int(config.get('margin_experience'), 0),
        'focus_mode': focus_mode,
        'focus_branches': json.dumps(config.get('focus_branches') or []),
        'focus_semesters': json.dumps(config.get('focus_semesters') or []),
        'focus_classes': json.dumps(config.get('focus_classes') or []),
        'slots_per_day': max(1, _safe_int(config.get('slots_per_day'), 6)),
        'slot_duration_minutes': max(15, _safe_int(config.get('slot_duration_minutes'), 60)),
        'days_per_week': max(1, _safe_int(config.get('days_per_week'), 5)),
        'term_weeks': max(1, _safe_int(config.get('term_weeks'), 20)),
        'first_slot_start': (config.get('first_slot_start') or '').strip() or None,
        'breaks_json': json.dumps(config.get('breaks') or []),
        'lab_multi_slot': 1 if config.get('lab_multi_slot', True) else 0,
        'config_json': json.dumps(config, ensure_ascii=False)
    }

    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO timetable_runs (
                institution_id, status, targeting_mode, margin_proficiency, margin_experience,
                focus_mode, focus_branches, focus_semesters, focus_classes,
                slots_per_day, slot_duration_minutes, days_per_week, term_weeks, first_slot_start,
                breaks_json, lab_multi_slot, config_json
            ) VALUES (?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            institution_id,
            payload['targeting_mode'],
            payload['margin_proficiency'],
            payload['margin_experience'],
            payload['focus_mode'],
            payload['focus_branches'],
            payload['focus_semesters'],
            payload['focus_classes'],
            payload['slots_per_day'],
            payload['slot_duration_minutes'],
            payload['days_per_week'],
            payload['term_weeks'],
            payload['first_slot_start'],
            payload['breaks_json'],
            payload['lab_multi_slot'],
            payload['config_json']
        ))
        run_id = cursor.lastrowid
        conn.commit()
        return {'status': 'success', 'run_id': run_id}


def update_timetable_run_status(run_id, institution_id, status):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE timetable_runs SET status = ? WHERE id = ? AND institution_id = ?
        ''', (status, run_id, institution_id))
        conn.commit()
        return cursor.rowcount > 0

def delete_timetable_run(run_id, institution_id):
    if not run_id:
        return False
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM timetable_runs WHERE id = ? AND institution_id = ?
        ''', (run_id, institution_id))
        conn.commit()
        return cursor.rowcount > 0


def get_recent_timetable_runs(institution_id, limit=5, status=None):
    """Return the latest timetable runs, optionally filtered by status."""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        status_filter = None
        if isinstance(status, str):
            status_filter = status.strip().lower() or None

        query = '''
            SELECT * FROM timetable_runs
            WHERE institution_id = ?
        '''
        params = [institution_id]
        if status_filter:
            query += ' AND LOWER(status) = ?'
            params.append(status_filter)
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)

        cursor.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        for row in rows:
            row['config'] = json.loads(row.get('config_json') or '{}')
            row['engine_summary'] = row['config'].get('engine_summary') if isinstance(row['config'], dict) else None
            row['focus_branches'] = json.loads(row.get('focus_branches') or '[]')
            row['focus_semesters'] = json.loads(row.get('focus_semesters') or '[]')
            row['focus_classes'] = json.loads(row.get('focus_classes') or '[]')
            row['breaks'] = json.loads(row.get('breaks_json') or '[]')
        return rows


def get_latest_timetable_run(institution_id, status='completed'):
    """Convenience wrapper to grab the newest run matching an optional status filter."""
    runs = get_recent_timetable_runs(institution_id, limit=1, status=status)
    return runs[0] if runs else None

def get_timetable_run(run_id, institution_id):
    """Return a single timetable run with decoded JSON fields."""
    if not run_id:
        return None

    def _decode_list(raw_value):
        try:
            decoded = json.loads(raw_value or '[]')
        except (TypeError, json.JSONDecodeError):
            return []
        cleaned = []
        for value in decoded:
            try:
                cleaned.append(int(value))
            except (TypeError, ValueError):
                continue
        return cleaned

    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM timetable_runs
            WHERE id = ? AND institution_id = ?
        ''', (run_id, institution_id))
        row = cursor.fetchone()
        if not row:
            return None
        payload = dict(row)
        try:
            payload['config'] = json.loads(payload.get('config_json') or '{}')
        except (TypeError, json.JSONDecodeError):
            payload['config'] = {}
        if isinstance(payload['config'], dict):
            payload['engine_summary'] = payload['config'].get('engine_summary')
        payload['focus_branches'] = _decode_list(payload.get('focus_branches'))
        payload['focus_semesters'] = _decode_list(payload.get('focus_semesters'))
        payload['focus_classes'] = _decode_list(payload.get('focus_classes'))
        try:
            payload['breaks'] = json.loads(payload.get('breaks_json') or '[]')
        except (TypeError, json.JSONDecodeError):
            payload['breaks'] = []
        return payload


def update_timetable_run_config(run_id, institution_id, config):
    """Persist a modified config payload for a timetable run."""
    if config is None:
        config = {}
    serialized = json.dumps(config, ensure_ascii=False)
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE timetable_runs
            SET config_json = ?
            WHERE id = ? AND institution_id = ?
        ''', (serialized, run_id, institution_id))
        conn.commit()
        return cursor.rowcount > 0


def get_timetable_entries(run_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM timetable_entries WHERE run_id = ? AND institution_id = ?
            ORDER BY day_index, slot_index
        ''', (run_id, institution_id))
        return [dict(row) for row in cursor.fetchall()]


def replace_timetable_entries(run_id, institution_id, entries):
    entries = entries or []
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM timetable_entries WHERE run_id = ? AND institution_id = ?', (run_id, institution_id))
        if entries:
            cursor.executemany('''
                INSERT INTO timetable_entries (
                    run_id, institution_id, class_id, subject_id, faculty_id,
                    room_id, day_index, slot_index, slot_span
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', [
                (
                    run_id,
                    institution_id,
                    entry.get('class_id'),
                    entry.get('subject_id'),
                    entry.get('faculty_id'),
                    entry.get('room_id'),
                    entry.get('day_index', 0),
                    entry.get('slot_index', 0),
                    max(1, int(entry.get('slot_span', 1)))
                )
                for entry in entries
            ])
        conn.commit()
        return {'status': 'success', 'count': len(entries)}


def get_timetable_sessions_for_faculty(run_id, institution_id, faculty_id):
    """Return the scheduled blocks for a faculty member within a specific run."""
    if not run_id or not faculty_id:
        return []
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                te.day_index,
                te.slot_index,
                te.slot_span,
                te.class_id,
                te.subject_id,
                te.room_id,
                subj.name AS subject_name,
                subj.subject_id AS subject_code,
                cls.class_name,
                cls.section,
                cls.class_id AS class_code,
                sem.semester_number,
                prog.program_name,
                room.room_number,
                room.room_type
            FROM timetable_entries te
            LEFT JOIN subjects subj ON subj.id = te.subject_id
            LEFT JOIN classes cls ON cls.id = te.class_id
            LEFT JOIN semesters sem ON cls.semester_id = sem.id
            LEFT JOIN programs prog ON sem.program_id = prog.id
            LEFT JOIN campus_rooms room ON room.id = te.room_id
            WHERE te.run_id = ? AND te.institution_id = ? AND te.faculty_id = ?
            ORDER BY te.day_index, te.slot_index
        ''', (run_id, institution_id, faculty_id))
        sessions = []
        for row in cursor.fetchall():
            payload = dict(row)
            title = payload.get('subject_name') or 'Subject TBD'
            code = payload.get('subject_code')
            label = f"{title} • {code}" if code else title
            class_bits = []
            if payload.get('class_name'):
                class_bits.append(payload['class_name'])
            if payload.get('section'):
                class_bits.append(f"Section {payload['section']}")
            if payload.get('program_name') and payload.get('semester_number'):
                class_bits.append(f"{payload['program_name']} • Sem {payload['semester_number']}")
            class_label = ' • '.join(class_bits) if class_bits else ''
            room_label = None
            if payload.get('room_number'):
                descriptor = payload.get('room_type') or 'Room'
                room_label = f"{descriptor.title()} {payload['room_number']}"
            sessions.append({
                'day_index': payload.get('day_index', 0),
                'slot_index': payload.get('slot_index', 0),
                'slot_span': payload.get('slot_span', 1),
                'subject_label': label,
                'subject_name': title,
                'subject_code': code,
                'class_label': class_label,
                'class_id': payload.get('class_id'),
                'subject_id': payload.get('subject_id'),
                'room_label': room_label,
                'room_id': payload.get('room_id')
            })
        return sessions


def get_timetable_preview_snapshot(run_id, institution_id, rollup_limit=6):
    """Provide aggregate counts plus top-level faculty/class coverage for a run."""
    if not run_id:
        return {'totals': {}, 'faculty': [], 'classes': []}
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                COUNT(*) AS session_count,
                COUNT(DISTINCT faculty_id) AS faculty_count,
                COUNT(DISTINCT class_id) AS class_count
            FROM timetable_entries
            WHERE run_id = ? AND institution_id = ?
        ''', (run_id, institution_id))
        raw_totals = cursor.fetchone()
        totals_row = dict(raw_totals) if raw_totals else {}
        totals = {
            'session_count': totals_row.get('session_count', 0),
            'faculty_count': totals_row.get('faculty_count', 0),
            'class_count': totals_row.get('class_count', 0)
        }

        cursor.execute('''
            SELECT
                te.faculty_id,
                f.first_name,
                f.last_name,
                f.faculty_id AS faculty_code,
                COUNT(*) AS session_count,
                COUNT(DISTINCT te.class_id) AS class_count,
                COUNT(DISTINCT te.subject_id) AS subject_count
            FROM timetable_entries te
            LEFT JOIN faculty f ON f.id = te.faculty_id
            WHERE te.run_id = ? AND te.institution_id = ?
            GROUP BY te.faculty_id
            ORDER BY session_count DESC
            LIMIT ?
        ''', (run_id, institution_id, rollup_limit))
        faculty_rows = []
        for row in cursor.fetchall():
            payload = dict(row)
            full_name = ' '.join(filter(None, [payload.get('first_name'), payload.get('last_name')])).strip()
            faculty_rows.append({
                'faculty_db_id': payload.get('faculty_id'),
                'display_name': full_name or (payload.get('faculty_code') or 'Faculty'),
                'faculty_code': payload.get('faculty_code'),
                'session_count': payload.get('session_count', 0),
                'class_count': payload.get('class_count', 0),
                'subject_count': payload.get('subject_count', 0)
            })

        cursor.execute('''
            SELECT
                te.class_id,
                cls.class_name,
                cls.section,
                cls.class_id AS class_code,
                COUNT(*) AS session_count,
                COUNT(DISTINCT te.subject_id) AS subject_count,
                COUNT(DISTINCT te.faculty_id) AS faculty_count,
                sem.semester_number,
                prog.program_name
            FROM timetable_entries te
            LEFT JOIN classes cls ON cls.id = te.class_id
            LEFT JOIN semesters sem ON cls.semester_id = sem.id
            LEFT JOIN programs prog ON sem.program_id = prog.id
            WHERE te.run_id = ? AND te.institution_id = ?
            GROUP BY te.class_id
            ORDER BY session_count DESC
            LIMIT ?
        ''', (run_id, institution_id, rollup_limit))
        class_rows = []
        for row in cursor.fetchall():
            payload = dict(row)
            label_parts = [payload.get('class_name') or 'Class']
            if payload.get('section'):
                label_parts.append(f"Section {payload['section']}")
            if payload.get('program_name') and payload.get('semester_number'):
                label_parts.append(f"{payload['program_name']} • Sem {payload['semester_number']}")
            class_rows.append({
                'class_db_id': payload.get('class_id'),
                'display_label': ' • '.join(label_parts),
                'class_code': payload.get('class_code'),
                'session_count': payload.get('session_count', 0),
                'faculty_count': payload.get('faculty_count', 0),
                'subject_count': payload.get('subject_count', 0)
            })

        return {
            'totals': totals,
            'faculty': faculty_rows,
            'classes': class_rows
        }


def create_subject_chapter(subject_id, chapter_name, chapter_number, institution_id, created_by=None, description=None):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO subject_chapters (subject_id, chapter_name, chapter_number, description, created_by, institution_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (subject_id, chapter_name.strip(), chapter_number, description or '', created_by, institution_id))
        conn.commit()
        return cursor.lastrowid


def delete_subject_chapter(chapter_id, institution_id):
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE subject_resources SET chapter_id = NULL WHERE chapter_id = ? AND institution_id = ?', (chapter_id, institution_id))
        cursor.execute('DELETE FROM subject_chapters WHERE id = ? AND institution_id = ?', (chapter_id, institution_id))
        conn.commit()
        return cursor.rowcount > 0


def get_chapter_resources(chapter_id, institution_id):
    chapter = get_subject_chapter(chapter_id, institution_id)
    if not chapter:
        return None, []
    resources = get_subject_resources(chapter['subject_id'], institution_id, chapter_id=chapter_id)
    return chapter, resources


def delete_subject_resource(resource_id, institution_id):
    """Delete a resource record and remove the stored file if it exists."""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT file_path FROM subject_resources WHERE id = ? AND institution_id = ?
        ''', (resource_id, institution_id))
        row = cursor.fetchone()
        if not row:
            return False
        file_path = row['file_path']
        cursor.execute('DELETE FROM subject_resources WHERE id = ? AND institution_id = ?', (resource_id, institution_id))
        conn.commit()

    if file_path and os.path.isfile(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass
    return True

# ============ DELETE FUNCTIONS ============

def delete_program(program_id, institution_id):
    """Delete a program and all related data"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        try:
            # Delete all students in classes of this program
            cursor.execute('''
                DELETE FROM students 
                WHERE class_id IN (
                    SELECT id FROM classes WHERE program_id = ?
                )
            ''', (program_id,))
            
            # Delete all faculty assignments for classes in this program
            cursor.execute('''
                DELETE FROM faculty_classes
                WHERE class_id IN (
                    SELECT id FROM classes WHERE program_id = ?
                )
            ''', (program_id,))
            
            # Delete all classes
            cursor.execute('DELETE FROM classes WHERE program_id = ?', (program_id,))
            
            # Delete all semesters
            cursor.execute('DELETE FROM semesters WHERE program_id = ?', (program_id,))
            
            # Delete the program
            cursor.execute('DELETE FROM programs WHERE id = ?', (program_id,))
            
            conn.commit()
            return {'status': 'success', 'message': 'Program deleted'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

def delete_semester(semester_id, institution_id):
    """Delete a semester and all related data"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        try:
            # Delete all students in classes of this semester
            cursor.execute('''
                DELETE FROM students 
                WHERE class_id IN (
                    SELECT id FROM classes WHERE semester_id = ?
                )
            ''', (semester_id,))
            
            # Delete all faculty assignments for classes in this semester
            cursor.execute('''
                DELETE FROM faculty_classes
                WHERE class_id IN (
                    SELECT id FROM classes WHERE semester_id = ?
                )
            ''', (semester_id,))
            
            # Delete all classes
            cursor.execute('DELETE FROM classes WHERE semester_id = ?', (semester_id,))
            
            # Delete the semester
            cursor.execute('DELETE FROM semesters WHERE id = ?', (semester_id,))
            
            conn.commit()
            return {'status': 'success', 'message': 'Semester deleted'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

def delete_class(class_id, institution_id):
    """Delete a class and all related data"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        try:
            # Delete all students in this class
            cursor.execute('DELETE FROM students WHERE class_id = ?', (class_id,))
            
            # Delete all faculty assignments for this class
            cursor.execute('DELETE FROM faculty_classes WHERE class_id = ?', (class_id,))
            
            # Delete the class
            cursor.execute('DELETE FROM classes WHERE id = ?', (class_id,))
            
            conn.commit()
            return {'status': 'success', 'message': 'Class deleted'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

def delete_faculty(faculty_id, institution_id):
    """Delete a faculty member and remove from all classes"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        try:
            # Delete all class assignments for this faculty
            cursor.execute('DELETE FROM faculty_classes WHERE faculty_id = ?', (faculty_id,))
            
            # Delete the faculty member
            cursor.execute('DELETE FROM faculty WHERE id = ?', (faculty_id,))
            
            conn.commit()
            return {'status': 'success', 'message': 'Faculty deleted'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

def delete_student(student_id, institution_id):
    """Delete a student"""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT class_id FROM students WHERE id = ? AND institution_id = ?
            ''', (student_id, institution_id))
            row = cursor.fetchone()
            if not row:
                return {'status': 'error', 'message': 'Student not found'}

            cursor.execute('DELETE FROM students WHERE id = ? AND institution_id = ?', (student_id, institution_id))
            if row['class_id']:
                _refresh_class_enrollment_metadata(cursor, row['class_id'], institution_id)
            conn.commit()
            return {'status': 'success', 'message': 'Student deleted'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}


# ============ FULL DATA EXPORT/IMPORT (BETA) ============

def _fetch_table_data(conn, table_name, where_clause=None, params=None):
    """Internal helper to fetch entire table as list of dicts"""
    cursor = conn.cursor()
    query = f'SELECT * FROM {table_name}'
    if where_clause:
        query += f' WHERE {where_clause}'
    cursor.execute(query, params or ())
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def _insert_rows(conn, table_name, rows):
    """Insert rows into a table preserving explicit IDs"""
    if not rows:
        return
    cursor = conn.cursor()
    columns = list(rows[0].keys())
    placeholders = ','.join(['?' for _ in columns])
    column_clause = ','.join(columns)
    values = [tuple(row.get(col) for col in columns) for row in rows]
    cursor.executemany(
        f'INSERT INTO {table_name} ({column_clause}) VALUES ({placeholders})',
        values
    )


def _replace_table_data(conn, table_name, rows):
    """Internal helper to replace table contents with provided rows"""
    cursor = conn.cursor()
    cursor.execute(f'DELETE FROM {table_name}')
    _insert_rows(conn, table_name, rows)


def _gather_institution_files(institution_id):
    """Collect every non-database file for the institution for backup"""
    base_path = os.path.join(INSTITUTIONS_DIR, institution_id)
    blobs = []
    if not os.path.exists(base_path):
        return blobs
    for root, _, files in os.walk(base_path):
        for name in files:
            if name.lower().endswith('.db'):
                continue
            abs_path = os.path.join(root, name)
            rel_path = os.path.relpath(abs_path, base_path)
            try:
                with open(abs_path, 'rb') as handle:
                    encoded = base64.b64encode(handle.read()).decode('utf-8')
                blobs.append({
                    'path': rel_path.replace('\\', '/'),
                    'data': encoded
                })
            except Exception:
                continue
    return blobs


def _restore_institution_files(institution_id, files):
    """Recreate institution file storage from backup payload"""
    base_path = os.path.join(INSTITUTIONS_DIR, institution_id)
    os.makedirs(base_path, exist_ok=True)
    if files is None:
        files = []

    # Remove existing non-DB files so restore is clean
    existing = []
    for root, _, filenames in os.walk(base_path):
        for name in filenames:
            if name.lower().endswith('.db'):
                continue
            rel_path = os.path.relpath(os.path.join(root, name), base_path)
            existing.append(rel_path)
    for rel in existing:
        try:
            os.remove(os.path.join(base_path, rel))
        except FileNotFoundError:
            continue

    # Remove emptied directories (skip those containing DB files)
    for root, dirs, filenames in os.walk(base_path, topdown=False):
        if any(name.lower().endswith('.db') for name in filenames):
            continue
        if not dirs and not filenames:
            try:
                os.rmdir(root)
            except OSError:
                pass

    restored = 0
    for entry in files:
        path = (entry or {}).get('path')
        data = (entry or {}).get('data')
        if not path or data is None:
            continue
        normalized = os.path.normpath(path).replace('\\', '/')
        if normalized.startswith('..'):
            continue
        dest = os.path.join(base_path, normalized)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            with open(dest, 'wb') as handle:
                handle.write(base64.b64decode(data))
            restored += 1
        except Exception:
            continue
    return restored


def get_infinity_pane_state(institution_id):
    """Fetch saved Infinity Pane canvas state for an institution."""
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT payload
            FROM infinity_pane_state
            WHERE institution_id = ?
        ''', (institution_id,))
        row = cursor.fetchone()
        if not row:
            return None
        payload = row['payload']
        if not payload:
            return None
        try:
            return json.loads(payload)
        except (TypeError, ValueError):
            return None


def save_infinity_pane_state(institution_id, payload, actor=None):
    """Persist Infinity Pane canvas state for an institution."""
    payload_json = json.dumps(payload or {})
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO infinity_pane_state (institution_id, payload, updated_by, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(institution_id) DO UPDATE SET
                payload = excluded.payload,
                updated_by = excluded.updated_by,
                updated_at = CURRENT_TIMESTAMP
        ''', (institution_id, payload_json, actor))
        conn.commit()


def create_infinity_pane_audit(institution_id, actor_id, actor_name, action, summary=None):
    """Write an audit entry for Infinity Pane changes."""
    summary_json = json.dumps(summary or {})
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO infinity_pane_audit (institution_id, actor_id, actor_name, action, summary)
            VALUES (?, ?, ?, ?, ?)
        ''', (institution_id, actor_id, actor_name, action, summary_json))
        conn.commit()


def get_infinity_pane_audit(institution_id, limit=50):
    """Return recent Infinity Pane audit entries."""
    safe_limit = max(1, min(int(limit or 50), 200))
    with get_db_connection(institution_id, 'student') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, institution_id, actor_id, actor_name, action, summary, created_at
            FROM infinity_pane_audit
            WHERE institution_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        ''', (institution_id, safe_limit))
        rows = []
        for row in cursor.fetchall():
            entry = dict(row)
            try:
                entry['summary'] = json.loads(entry.get('summary') or '{}')
            except (TypeError, ValueError):
                entry['summary'] = {}
            rows.append(entry)
        return rows


def export_full_institution_data(institution_id):
    """Export every table for an institution across all role databases"""
    data = {
        'metadata': {
            'institution_id': institution_id,
            'exported_at': datetime.utcnow().isoformat(),
            'version': 'beta-2'
        }
    }

    # Student DB snapshot
    student_tables = [
        'programs',
        'semesters',
        'classes',
        'faculty',
        'faculty_classes',
        'faculty_subjects',
        'students',
        'subjects',
        'subject_students',
        'subject_semesters',
        'subject_chapters',
        'subject_resources',
        'campus_floors',
        'campus_sections',
        'campus_rooms',
        'timetable_runs',
        'timetable_entries',
        'infinity_pane_state',
        'infinity_pane_audit'
    ]
    with get_db_connection(institution_id, 'student') as conn:
        data['student_db'] = {
            table: _fetch_table_data(conn, table)
            for table in student_tables
        }

    # Faculty DB snapshot
    faculty_tables = ['faculties', 'class_faculty', 'assignments', 'resources']
    with get_db_connection(institution_id, 'faculty') as conn:
        data['faculty_db'] = {
            table: _fetch_table_data(conn, table)
            for table in faculty_tables
        }

    # Admin DB snapshot
    with get_db_connection(institution_id, 'admin') as conn:
        data['admin_db'] = {
            'admins': _fetch_table_data(conn, 'admins')
        }

    # Master DB snapshot (institution scoped)
    with get_db_connection(institution_id, 'master') as conn:
        data['master_db'] = {
            'institutions': _fetch_table_data(conn, 'institutions', 'id = ?', (institution_id,)),
            'admin_roles': _fetch_table_data(conn, 'admin_roles', 'institution_id = ?', (institution_id,))
        }

    data['files'] = _gather_institution_files(institution_id)

    return data


def import_full_institution_data(institution_id, payload):
    """Restore every table for an institution from a full export payload"""
    if not isinstance(payload, dict):
        raise ValueError('Invalid payload format')

    summary = {}

    def _import_section(conn, table_order, data_key):
        section = payload.get(data_key, {})
        processed = {}
        if not isinstance(section, dict):
            return processed
        cursor = conn.cursor()
        cursor.execute('PRAGMA foreign_keys = OFF')
        try:
            for table in table_order:
                if table not in section:
                    continue
                rows = section.get(table) or []
                _replace_table_data(conn, table, rows)
                processed[table] = len(rows)
        finally:
            cursor.execute('PRAGMA foreign_keys = ON')
        return processed

    # Student DB
    with get_db_connection(institution_id, 'student') as conn:
        summary['student_db'] = _import_section(
            conn,
            [
                'programs',
                'semesters',
                'classes',
                'faculty',
                'faculty_classes',
                'faculty_subjects',
                'students',
                'subjects',
                'subject_students',
                'subject_semesters',
                'subject_chapters',
                'subject_resources',
                'campus_floors',
                'campus_sections',
                'campus_rooms',
                'timetable_runs',
                'timetable_entries',
                'infinity_pane_state',
                'infinity_pane_audit'
            ],
            'student_db'
        )

    # Faculty DB
    with get_db_connection(institution_id, 'faculty') as conn:
        summary['faculty_db'] = _import_section(
            conn,
            ['faculties', 'class_faculty', 'assignments', 'resources'],
            'faculty_db'
        )

    # Admin DB
    with get_db_connection(institution_id, 'admin') as conn:
        summary['admin_db'] = _import_section(conn, ['admins'], 'admin_db')

    # Master DB (scoped delete/insert)
    master_section = payload.get('master_db', {})
    summary['master_db'] = {}
    with get_db_connection(institution_id, 'master') as conn:
        cursor = conn.cursor()
        if 'institutions' in master_section:
            cursor.execute('DELETE FROM institutions WHERE id = ?', (institution_id,))
            rows = master_section.get('institutions') or []
            _insert_rows(conn, 'institutions', rows)
            summary['master_db']['institutions'] = len(rows)
        if 'admin_roles' in master_section:
            cursor.execute('DELETE FROM admin_roles WHERE institution_id = ?', (institution_id,))
            rows = master_section.get('admin_roles') or []
            _insert_rows(conn, 'admin_roles', rows)
            summary['master_db']['admin_roles'] = len(rows)

    restored_files = _restore_institution_files(institution_id, payload.get('files'))
    summary['files'] = restored_files

    return summary

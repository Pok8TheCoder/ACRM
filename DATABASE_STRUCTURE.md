# Institution Database Structure

## Overview
Each institution now has a hierarchical database structure that separates concerns by role and includes file storage for user-generated content.

## Directory Structure

```
institutions/
└── {institution_id}/              (e.g., iit_delhi)
    ├── Master_Admin.db            (Principal/Super Admin - controls all access)
    ├── student/
    │   ├── student.db             (Student data, programs, classes)
    │   └── data/
    │       └── {student_id}/      (Student assignments, uploads)
    ├── faculty/
    │   ├── faculty.db             (Faculty data, assignments, resources)
    │   └── data/
    │       └── {faculty_id}/      (Faculty resources, notes, uploads)
    └── Admin/
        ├── admin.db               (Admin/staff data)
        └── data/
            └── {admin_id}/        (Admin documents, logs)
```

## Database Files

### Master_Admin.db
**Purpose**: Access control and admin role management  
**Tables**:
- `institutions` - List of all institutions
- `admin_roles` - Defines admin permissions (can_create_students, can_create_faculty, can_create_admins)

**Key Feature**: A principal creates other admins and grants them specific permissions. For example:
- Principal can create/delete admins, students, and faculty
- IT Head admin (created by principal) can create student and faculty IDs
- Department Head admin (created by principal) can only view specific departments

### student.db
**Purpose**: All student-related data  
**Tables**:
- `programs` - Degree programs (CSE, ECE, ME, CE, etc.)
- `classes` - Class sections (CSE-1A, CSE-1B, etc.)
- `students` - Student accounts and academic data

**Isolated**: Only contains student information, no faculty or admin data

### faculty.db
**Purpose**: All faculty-related teaching and content  
**Tables**:
- `faculties` - Faculty accounts and info
- `class_faculty` - Faculty-class assignments and subjects
- `assignments` - Assignment metadata
- `resources` - Course materials, notes, lecture slides

**Isolated**: Only contains faculty information and their teaching materials

### Admin.db
**Purpose**: Administrative staff data  
**Tables**:
- `admins` - Admin/staff accounts

**Isolated**: Separate from Principal's Master_Admin.db

## File Upload Paths

### Student Data
```
institutions/iit_delhi/student/data/STD001/
├── assignment_1_solution.pdf
├── project_submission_1.zip
└── [other student uploads]
```

### Faculty Data
```
institutions/iit_delhi/faculty/data/FAC001/
├── lecture_slides_01.pdf
├── course_notes.docx
├── resource_assignment_1.pdf
└── [other faculty uploads]
```

### Admin Data
```
institutions/iit_delhi/Admin/data/ADM001/
├── reports.xlsx
├── logs.txt
└── [other admin documents]
```

## Access Control Hierarchy

### Principal (Super Admin) - Master_Admin.db
- ✅ Create new admins with specific roles
- ✅ Grant permissions to admins (can_create_students, can_create_faculty, can_create_admins)
- ✅ View all institution data
- ✅ Full system control

### Regular Admin - Master_Admin.db + specific role DB
- ✅ Create students/faculty (if granted permission)
- ✅ Manage their respective domains
- ❌ Cannot create other admins (unless granted)
- ❌ Limited view based on permissions

### Faculty - faculty.db
- ✅ Create assignments
- ✅ Upload course materials
- ✅ View student work
- ❌ Cannot modify student records
- ❌ Cannot access admin functions

### Student - student.db
- ✅ View class information
- ✅ Upload assignments
- ✅ View grades/GPA
- ❌ Cannot modify class data
- ❌ Cannot view other students' work

## Benefits

1. **Data Isolation**: Each role has its own database, preventing unauthorized access
2. **Scalability**: Easy to add new institutions (just create new institution folder)
3. **Organized Storage**: File uploads are organized by role and user ID
4. **Access Control**: Master_Admin.db provides granular permission management
5. **Maintainability**: Separate databases make it easier to backup and manage data
6. **Security**: Reduces attack surface by limiting cross-role data exposure

## Usage in Code

```python
from database import get_db_connection, get_data_upload_path

# Get student database connection
with get_db_connection('iit_delhi', 'student') as conn:
    # Query student data
    pass

# Get faculty database connection
with get_db_connection('iit_delhi', 'faculty') as conn:
    # Query faculty/assignment data
    pass

# Get file upload path for a student
upload_path = get_data_upload_path('iit_delhi', 'student', 'STD001')
# Returns: institutions/iit_delhi/student/data/STD001/

# Get file upload path for faculty
upload_path = get_data_upload_path('iit_delhi', 'faculty', 'FAC001')
# Returns: institutions/iit_delhi/faculty/data/FAC001/
```

## Creating a New Institution

To add a new institution (e.g., NIT Rourkee):

1. Create institution folder: `institutions/nit_rourkee/`
2. Call `init_db('nit_rourkee')` - This will:
   - Create `Master_Admin.db` with principal account
   - Create `student/student.db` with sample programs/classes
   - Create `faculty/faculty.db` with sample faculty
   - Create `Admin/admin.db`
   - Create all necessary `data/` folders

```python
from database import init_db

# Initialize new institution
init_db('nit_rourkee')
```

That's it! The new institution is ready to use.

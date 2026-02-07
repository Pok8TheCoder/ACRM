# ACRM Student & Faculty System - Quick Start Guide

## System Architecture

The ACRM system is based on **IIT Delhi Engineering Campus** with proper role-based access control:

### Institutions (Database Storage)
- ✅ IIT Delhi Engineering Campus (stored in SQLite database)
- Uses: `id = 'iit_delhi'`

### Programs (Engineering - UG)
- Computer Science & Engineering (CSE)
- Electronics & Communication Engineering (ECE)
- Mechanical Engineering (ME)
- Civil Engineering (CE)

### Role Structure
1. **Student** - Views assignments, submits work, tracks progress
2. **Faculty** - Creates assignments, manages classes, verifies submissions
3. **Admin** - System administration
4. **Principal** - Institutional oversight

---

## How the System Now Works

### ✅ FIXED: Student Sees Faculty Assignments

**Before**: Student couldn't see assignments created by faculty
**Now**: 
1. Faculty creates assignment in a class
2. Assignment auto-assigned to all students in that class
3. Students see it in `/student/classroom` 
4. Students can view via subject cards → assignment modal

### Linking Flow
```
Faculty Creates Assignment (class_faculty_id = 1, subject = "Data Structures")
    ↓
Database creates "assignments" entry
    ↓
Database auto-creates "student_assignments" entries for ALL students in class
    ↓
Student logs in
    ↓
Session stores student's class_id
    ↓
/api/student/subjects returns student's classes via class_faculty matching
    ↓
/api/student/subject/<class_faculty_id>/assignments returns assignments
    ↓
Student sees assignments in classroom modal
```

---

## Student Workflow

### Login
```
1. Visit http://localhost:5000/login
2. Select "IIT Delhi Engineering Campus"
3. Select "Student" role
4. Enter Student ID + Password
   Example: STD001 / password123
```

### View Dashboard
```
Dashboard shows:
- Welcome greeting
- Assignments due (next 7 days)
- Completed assignments this semester
- Overall attendance % with subject breakdown
```

### View Classroom & Assignments
```
1. Click "Classroom" in left sidebar
2. Grid of subject cards appears (one for each subject you're enrolled in)
   - Shows: Subject name, Faculty name, Class name
3. Click any subject card → Modal opens
4. See "Assignments" tab (default) with all assignments:
   - Active assignments (blue)
   - Overdue assignments (red)
   - Closing soon assignments (orange - < 24hrs)
   - Closed assignments (gray)
5. Click "Resources" tab for future course materials
```

---

## Faculty Workflow

### Login
```
1. Visit http://localhost:5000/login
2. Select "IIT Delhi Engineering Campus"
3. Select "Faculty" role
4. Enter Faculty ID + Password
   Example: FAC001 / faculty123
```

### View Classroom & Manage Assignments
```
1. Click "Classroom" in left sidebar
2. Grid of class cards appears (all classes you teach)
   - Shows: Class name, Program, Subject, Room, Student count
3. Click "Manage" on a class card → Class management interface opens
4. Two tabs appear:
   a) Assignments Tab (default):
      - List of all assignments for this class
      - Stats: Submitted count, Pending count, Verified count
      - Green "Add Assignment" button → Opens modal
      - Click any assignment → View student submissions page
      
   b) Resources Tab:
      - "Upload Resource" button (future feature)
5. Create Assignment Process:
   - Click "Add Assignment" button
   - Modal appears with:
     * Title field
     * Description field
     * Due Date & Time field
   - Submit → Assignment created instantly
   - Auto-assigned to ALL students in class
   - Modal closes, list refreshes
```

### View Student Submissions
```
1. From Assignments list, click any assignment card
2. Go to assignment details page
3. See stats: Total students, Submitted, Not submitted, Verified
4. List of students with submission status
5. Click "Verify" button to mark submission as verified
6. Status updates immediately
```

---

## Database Structure

### Key Tables
1. **institutions** - IIT Delhi campus info
2. **programs** - CSE, ECE, ME, CE
3. **classes** - CSE-1A, CSE-1B, ECE-1A, ME-1A, CE-1A
4. **students** - Linked to program AND class
5. **faculties** - Faculty members with departments
6. **class_faculty** - Maps which faculty teaches which class (many-to-many)
7. **assignments** - Assignment records
8. **student_assignments** - Per-student: submission status + verification status
9. **resources** - Course materials (future)
10. **admins** - Admin/Principal accounts

### How Students Get Assignments
1. Faculty teaches class → creates entry in `class_faculty`
2. Faculty creates assignment → entry in `assignments` with class_faculty_id
3. System auto-creates `student_assignments` for all students in that class_faculty.class_id
4. Student can now see assignment in their classroom view

---

## Demo Data

### IIT Delhi Sample Setup

**CSE Program (2 Classes)**
- **CSE-1A** (Room 101, 60 students)
  - Faculty: Dr. Rajesh Kumar (FAC001)
  - Subject: Data Structures
  - Students: STD001 (Arjun), STD002 (Priya)
  
- **CSE-1B** (Room 102, 60 students)
  - Faculty: Dr. Rajesh Kumar (FAC001)
  - Subject: Data Structures
  - Students: STD003 (Rohan)

**ECE Program (1 Class)**
- **ECE-1A** (Room 201, 55 students)
  - Faculty: Prof. Sneha Desai (FAC002)
  - Subject: Signals & Systems
  - Students: STD004 (Neha)

**ME Program (1 Class)**
- **ME-1A** (Room 301, 50 students)
  - Faculty: Dr. Anil Verma (FAC003)
  - Subject: Engineering Thermodynamics
  - Students: STD005 (Vikram)

**CE Program (1 Class)**
- **CE-1A** (Room 401, 50 students)
  - No faculty assigned yet

---

## Test Scenarios

### Scenario 1: New Assignment Visibility
```
Step 1: Login as FAC001 (teaches CSE-1A and CSE-1B Data Structures)
Step 2: Go to Classroom → Click CSE-1A → Click "Add Assignment"
Step 3: Create assignment: 
   Title: "Quick Sort Implementation"
   Due: 2025-11-28 17:00
Step 4: Logout

Step 5: Login as STD001 (in CSE-1A)
Step 6: Go to Classroom → Click "Data Structures" card
Step 7: ✅ See "Quick Sort Implementation" in Assignments tab

Step 8: Logout and Login as STD003 (in CSE-1B)
Step 9: Go to Classroom → Click "Data Structures" card
Step 10: ✅ See "Quick Sort Implementation" (same faculty teaches CSE-1B)

Step 11: Logout and Login as STD004 (in ECE-1A)
Step 12: Go to Classroom → Click "Signals & Systems" card
Step 13: ✅ Do NOT see CSE assignment (different class)
```

### Scenario 2: Subject Isolation
```
Step 1: Login as any student
Step 2: Go to Classroom
Step 3: ✅ Only see subjects where they're enrolled (based on their class_id)
Step 4: Subject card shows correct faculty name
Step 5: Subject card shows correct class name
```

### Scenario 3: Assignment Status Tracking
```
Step 1: Login as FAC001
Step 2: Create assignment with due date in past
Step 3: Logout

Step 4: Login as STD001
Step 5: Go to Classroom → Subject → Assignments
Step 6: ✅ Assignment shows RED status badge (Overdue)
```

---

## Troubleshooting

### Student Not Seeing Assignments
**Check**:
1. Student is enrolled in the correct class (check `class_id` in DB)
2. Faculty has been assigned to teach that class (`class_faculty` entry)
3. Assignment has been created with `class_faculty_id` pointing to that teaching assignment
4. Browser cache cleared (Ctrl+Shift+Delete)

**Debug**:
```
Faculty teaching CSE-1A → class_faculty.id = 1
Assignment created → assignments.class_faculty_id = 1
Student in CSE-1A → students.class_id = 1 (the actual ID, not text)
Assignment auto-assigned → student_assignments created for all class students
```

### Assignment Not Appearing in Student's Subject
**Check**:
1. Verify faculty ID matches in `class_faculty` table
2. Verify student's `class_id` matches the `class_faculty.class_id`
3. Try refreshing browser or clearing cache
4. Check browser console for API errors (F12 → Console tab)

### Database Issues
**Reset Database**:
```
1. Delete acrm.db file
2. Restart Flask app
3. Fresh database created with demo data
```

---

## Key Improvements Made

✅ **Fixed Student-Assignment Linking**
- Corrected database query logic
- Students now properly see assignments created by their faculty

✅ **Added Student Classroom View**
- New `/student/classroom` page
- Subject grid with faculty information
- Assignment modal with status indicators

✅ **Improved Session Management**
- Student's class_id and program_id stored in session
- Faster queries and better filtering

✅ **All Using SQLite Database**
- No JSON files
- Persistent, queryable data
- Proper foreign key relationships

✅ **IIT Delhi Engineering Campus**
- 4 UG programs configured
- 5 classes created with proper mappings
- 5 sample students in their respective classes
- 3 sample faculty with teaching assignments

---

## Next Features to Build

1. **Student Assignment Submission**
   - File upload form in student assignment view
   - Update submission_status to 'submitted'
   - Track submission_date

2. **Faculty Resource Upload**
   - Enable "Upload Resource" button
   - Create resources in `resources` table
   - Show PDFs/notes in student classroom

3. **Timetable Integration**
   - Show class schedule
   - Link to classroom
   - Display on student and faculty dashboards

4. **Email Notifications**
   - Alert students when new assignments posted
   - Reminder emails before deadline
   - Submission confirmation

5. **Admin Dashboard**
   - View all students/faculty
   - Create new classes
   - Manage assignments across institution

---

## API Reference

### Student APIs
- `GET /api/student/subjects` - Get all enrolled subjects
- `GET /api/student/assignments` - Get all assignments for student's class
- `GET /api/student/subject/<id>/assignments` - Get assignments for one subject

### Faculty APIs
- `GET /api/faculty/classes` - Get all classes taught
- `GET /api/faculty/assignments/<class_faculty_id>` - Get assignments for class
- `POST /api/faculty/create-assignment` - Create new assignment
- `GET /api/assignment/<assignment_id>` - Get assignment details + submissions
- `POST /api/verify-submission` - Mark submission as verified

### General APIs
- `POST /api/contact-message` - Contact form submission

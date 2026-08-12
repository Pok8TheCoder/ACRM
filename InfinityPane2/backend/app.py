"""
InfinityPane Backend - Flask API Server
A scheduling application for managing teachers, subjects, classes, and timetables
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import uuid

app = Flask(__name__)
CORS(app)

# In-memory data store (replace with database in production)
data_store = {
    "teachers": [
        {"id": "t1", "name": "Dr. Sarah Johnson", "subjects": ["s1", "s3"], "color": "#FF6B6B"},
        {"id": "t2", "name": "Prof. Michael Chen", "subjects": ["s2"], "color": "#4ECDC4"},
        {"id": "t3", "name": "Ms. Emily Davis", "subjects": ["s1", "s4"], "color": "#45B7D1"},
        {"id": "t4", "name": "Mr. Robert Wilson", "subjects": ["s5"], "color": "#96CEB4"},
        {"id": "t5", "name": "Dr. Amanda Brown", "subjects": ["s2", "s6"], "color": "#FFEAA7"},
        {"id": "t6", "name": "Prof. James Miller", "subjects": ["s3", "s5"], "color": "#DDA0DD"},
        {"id": "t7", "name": "Ms. Lisa Anderson", "subjects": ["s4", "s6"], "color": "#98D8C8"},
        {"id": "t8", "name": "Mr. David Taylor", "subjects": ["s1", "s2"], "color": "#F7DC6F"},
    ],
    "subjects": [
        {"id": "s1", "name": "Mathematics", "code": "MATH101", "color": "#FF6B6B"},
        {"id": "s2", "name": "Physics", "code": "PHY101", "color": "#4ECDC4"},
        {"id": "s3", "name": "Chemistry", "code": "CHEM101", "color": "#45B7D1"},
        {"id": "s4", "name": "Computer Science", "code": "CS101", "color": "#96CEB4"},
        {"id": "s5", "name": "English", "code": "ENG101", "color": "#FFEAA7"},
        {"id": "s6", "name": "History", "code": "HIS101", "color": "#DDA0DD"},
    ],
    "classes": [
        {"id": "c1", "name": "Computer Science A", "section": "A", "strength": 40},
        {"id": "c2", "name": "Computer Science B", "section": "B", "strength": 38},
        {"id": "c3", "name": "Electronics A", "section": "A", "strength": 35},
        {"id": "c4", "name": "Mechanical A", "section": "A", "strength": 42},
    ],
    "canvas_state": {
        "groups": [],
        "timetables": [],
        "arrows": [],
        "teacherPlacements": [],
        "subjectPlacements": [],
    }
}


# ============== Teacher Endpoints ==============

@app.route('/api/teachers', methods=['GET'])
def get_teachers():
    """Get all teachers with optional search filter"""
    search = request.args.get('search', '').lower()
    teachers = data_store['teachers']
    
    if search:
        teachers = [
            t for t in teachers 
            if search in t['name'].lower() 
            or search in t['id'].lower()
            or any(search in s.lower() for s in t.get('subjects', []))
        ]
    
    # Enrich with subject names
    subject_map = {s['id']: s for s in data_store['subjects']}
    enriched = []
    for t in teachers:
        teacher_copy = t.copy()
        teacher_copy['subjectDetails'] = [
            subject_map.get(sid, {'name': 'Unknown'}) 
            for sid in t.get('subjects', [])
        ]
        enriched.append(teacher_copy)
    
    return jsonify(enriched)


@app.route('/api/teachers', methods=['POST'])
def create_teacher():
    """Create a new teacher"""
    data = request.json
    new_teacher = {
        "id": f"t{uuid.uuid4().hex[:8]}",
        "name": data.get('name', 'New Teacher'),
        "subjects": data.get('subjects', []),
        "color": data.get('color', '#808080')
    }
    data_store['teachers'].append(new_teacher)
    return jsonify(new_teacher), 201


@app.route('/api/teachers/<teacher_id>', methods=['PUT'])
def update_teacher(teacher_id):
    """Update a teacher"""
    data = request.json
    for i, t in enumerate(data_store['teachers']):
        if t['id'] == teacher_id:
            data_store['teachers'][i].update(data)
            return jsonify(data_store['teachers'][i])
    return jsonify({"error": "Teacher not found"}), 404


@app.route('/api/teachers/<teacher_id>', methods=['DELETE'])
def delete_teacher(teacher_id):
    """Delete a teacher"""
    data_store['teachers'] = [t for t in data_store['teachers'] if t['id'] != teacher_id]
    return jsonify({"success": True})


# ============== Subject Endpoints ==============

@app.route('/api/subjects', methods=['GET'])
def get_subjects():
    """Get all subjects with optional search filter"""
    search = request.args.get('search', '').lower()
    subjects = data_store['subjects']
    
    if search:
        subjects = [
            s for s in subjects 
            if search in s['name'].lower() 
            or search in s['code'].lower()
            or search in s['id'].lower()
        ]
    
    return jsonify(subjects)


@app.route('/api/subjects', methods=['POST'])
def create_subject():
    """Create a new subject"""
    data = request.json
    new_subject = {
        "id": f"s{uuid.uuid4().hex[:8]}",
        "name": data.get('name', 'New Subject'),
        "code": data.get('code', 'SUB101'),
        "color": data.get('color', '#808080')
    }
    data_store['subjects'].append(new_subject)
    return jsonify(new_subject), 201


@app.route('/api/subjects/<subject_id>', methods=['PUT'])
def update_subject(subject_id):
    """Update a subject"""
    data = request.json
    for i, s in enumerate(data_store['subjects']):
        if s['id'] == subject_id:
            data_store['subjects'][i].update(data)
            return jsonify(data_store['subjects'][i])
    return jsonify({"error": "Subject not found"}), 404


@app.route('/api/subjects/<subject_id>', methods=['DELETE'])
def delete_subject(subject_id):
    """Delete a subject"""
    data_store['subjects'] = [s for s in data_store['subjects'] if s['id'] != subject_id]
    return jsonify({"success": True})


# ============== Class Endpoints ==============

@app.route('/api/classes', methods=['GET'])
def get_classes():
    """Get all classes"""
    return jsonify(data_store['classes'])


@app.route('/api/classes', methods=['POST'])
def create_class():
    """Create a new class"""
    data = request.json
    new_class = {
        "id": f"c{uuid.uuid4().hex[:8]}",
        "name": data.get('name', 'New Class'),
        "section": data.get('section', 'A'),
        "strength": data.get('strength', 30)
    }
    data_store['classes'].append(new_class)
    return jsonify(new_class), 201


# ============== Canvas State Endpoints ==============

@app.route('/api/canvas', methods=['GET'])
def get_canvas_state():
    """Get the entire canvas state"""
    return jsonify(data_store['canvas_state'])


@app.route('/api/canvas', methods=['POST'])
def save_canvas_state():
    """Save the entire canvas state"""
    data = request.json
    data_store['canvas_state'] = data
    return jsonify({"success": True})


@app.route('/api/canvas/groups', methods=['POST'])
def add_group():
    """Add a group to the canvas"""
    data = request.json
    group = {
        "id": f"g{uuid.uuid4().hex[:8]}",
        "name": data.get('name', ''),
        "x": data.get('x', 0),
        "y": data.get('y', 0),
        "width": data.get('width', 200),
        "height": data.get('height', 150),
        "parentId": data.get('parentId', None),
        "color": data.get('color', '#E8E8E8'),
        "teachers": [],
        "subjects": [],
    }
    data_store['canvas_state']['groups'].append(group)
    return jsonify(group), 201


@app.route('/api/canvas/timetables', methods=['POST'])
def add_timetable():
    """Add a timetable to the canvas"""
    data = request.json
    timetable = {
        "id": f"tt{uuid.uuid4().hex[:8]}",
        "classId": data.get('classId'),
        "x": data.get('x', 0),
        "y": data.get('y', 0),
        "days": data.get('days', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']),
        "slotsPerDay": data.get('slotsPerDay', 8),
        "slotDuration": data.get('slotDuration', 60),  # minutes
        "startTime": data.get('startTime', '09:00'),
        "groupId": data.get('groupId'),  # Must be linked to a group
    }
    data_store['canvas_state']['timetables'].append(timetable)
    return jsonify(timetable), 201


@app.route('/api/canvas/arrows', methods=['POST'])
def add_arrow():
    """Add an arrow connection"""
    data = request.json
    arrow = {
        "id": f"a{uuid.uuid4().hex[:8]}",
        "fromType": data.get('fromType'),  # 'teacher' or 'subject'
        "fromId": data.get('fromId'),
        "toType": data.get('toType'),  # 'teacher' or 'subject'
        "toId": data.get('toId'),
        "groupId": data.get('groupId'),  # Context group
    }
    data_store['canvas_state']['arrows'].append(arrow)
    return jsonify(arrow), 201


@app.route('/api/canvas/arrows/<arrow_id>', methods=['DELETE'])
def delete_arrow(arrow_id):
    """Delete an arrow connection"""
    data_store['canvas_state']['arrows'] = [
        a for a in data_store['canvas_state']['arrows'] if a['id'] != arrow_id
    ]
    return jsonify({"success": True})


# ============== Validation Endpoints ==============

@app.route('/api/validate/schedule', methods=['POST'])
def validate_schedule():
    """Validate the current schedule for conflicts"""
    canvas = data_store['canvas_state']
    conflicts = []
    warnings = []
    
    # Check for teacher conflicts (same teacher at same time)
    # Check for timetables without groups
    for tt in canvas.get('timetables', []):
        if not tt.get('groupId'):
            warnings.append({
                "type": "missing_group",
                "timetableId": tt['id'],
                "message": f"Timetable is not linked to any group"
            })
    
    # Check for groups without any content
    for group in canvas.get('groups', []):
        if not group.get('teachers') and not group.get('subjects'):
            warnings.append({
                "type": "empty_group",
                "groupId": group['id'],
                "message": f"Group '{group.get('name', 'Unnamed')}' is empty"
            })
    
    return jsonify({
        "valid": len(conflicts) == 0,
        "conflicts": conflicts,
        "warnings": warnings
    })


# ============== Health Check ==============

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)

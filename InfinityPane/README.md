# InfinityPane

React-based prototype with a Flask backend.

## What’s Included
- Infinite 2D canvas with pan and zoom
- Tool bar for tables, groups, and arrow linking
- Timetables linked to existing classes
- Groups that can nest and resize
- Teachers (left) and subjects (right) drag-and-drop
- Arrow links between subjects and teachers

## Run

### Backend (serves API + frontend)
1. Create a virtual environment (optional).
2. Install dependencies:
   - `pip install -r backend/requirements.txt`
3. Start the server:
   - `python backend/app.py`
4. Open: http://localhost:5000

## Usage Notes
- Right-click a timetable to edit days and slots.
- Tables warn when no class is linked or when no group exists.
- Drop subjects into groups; teachers can be in groups or global (canvas).
- Arrow tool: click a subject then a teacher (or vice versa) to link.

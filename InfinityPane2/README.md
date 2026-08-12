# InfinityPane 🚀

An infinite canvas scheduling application for managing teachers, subjects, classes, and timetables with an intuitive visual interface.

![InfinityPane](https://via.placeholder.com/800x400/1a1a2e/4361ee?text=InfinityPane+%E2%88%9E)

## ✨ Features

### Core Features
- **🎨 Infinite 2D Canvas**: Pan and zoom in all directions with unlimited magnification (0.1x to 10x)
- **📅 Timetable Blocks**: Create customizable timetables with configurable days and time slots
- **📦 Group Blocks**: Expandable, nameable, nestable containers for organizing faculty
- **👨‍🏫 Teacher Management**: Drag teachers from sidebar to canvas/groups
- **📚 Subject Management**: Drag subjects and link them to teachers with arrows
- **🔗 Arrow Connections**: Visual links between teachers and subjects

### Timetable Features
- Default: Monday to Saturday with 8 hourly slots
- Right-click to customize:
  - Select specific days (Mon-Fri, Mon-Sat, custom)
  - Adjust slots per day (1-24)
  - Change slot duration (30/45/60/90/120 minutes)
  - Set custom start time
- Link to existing classes

### Group Features
- Drag from corners or edges to resize
- Double-click header to rename
- Automatic nesting when placed inside other groups
- Color customization via right-click menu
- Teachers in a group only work for that group's context

### Faculty Scope Rules
- **Group-scoped**: Teachers placed in a group work only for that group
- **Nested Groups**: Share faculty with parent/child groups
- **Global Teachers**: Teachers placed on the bare canvas work globally across all groups

### Additional Features I've Added
- **🔍 Search**: Search teachers by name, subject, or ID; search subjects by name or code
- **⌨️ Keyboard Shortcuts**: V(select), H(pan), A(arrow), G(group), T(timetable), Esc(cancel)
- **📊 Status Bar**: Shows current tool, hints, and canvas statistics
- **💾 Auto-save Ready**: Backend API for persisting canvas state
- **🎯 Grid Background**: Adaptive grid that changes with zoom level
- **🔄 Origin Marker**: Visual indicator for canvas center
- **📍 Coordinates Display**: Shows current canvas position
- **🖱️ Context Menus**: Right-click on any element for actions

## 🛠️ Tech Stack

### Frontend
- **React 18** - UI framework
- **Zustand** - State management
- **Lucide React** - Icons
- **CSS Variables** - Theming

### Backend
- **Flask** - Python web framework
- **Flask-CORS** - Cross-origin support

## 🚀 Quick Start

### Prerequisites
- Node.js 18+
- Python 3.8+
- npm or yarn

### Windows Quick Start (PowerShell)

1. Open PowerShell and allow local scripts if needed:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
2. Run setup (installs backend venv + frontend deps):
```powershell
cd InfinityPane2
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```
3. Start Backend (Terminal 1):
```powershell
powershell -ExecutionPolicy Bypass -File .\start-backend.ps1
```
4. Start Frontend (Terminal 2):
```powershell
powershell -ExecutionPolicy Bypass -File .\start-frontend.ps1
```

Batch wrappers are also available: `setup.bat`, `start-backend.bat`, `start-frontend.bat`.

### Linux/macOS Quick Start

1. **Clone and navigate**:
```bash
cd InfinityPane2
```

2. **Run setup script**:
```bash
chmod +x setup.sh start-backend.sh start-frontend.sh
./setup.sh
```

3. **Start Backend** (Terminal 1):
```bash
./start-backend.sh
# Or manually:
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

4. **Start Frontend** (Terminal 2):
```bash
./start-frontend.sh
# Or manually:
cd frontend
npm install
npm start
```

5. **Open browser**: http://localhost:3000

## 📖 Usage Guide

### Navigation
| Action | Method |
|--------|--------|
| Pan | Middle-click drag, Shift+drag, or H key + drag |
| Zoom | Ctrl/Cmd + Scroll wheel |
| Scroll Pan | Scroll wheel |
| Reset View | Ctrl/Cmd + 0, or click zoom percentage |

### Tools
| Tool | Shortcut | Description |
|------|----------|-------------|
| Select | V | Click to select, drag to move |
| Pan | H | Drag to pan the canvas |
| Arrow | A | Click source, then target to connect |
| Group | G | Creates a group at canvas center |
| Timetable | T | Creates a timetable at canvas center |

### Creating a Schedule

1. **Add a Group**: Press G or right-click → Add Group
2. **Name the Group**: Double-click the header
3. **Add Timetable**: Press T or right-click → Add Timetable
4. **Link Timetable to Group**: Right-click timetable → Link to Group
5. **Configure Timetable**: Right-click → Configure Days & Slots
6. **Add Teachers**: Drag from left sidebar into the group
7. **Add Subjects**: Drag from right sidebar into the group
8. **Connect**: Use Arrow tool (A) to link teachers to subjects

### Nesting Groups
1. Create a parent group (e.g., "Computer Science Department")
2. Create child groups inside it (e.g., "CS-A", "CS-B")
3. Teachers in parent group are available to all child groups
4. Teachers in child groups are scoped only to that group

### Global Teachers
- Drag a teacher to the bare canvas (outside any group)
- They'll have a 🌐 badge indicating global scope
- Connect them to subjects in any group using arrows

## 📁 Project Structure

```
InfinityPane2/
├── backend/
│   ├── app.py              # Flask API server
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── components/
│   │   │   ├── Arrows/     # Arrow connection components
│   │   │   ├── Blocks/     # Group, Timetable, Teacher, Subject blocks
│   │   │   ├── Canvas/     # Infinite canvas and grid
│   │   │   ├── Sidebar/    # Teacher and Subject sidebars
│   │   │   ├── Toolbar/    # Top toolbar
│   │   │   └── UI/         # Context menu, Modal, Status bar
│   │   ├── store/
│   │   │   └── useStore.js # Zustand state management
│   │   ├── App.js
│   │   ├── App.css
│   │   ├── index.js
│   │   └── index.css
│   └── package.json
├── setup.sh                # Setup script
├── start-backend.sh        # Backend start script
├── start-frontend.sh       # Frontend start script
└── README.md
```

## 🔌 API Endpoints

### Teachers
- `GET /api/teachers` - List all teachers (with search)
- `POST /api/teachers` - Create teacher
- `PUT /api/teachers/:id` - Update teacher
- `DELETE /api/teachers/:id` - Delete teacher

### Subjects
- `GET /api/subjects` - List all subjects (with search)
- `POST /api/subjects` - Create subject
- `PUT /api/subjects/:id` - Update subject
- `DELETE /api/subjects/:id` - Delete subject

### Classes
- `GET /api/classes` - List all classes
- `POST /api/classes` - Create class

### Canvas State
- `GET /api/canvas` - Get full canvas state
- `POST /api/canvas` - Save full canvas state
- `POST /api/canvas/groups` - Add group
- `POST /api/canvas/timetables` - Add timetable
- `POST /api/canvas/arrows` - Add arrow connection

### Validation
- `POST /api/validate/schedule` - Check for conflicts

## 🎨 Customization

### Theme Colors (CSS Variables)
Edit `frontend/src/index.css`:
```css
:root {
  --bg-primary: #0f0f23;
  --bg-secondary: #1a1a2e;
  --accent-primary: #4361ee;
  --accent-success: #06d6a0;
  --accent-warning: #ffd166;
  --accent-danger: #ef476f;
}
```

## 🔮 Future Enhancements

- [ ] Drag-and-drop subjects directly into timetable cells
- [ ] Conflict detection (teacher double-booked)
- [ ] Export to PDF/Image
- [ ] Undo/Redo history
- [ ] Collaborative editing (WebSocket)
- [ ] Minimap for large canvases
- [ ] Snap-to-grid option
- [ ] Template timetables
- [ ] Import/Export JSON
- [ ] Dark/Light theme toggle

## 📝 License

MIT License - feel free to use and modify!

---

Built with ❤️ for efficient scheduling

# InfinityPane2 AI Instructions

## Big picture
- React frontend (frontend/src) renders an infinite canvas scheduling UI; Flask backend (backend/app.py) serves a JSON API and an in-memory data store.
- State lives in a single Zustand store in [frontend/src/store/useStore.js](frontend/src/store/useStore.js); canvas components read/write only via this store.
- Frontend API base is `/api` with a CRA proxy to `http://localhost:5000` (see [frontend/package.json](frontend/package.json)).

## Current feature set (2026-02)
- Timetables support class-linked subjects with per-class total weeks and per-subject hours; edit via “Class Subjects” modal or drawer.
- Teachers are assigned to class subjects by drawing an arrow from a teacher placement onto a subject row; assignments render dashed arrows from teacher → subject drawer rows.
- Timetable cells are draggable (swap/move), double-click to lock/unlock, and right‑click to edit/clear.
- Locked elements pan the canvas instead of moving; lock toggle appears on all blocks.
- Warnings panel in the teacher sidebar aggregates group/placement/schedule inconsistencies and teacher slot conflicts.
- Auto-scheduler fills timetables based on total weeks and subject hours, respecting locked cells and preventing teacher collisions.
 - Per-day regenerate is available via right-click on a day header.
 - Copy/Cut/Paste supported for blocks: Ctrl+C, Ctrl+X, Ctrl+V (paste at cursor).
 - Assigned teachers list exists in the Teacher sidebar; click to center and highlight the teacher placement.
 - Warnings are clickable and highlight the relevant element with a blinking cyan outline.

## Key flows & boundaries
- Backend exposes teachers/subjects/classes and canvas state in [backend/app.py](backend/app.py) (`/api/teachers`, `/api/subjects`, `/api/classes`, `/api/canvas`, `/api/validate/schedule`).
- Canvas persistence is best-effort: `saveToBackend()`/`loadFromBackend()` in [frontend/src/store/useStore.js](frontend/src/store/useStore.js) include groups/timetables/arrows/placements + classSubjects/classWeeks; other UI state is client-only.
- Drag & drop from sidebars uses `dataTransfer` with JSON payloads (see [frontend/src/components/Sidebar/TeacherSidebar.js](frontend/src/components/Sidebar/TeacherSidebar.js) and [frontend/src/components/Sidebar/SubjectSidebar.js](frontend/src/components/Sidebar/SubjectSidebar.js)); canvas drop handlers should parse that shape.
- Timetable slot drag/drop uses `dataTransfer` with `{ type: 'timetable-cell', timetableId, cellKey }` payload; handled inside [frontend/src/components/Blocks/TimetableBlock.js](frontend/src/components/Blocks/TimetableBlock.js).
- Teacher → subject assignment uses arrow drawing and row hover tracking; assignment is finalized on mouse up in [frontend/src/components/Canvas/InfiniteCanvas.js](frontend/src/components/Canvas/InfiniteCanvas.js).
 - Class drag/drop from the Classes list creates a linked timetable at the drop location.

## Developer workflows
- One-time setup: run `./setup.sh` (creates venv, installs pip deps, installs npm deps).
- Start backend: `./start-backend.sh` (Flask on :5000).
- Start frontend: `./start-frontend.sh` (CRA on :3000).

## Project-specific conventions
- When mutating canvas entities (groups, timetables, arrows, placements, blocks), call `pushHistory()` to keep undo/redo consistent (see store actions in [frontend/src/store/useStore.js](frontend/src/store/useStore.js)). For drag/resize, use `update*` with `{ skipHistory: true }` during movement and `pushHistory()` on mouseup.
- Canvas interactions (zoom, pan, selection, arrow drawing) are centralized in [frontend/src/components/Canvas/InfiniteCanvas.js](frontend/src/components/Canvas/InfiniteCanvas.js); keep new interaction logic there to avoid scattered event handlers.
- IDs are generated client-side with `generateId()`; backend uses `uuid` for API-created items (teachers/subjects/classes/groups).
- Backend is in-memory only; do not assume persistence across server restarts unless you add a database.
- Locking: all blocks expose `locked` flag; locked items do not move and instead pan the canvas. Toggle via lock button or context menu.
- Timetable warnings: `computeWarnings()` in the store returns structured warning objects `{ type, timetableId?, targetType?, targetId?, message }` and is used by the warnings panel and timetable header icon.
- Drag/drop of timetable cells locks the destination cell and preserves locked slots during auto-schedule.

## Integration points
- UI composition in [frontend/src/App.js](frontend/src/App.js): toolbar, sidebars, infinite canvas, context menu, modal, status bar.
- Blocks/arrows live under [frontend/src/components/Blocks](frontend/src/components/Blocks) and [frontend/src/components/Arrows](frontend/src/components/Arrows); follow existing prop shapes from store entities.
- Timetable scheduling engine lives in `generateSchedule()` in [frontend/src/store/useStore.js](frontend/src/store/useStore.js). Trigger via bottom-right “Auto‑Schedule” button in the canvas.
- Timetable cell editing modal is `editSlot` in [frontend/src/components/UI/Modal.js](frontend/src/components/UI/Modal.js).
- Class-subject arrows are rendered by [frontend/src/components/Arrows/ClassSubjectArrowConnection.js](frontend/src/components/Arrows/ClassSubjectArrowConnection.js) and only shown when the drawer is open.

## Scheduling engine design (current)
- Global occupancy map prevents a teacher from being in two places at once.
- Phase 1: seed all locked slots and fail immediately on teacher collisions.
- Phase 2: sort remaining subject allocations by difficulty (shared teachers + remaining slots).
- Phase 3: recursive backtracking assigns subjects to day/slot with constraints:
	- slot empty and not locked
	- teacher not occupied at that day/slot
	- max 2 per day per subject
	- soft scoring to reduce gaps and distribute subjects across the week
- If no valid placement exists, returns warnings suggesting changing weeks/hours.

## Keyboard shortcuts
- Undo: Ctrl+Z
- Redo: Ctrl+Y
- Copy/Cut/Paste: Ctrl+C / Ctrl+X / Ctrl+V
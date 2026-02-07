# InfinityPane2 — Scheduling Canvas Module

InfinityPane2 is a standalone module of a larger scheduling system. It provides an infinite‑canvas UI for building class timetables, assigning teachers to class subjects, and auto‑generating schedules with constraints. The backend is a lightweight Flask API with in‑memory data; the frontend is a React app with a single Zustand store.

> This repository is meant to be embedded into a larger product. Treat it as a feature‑complete scheduling canvas module with clear integration points.

---

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Key Concepts](#key-concepts)
- [Scheduling Engine](#scheduling-engine)
- [Warnings & Validation](#warnings--validation)
- [UI Interactions](#ui-interactions)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Data Model](#data-model)
- [API Endpoints (Flask)](#api-endpoints-flask)
- [Persistence](#persistence)
- [Development](#development)
- [Integration Notes](#integration-notes)
- [Limitations](#limitations)

---

## Overview
InfinityPane2 provides:
- An infinite canvas UI for groups, timetables, teachers, subjects, and structural blocks.
- Class‑subject definitions (name, hours, total weeks) per class.
- Teacher assignment to class subjects via arrow connections.
- Auto‑schedule with backtracking and constraints.
- Manual editing and locking of timetable cells.
- Warning system with clickable highlights.

---

## Architecture
**Frontend (React + Zustand)**
- UI: `frontend/src` (blocks, canvas, toolbars, sidebars, modals).
- State: single store at `frontend/src/store/useStore.js`.

**Backend (Flask)**
- API: `backend/app.py`.
- In‑memory store only (no persistence across restarts).

---

## Key Concepts
### Groups
- Hierarchical containers for organizing timetables and placements.
- Nested groups are allowed (parent/child structure).

### Timetables
- Grid of days × slots.
- Linked to a class.
- Supports per‑day regeneration and full auto‑schedule.

### Class Subjects
- Each class has:
  - Total weeks
  - List of subjects (name, hours, optional teacher)
- Managed via the “Class Subjects” drawer/modal.

### Teacher Assignments
- Teachers are placed onto the canvas.
- An arrow from teacher → class subject row assigns the teacher.
- Assignments update timetable cells with the teacher’s name.

---

## Scheduling Engine
The scheduler is implemented in the store (`generateSchedule()` in `frontend/src/store/useStore.js`). It uses a global backtracking approach, not per‑timetable scheduling.

### Phase 1 — Locked Slot Seeding
- All locked slots are seeded into the global occupancy map.
- If a teacher is locked in two timetables at the same time/day, the scheduler stops with a fatal error.

### Phase 2 — Difficulty Sorting
Subjects are sorted by difficulty based on:
- Remaining slots required
- Teacher sharing intensity (a teacher used across many classes)

### Phase 3 — Recursive Backtracking
For each subject allocation:
- Find valid day/slot combinations where:
  - Slot is empty and not locked
  - Teacher is free in global occupancy map
  - Subject doesn’t exceed max per day (default: 2)
- Score slots to reduce gaps and distribute across the week.
- Backtrack if no valid configuration exists.

If no solution is found, warnings suggest:
- Increasing total weeks
- Reducing subject hours

---

## Warnings & Validation
Warnings are computed via `computeWarnings()` and surfaced in:
- Teacher sidebar warnings panel
- Timetable header warning icon

Warnings are clickable and will:
- Center the canvas on the relevant element
- Highlight it with a blinking cyan outline

Warning types include:
- Ungrouped placements
- Teacher/group mismatches
- Teacher conflicts in the same day/slot

---

## UI Interactions
### Drag & Drop
- Teachers/Subjects: drag from sidebars onto canvas or groups.
- Classes: drag from Classes list to create a linked timetable.
- Timetable cells: drag to swap/move (destination becomes locked).

### Timetable Cells
- Double‑click: lock/unlock (can lock empty slots).
- Right‑click: edit slot (subject + teacher), clear, lock.

### Locking
- All elements can be locked (button or context menu).
- Locked elements pan the canvas instead of moving.

---

## Keyboard Shortcuts
- Undo: Ctrl+Z
- Redo: Ctrl+Y
- Copy: Ctrl+C
- Cut: Ctrl+X
- Paste: Ctrl+V (paste at cursor)

---

## Data Model
### Timetable Cell
```js
{
  subjectId,
  subjectName,
  teacherId,
  teacherName,
  locked: boolean,
  empty: boolean
}
```

### Class Subject
```js
{
  id,
  name,
  hours,
  teacherId
}
```

### Warning
```js
{
  type,
  timetableId?,
  targetType?,
  targetId?,
  message
}
```

---

## API Endpoints (Flask)
Base: `/api`

- `GET /teachers` — list teachers
- `POST /teachers` — create teacher
- `PUT /teachers/:id` — update teacher
- `DELETE /teachers/:id` — delete teacher

- `GET /subjects` — list subjects
- `POST /subjects` — create subject
- `PUT /subjects/:id` — update subject
- `DELETE /subjects/:id` — delete subject

- `GET /classes` — list classes
- `POST /classes` — create class

- `GET /canvas` — get canvas state
- `POST /canvas` — save canvas state

---

## Persistence
Canvas state is saved via `saveToBackend()` and restored with `loadFromBackend()`.
It includes:
- Groups, timetables, arrows, placements
- Class subjects and total weeks

Non‑persistent UI state remains client‑side.

---

## Development
### Setup
```bash
./setup.sh
```

### Start Backend
```bash
./start-backend.sh
```

### Start Frontend
```bash
./start-frontend.sh
```

---

## Integration Notes
- This repo is intended as a module of a larger system.
- The frontend is self‑contained; you can embed it as a micro‑frontend or reuse the core store and components.
- The backend is in‑memory only. Replace Flask with your system’s persistence layer when integrating.

---

## Limitations
- No database persistence (backend is in‑memory).
- Scheduling is weekly with fixed slots; no variable slot duration per subject.
- Subject/teacher matching is based on assignment, not on subject compatibility.

---

If you need additional integration hooks or a more granular schedule API, extend the store or backend endpoints accordingly.

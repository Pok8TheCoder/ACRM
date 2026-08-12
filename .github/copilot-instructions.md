# ACRM Copilot Instructions

## Architecture & Context
- [app.py](app.py) boots Flask, immediately runs `init_db()` (drops/rebuilds student tables when `load_samples=True`), then `register_blueprints`; keep imports minimal to avoid accidental resets.
- Blueprints live in [routes/](routes) with strict `_require_*_role()` checks and url prefixes (`/student`, `/faculty`, `/admin`, `/principal`, `/api/principal`). Marketing pages are in [routes/home.py](routes/home.py) + [templates/*.html](templates), while role workflows live under [templates/<role>/](templates).
- Institutions are isolated under `institutions/<id>/` containing `Master_Admin.db`, `student/student.db`, `faculty/faculty.db`, and data roots; always open SQLite via `routes.database.get_db_connection(institution_id, role)` so row factories and commit/rollback semantics match the helpers.

## Persistence & Helpers
- Centralize all reads/writes through [routes/database.py](routes/database.py): reuse helpers like `get_student_subjects`, `get_class_faculty_assignments`, `create_subject_chapter`, `ensure_campus_floors`, `reset_campus_layout`, `create_timetable_run`, and timetable utilities instead of ad-hoc SQL.
- `init_db()` + `_migrate_databases()` manage schema; never call `init_db()` inside requests—use the admin reset API or delete the institution folder. Extend `_migrate_databases()` when adding columns so existing institutions upgrade in-place.
- Subject storage uses `get_subject_storage_path` and `_sanitize_relative_path`; upload paths must go through `secure_filename`, and API payloads must strip `file_path` (preview/download URLs come from `_build_resource_preview_payload`).
- Two faculty schemas exist: the student DB holds `faculty` used for class mapping, while the faculty DB holds `faculties`/`class_faculty`/`assignments`; pick the helper that matches the caller’s database context.

## Auth & Sessions
- Login flows in [routes/home.py](routes/home.py) call `verify_student|faculty|admin|principal`, then stash `user_id`, `role`, `institution_id`, `user_name`, plus `class_id`/`program_id` for students. Principal in session uses role `master_admin` for API guards.
- All protected APIs return `401` with `{'error': 'Unauthorized'}` on guard failure; always pass `institution_id` from session into DB/FS helpers to maintain isolation.

## Role Workflows
- Student ([routes/student.py](routes/student.py)): dashboards plus JSON for subjects → chapters → resources. Always gate with `is_subject_accessible_to_student`; strip `file_path`, add download URLs via `url_for`, and 404 when subjects/chapters are missing.
- Faculty ([routes/faculty.py](routes/faculty.py)): resources browser with multi-file/folder uploads; previews determined by `_detect_preview_type` and capped text previews (200 KB). Use `get_subject_chapter` and `create_subject_chapter` to keep chapter linkage intact; stream via `/stream` and `/text-preview` endpoints rather than exposing paths.
- Admin ([routes/admin.py](routes/admin.py)): programs/semesters/classes, students/faculty CRUD, subject CRUD, subject → faculty/class assignments, campus layout (`ensure_campus_floors`, `create_campus_sections`, `create_campus_room`, `reset_campus_layout`, CSV import/export), and timetable runs. Respect room/home-room validations and reuse layout/timetable helpers so Principal views stay consistent.
- Principal ([routes/principal.py](routes/principal.py)): manages admin accounts/permissions in Master_Admin DB; never mix student/faculty DBs here.

## Timetable Engine
- [routes/timetable_engine.py](routes/timetable_engine.py) processes `timetable_runs`: loads rooms (`get_campus_rooms`), class batches (auto-splits by `MAX_LAB_BATCH_SIZE`), and faculty-class-subject assignments. Honors targeting/focus settings, faculty teaching metadata/majors, and slot/break config; writes entries via `replace_timetable_entries` and snapshots summary into run config.

## Data Seeding & Resets
- Quick seed: [scripts/generate_sample_data.py](scripts/generate_sample_data.py) can wipe (`RESET_INSTITUTION=True`) and rebuild programs/semesters, campus rooms, classes with home rooms, students, and subjects with teaching-hour breakdowns. Run with `python scripts/generate_sample_data.py` (ensures `PROJECT_ROOT` on `sys.path`).
- Runtime reset: POST `/admin/api/reset-institution` (admin session) or delete `institutions/<id>/` and restart; avoids calling `init_db()` mid-request.

## Development Workflow
- Install with `pip install -r requirements.txt`; run dev server via `python app.py` (debug on). Sample credentials: `STD001/password123`, `FAC001/faculty123`, `ADM001/admin123`, `PRI001/principal123` (default `iit_delhi`).
- No automated tests—verify via role dashboards (`/student/dashboard`, `/faculty/resources`, `/admin/dashboard`, `/principal/dashboard`) and JSON APIs. Keep Tailwind-style utilities inline within [templates](templates) and mirror existing directory layout when adding views.

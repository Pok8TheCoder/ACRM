/**
 * Left sidebar — faculty list, class list, and CSV import panel.
 * Faculty cards are draggable onto timetable cells.
 * Class cards can be dropped onto the canvas to create a new timetable.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Users, BookOpen, Upload } from 'lucide-react'
import useCanvasStore from '../store/canvasStore'
import ImportPanel from './ImportPanel'
import './Sidebar.css'

function FacultyCard({ faculty }) {
  const onDragStart = useCallback((e) => {
    e.dataTransfer.setData('application/x-ip3', JSON.stringify({ type: 'faculty', item: faculty }))
    e.dataTransfer.effectAllowed = 'copy'
  }, [faculty])

  const scorePercent = Math.min(100, Math.round(faculty.match_score || 0))
  const scoreColor = scorePercent >= 75 ? 'var(--success)' : scorePercent >= 50 ? 'var(--warning)' : 'var(--danger)'

  return (
    <div className="faculty-card" draggable onDragStart={onDragStart} title={`Drag onto a timetable cell`}>
      <div className="faculty-name">{faculty.name}</div>
      <div className="faculty-id">{faculty.id}</div>
      <div className="faculty-subjects">
        {(faculty.majors || []).slice(0, 3).map(m => (
          <span key={m} className="faculty-subject-pill" title={m}>{m}</span>
        ))}
        {(faculty.majors || []).length > 3 && (
          <span className="faculty-subject-pill">+{faculty.majors.length - 3}</span>
        )}
      </div>
      <div className="faculty-score-bar">
        <div className="faculty-score-fill" style={{ width: `${scorePercent}%`, background: scoreColor }} />
      </div>
    </div>
  )
}

function ClassCard({ cls }) {
  const onDragStart = useCallback((e) => {
    e.dataTransfer.setData('application/x-ip3', JSON.stringify({ type: 'class', item: cls }))
    e.dataTransfer.effectAllowed = 'copy'
  }, [cls])

  const { addTimetableNode } = useCanvasStore()
  const handleAdd = useCallback(() => {
    addTimetableNode(cls.id, cls.name, { x: Math.random() * 400, y: Math.random() * 300 })
  }, [cls, addTimetableNode])

  return (
    <div className="class-card" draggable onDragStart={onDragStart} title="Drag to canvas or click + to add">
      <div className="class-card-info">
        <div className="class-name">{cls.name}</div>
        <div className="class-meta">
          {cls.program_code && `${cls.program_code} · `}Sem {cls.semester_number} · {cls.total_students || '?'} students
        </div>
      </div>
      <div className="class-add-btn" onClick={handleAdd} title="Add timetable to canvas">+</div>
    </div>
  )
}

export default function LeftSidebar() {
  const { faculty, classes, fetchFaculty, fetchClasses, leftPanelTab, setLeftPanelTab, facultyLoading, classesLoading } = useCanvasStore()
  const [facultySearch, setFacultySearch] = useState('')
  const [classSearch, setClassSearch] = useState('')
  const searchTimer = useRef(null)

  useEffect(() => {
    fetchFaculty()
    fetchClasses()
  }, [])

  const handleFacultySearch = (e) => {
    const val = e.target.value
    setFacultySearch(val)
    clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => fetchFaculty(val), 300)
  }

  const filteredClasses = classSearch
    ? classes.filter(c => c.name.toLowerCase().includes(classSearch.toLowerCase()) || (c.program_code || '').toLowerCase().includes(classSearch.toLowerCase()))
    : classes

  return (
    <div className="sidebar">
      {/* Tab bar */}
      <div className="sidebar-tabs">
        <div className={`sidebar-tab ${leftPanelTab === 'faculty' ? 'active' : ''}`} onClick={() => setLeftPanelTab('faculty')}>
          <Users size={11} style={{ display: 'inline', marginRight: 3 }} />Faculty
        </div>
        <div className={`sidebar-tab ${leftPanelTab === 'classes' ? 'active' : ''}`} onClick={() => setLeftPanelTab('classes')}>
          <BookOpen size={11} style={{ display: 'inline', marginRight: 3 }} />Classes
        </div>
        <div className={`sidebar-tab ${leftPanelTab === 'import' ? 'active' : ''}`} onClick={() => setLeftPanelTab('import')}>
          <Upload size={11} style={{ display: 'inline', marginRight: 3 }} />Import
        </div>
      </div>

      {/* Faculty tab */}
      {leftPanelTab === 'faculty' && (
        <>
          <div className="sidebar-header">
            <div className="sidebar-title">
              <h3><Users size={12} /> Faculty</h3>
              <span className="sidebar-count">{faculty.length}</span>
            </div>
            <input
              className="sidebar-search"
              placeholder="Search by name, ID, major…"
              value={facultySearch}
              onChange={handleFacultySearch}
            />
          </div>
          <div className="sidebar-list">
            {facultyLoading && <div className="empty-state">Loading…</div>}
            {!facultyLoading && faculty.length === 0 && (
              <div className="empty-state">No faculty found.<br />Check ACRM data or search query.</div>
            )}
            {faculty.map(f => <FacultyCard key={f.id} faculty={f} />)}
          </div>
        </>
      )}

      {/* Classes tab */}
      {leftPanelTab === 'classes' && (
        <>
          <div className="sidebar-header">
            <div className="sidebar-title">
              <h3><BookOpen size={12} /> Classes</h3>
              <span className="sidebar-count">{classes.length}</span>
            </div>
            <input
              className="sidebar-search"
              placeholder="Search class or program…"
              value={classSearch}
              onChange={e => setClassSearch(e.target.value)}
            />
          </div>
          <div className="sidebar-list">
            {classesLoading && <div className="empty-state">Loading…</div>}
            {filteredClasses.map(c => <ClassCard key={c.id} cls={c} />)}
            {!classesLoading && filteredClasses.length === 0 && (
              <div className="empty-state">No classes found.</div>
            )}
          </div>
        </>
      )}

      {/* Import tab */}
      {leftPanelTab === 'import' && <ImportPanel />}
    </div>
  )
}

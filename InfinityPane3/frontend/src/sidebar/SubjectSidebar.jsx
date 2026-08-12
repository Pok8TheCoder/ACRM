/**
 * Right sidebar — subject list (draggable onto timetable cells).
 */

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { BookMarked } from 'lucide-react'
import useCanvasStore from '../store/canvasStore'
import './Sidebar.css'

function SubjectCard({ subject, color }) {
  const onDragStart = useCallback((e) => {
    const item = { ...subject, color }
    e.dataTransfer.setData('application/x-ip3', JSON.stringify({ type: 'subject', item }))
    e.dataTransfer.effectAllowed = 'copy'
  }, [subject, color])

  return (
    <div
      className="subject-card"
      draggable
      onDragStart={onDragStart}
      style={{ '--card-color': color }}
      title={`Drag onto a timetable cell — requires lab: ${subject.requires_lab ? 'Yes (will span 2 slots)' : 'No'}`}
    >
      <style>{`.subject-card { } .subject-card::before { background: ${color}; }`}</style>
      <div className="subject-name">{subject.name}</div>
      <div className="subject-code">{subject.code}</div>
      <div className="subject-badges">
        {subject.requires_lab && <span className="badge accent">Lab</span>}
        {subject.has_practical && !subject.requires_lab && <span className="badge">Practical</span>}
        {subject.delivery_mode && subject.delivery_mode !== 'theory' && (
          <span className="badge">{subject.delivery_mode}</span>
        )}
        {subject.theory_hours > 0 && (
          <span className="badge">{subject.theory_hours}h theory</span>
        )}
      </div>
    </div>
  )
}

export default function SubjectSidebar() {
  const { subjects, fetchSubjects, subjectsLoading, getSubjectColor } = useCanvasStore()
  const [search, setSearch] = useState('')
  const timer = useRef(null)

  useEffect(() => { fetchSubjects() }, [])

  const handleSearch = (e) => {
    const val = e.target.value
    setSearch(val)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => fetchSubjects(val), 300)
  }

  return (
    <div className="sidebar right">
      <div className="sidebar-header">
        <div className="sidebar-title">
          <h3><BookMarked size={12} /> Subjects</h3>
          <span className="sidebar-count">{subjects.length}</span>
        </div>
        <input
          className="sidebar-search"
          placeholder="Search subjects…"
          value={search}
          onChange={handleSearch}
        />
      </div>
      <div className="sidebar-list">
        {subjectsLoading && <div className="empty-state">Loading…</div>}
        {!subjectsLoading && subjects.length === 0 && (
          <div className="empty-state">No subjects found.</div>
        )}
        {subjects.map(s => (
          <SubjectCard key={s.id} subject={s} color={getSubjectColor(s.id)} />
        ))}
      </div>
    </div>
  )
}

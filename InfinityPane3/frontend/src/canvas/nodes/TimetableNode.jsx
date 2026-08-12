/**
 * TimetableNode — React Flow custom node for a class timetable.
 *
 * Key features:
 *  - Grid of days × time slots, rendered as a CSS Grid
 *  - Lab block support: cells with slot_span > 1 span multiple rows
 *  - Drag-over highlighting: accept faculty/subject drops from sidebar
 *  - Conflict detection: same faculty double-booked turns cell red
 *  - Break rows: visually distinct "break" slots
 *  - Cell clear on click × button
 */

import React, { useState, useCallback, useMemo } from 'react'
import { NodeResizer, useReactFlow } from '@xyflow/react'
import { Calendar, Trash2, Settings, Lock } from 'lucide-react'
import useCanvasStore from '../../store/canvasStore'
import useCollabStore from '../../store/collabStore'
import './TimetableNode.css'

// ── helpers ────────────────────────────────────────────────────────────────────

function slotTime(startTime, slotIndex, slotDuration) {
  const [h, m] = startTime.split(':').map(Number)
  const totalMin = h * 60 + m + slotIndex * slotDuration
  const hh = String(Math.floor(totalMin / 60) % 24).padStart(2, '0')
  const mm = String(totalMin % 60).padStart(2, '0')
  return `${hh}:${mm}`
}

// Detect conflicting cells: same faculty assigned to 2+ cells in same slot
function detectConflicts(cells) {
  // group by slot index
  const slotMap = {}
  for (const [key, val] of Object.entries(cells)) {
    if (!val) continue
    const slotIdx = key.split('-').slice(-1)[0]
    if (!slotMap[slotIdx]) slotMap[slotIdx] = []
    slotMap[slotIdx].push({ key, faculty_id: val.faculty_id })
  }

  const conflictKeys = new Set()
  for (const entries of Object.values(slotMap)) {
    const seen = {}
    for (const { key, faculty_id } of entries) {
      if (seen[faculty_id]) {
        conflictKeys.add(key)
        conflictKeys.add(seen[faculty_id])
      } else {
        seen[faculty_id] = key
      }
    }
  }
  return conflictKeys
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function TimetableNode({ id, data, selected }) {
  const { deleteElements } = useReactFlow()
  const { assignCell, clearCell } = useCanvasStore()
  const { nodeLocks } = useCollabStore()

  const [dragOverCell, setDragOverCell] = useState(null)

  const {
    class_id,
    class_name,
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
    slots_per_day = 8,
    slot_duration = 60,
    start_time = '09:00',
    break_slots = [],
    cells = {},
    lab_spans = {},
  } = data

  const lock = nodeLocks[id]

  // All slot indices including breaks
  const allSlots = useMemo(() => {
    const arr = []
    for (let i = 0; i < slots_per_day; i++) arr.push(i)
    return arr
  }, [slots_per_day])

  // Compute conflict keys for red highlighting
  const conflictKeys = useMemo(() => detectConflicts(cells), [cells])

  // Track which cells are "consumed" by spanning cells above
  const consumedCells = useMemo(() => {
    const set = new Set()
    for (const [key, span] of Object.entries(lab_spans)) {
      if (span <= 1) continue
      const [day, slotStr] = key.split(/-(?=[^-]+$)/)  // split on last '-'
      const slotIdx = parseInt(slotStr, 10)
      for (let i = 1; i < span; i++) {
        set.add(`${day}-${slotIdx + i}`)
      }
    }
    return set
  }, [lab_spans])

  // ── drag handlers on cells ─────────────────────────────────────────────────

  const handleCellDragOver = useCallback((e, cellKey) => {
    const data = e.dataTransfer.getData('application/x-ip3')
    if (!data && !e.dataTransfer.types.includes('application/x-ip3')) return
    e.preventDefault()
    setDragOverCell(cellKey)
  }, [])

  const handleCellDragLeave = useCallback(() => {
    setDragOverCell(null)
  }, [])

  const handleCellDrop = useCallback((e, day, slotIdx) => {
    e.preventDefault()
    e.stopPropagation()
    setDragOverCell(null)

    let payload
    try {
      payload = JSON.parse(e.dataTransfer.getData('application/x-ip3'))
    } catch {
      return
    }

    const cellKey = `${day}-${slotIdx}`

    if (payload.type === 'faculty') {
      // Faculty dropped alone — keep existing subject or prompt
      const existing = cells[cellKey]
      const assignment = {
        faculty_id: payload.item.id,
        faculty_name: payload.item.name,
        subject_id: existing?.subject_id || '',
        subject_code: existing?.subject_code || '',
        subject_name: existing?.subject_name || '',
        room_id: existing?.room_id || null,
        room_number: existing?.room_number || null,
        color: existing?.color || '#6366f1',
        conflict: false,
      }
      assignCell(id, cellKey, assignment, lab_spans[cellKey] || 1)
    } else if (payload.type === 'subject') {
      // Subject dropped — keep existing faculty or leave blank
      const existing = cells[cellKey]
      const slotSpan = payload.item.requires_lab ? 2 : 1
      const assignment = {
        faculty_id: existing?.faculty_id || '',
        faculty_name: existing?.faculty_name || '',
        subject_id: payload.item.id,
        subject_code: payload.item.code,
        subject_name: payload.item.name,
        room_id: existing?.room_id || null,
        room_number: existing?.room_number || null,
        color: payload.item.color || '#6366f1',
        conflict: false,
      }
      assignCell(id, cellKey, assignment, slotSpan)
    } else if (payload.type === 'faculty+subject') {
      // Combined drop (from sidebar "assign" button or future feature)
      assignCell(id, cellKey, payload.assignment, payload.slot_span || 1)
    }
  }, [id, cells, lab_spans, assignCell])

  const handleClearCell = useCallback((e, cellKey) => {
    e.stopPropagation()
    clearCell(id, cellKey)
  }, [id, clearCell])

  const handleDeleteNode = useCallback(() => {
    deleteElements({ nodes: [{ id }] })
  }, [id, deleteElements])

  // ── Stats ──────────────────────────────────────────────────────────────────
  const totalSlots = days.length * (slots_per_day - break_slots.length)
  const filledSlots = Object.values(cells).filter(Boolean).length
  const conflictCount = conflictKeys.size

  // ── Grid column template: time label + one col per day ────────────────────
  const gridTemplate = `52px repeat(${days.length}, minmax(110px, 1fr))`

  return (
    <div
      className={`tt-node ${selected ? 'selected' : ''} ${lock ? 'locked' : ''}`}
      style={{ position: 'relative' }}
    >
      <NodeResizer
        minWidth={400}
        minHeight={200}
        isVisible={selected}
        lineStyle={{ border: '1.5px solid var(--accent)' }}
        handleStyle={{ background: 'var(--accent)', border: 'none', borderRadius: '3px' }}
      />

      {/* Lock overlay */}
      {lock && (
        <div className="tt-lock-overlay">
          <div className="tt-lock-badge">
            <Lock size={10} />
            {lock.userName}
          </div>
        </div>
      )}

      {/* Header — drag handle for React Flow */}
      <div className="tt-header nodrag" style={{ cursor: 'default' }}>
        <div className="tt-icon"><Calendar size={15} /></div>
        <div className="tt-class-name" title={class_name || class_id}>
          {class_name || class_id || 'Unnamed Class'}
        </div>
        <div className="tt-meta">
          <span className="tt-meta-item">{days.length}d</span>
          <span className="tt-meta-item">×</span>
          <span className="tt-meta-item">{slots_per_day}s</span>
        </div>
        <div className="tt-actions">
          <div className="tt-action-btn danger" onClick={handleDeleteNode} title="Delete timetable">
            <Trash2 size={13} />
          </div>
        </div>
      </div>

      {/* Grid */}
      <div className="tt-grid-wrapper nodrag">
        <div
          className="tt-grid"
          style={{ gridTemplateColumns: gridTemplate }}
        >
          {/* Day header row */}
          <div className="tt-corner">Time</div>
          {days.map(day => (
            <div key={day} className="tt-day-cell">{day.slice(0, 3)}</div>
          ))}

          {/* Slot rows */}
          {allSlots.map(slotIdx => {
            const isBreak = break_slots.includes(slotIdx)
            const timeLabel = slotTime(start_time, slotIdx, slot_duration)

            return (
              <React.Fragment key={slotIdx}>
                {/* Time label */}
                <div className={`tt-time-label ${isBreak ? 'break-label' : ''}`}>
                  {isBreak ? 'BRK' : timeLabel}
                </div>

                {/* Day cells */}
                {days.map(day => {
                  const cellKey = `${day}-${slotIdx}`

                  // Skip cells consumed by a spanning lab above
                  if (consumedCells.has(cellKey)) return null

                  const assignment = cells[cellKey]
                  const span = lab_spans[cellKey] || 1
                  const isDragOver = dragOverCell === cellKey
                  const isConflict = conflictKeys.has(cellKey)

                  return (
                    <div
                      key={cellKey}
                      className={[
                        'tt-cell',
                        assignment ? '' : 'empty',
                        isBreak ? 'break-row' : '',
                        isDragOver ? 'drag-over' : '',
                        isConflict ? 'conflict' : '',
                        span > 1 ? 'lab-block' : '',
                      ].join(' ')}
                      style={span > 1 ? { gridRow: `span ${span}` } : undefined}
                      onDragOver={!isBreak ? e => handleCellDragOver(e, cellKey) : undefined}
                      onDragLeave={!isBreak ? handleCellDragLeave : undefined}
                      onDrop={!isBreak ? e => handleCellDrop(e, day, slotIdx) : undefined}
                    >
                      {/* Drop hint */}
                      {!assignment && !isBreak && (
                        <div className="tt-cell-hint">Drop here</div>
                      )}

                      {/* Assignment card */}
                      {assignment && (
                        <div
                          className="tt-assignment"
                          style={{ background: assignment.color || '#6366f1' }}
                          title={`${assignment.subject_name} — ${assignment.faculty_name}`}
                        >
                          <div className="tt-assignment-subject">{assignment.subject_code || assignment.subject_id}</div>
                          <div className="tt-assignment-faculty">{assignment.faculty_name}</div>
                          <div className="tt-assignment-meta">
                            {assignment.room_number && (
                              <span className="tt-assignment-room">🏛 {assignment.room_number}</span>
                            )}
                            {span > 1 && <span className="tt-lab-badge">LAB×{span}</span>}
                            {isConflict && <span className="tt-conflict-dot" title="Scheduling conflict" />}
                          </div>
                          {/* Clear button */}
                          <div className="tt-cell-clear" onClick={e => handleClearCell(e, cellKey)}>×</div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </React.Fragment>
            )
          })}
        </div>
      </div>

      {/* Footer */}
      <div className="tt-footer">
        <span className="tt-stat">
          <strong>{filledSlots}</strong> / {totalSlots} filled
        </span>
        {conflictCount > 0 && (
          <span className="tt-stat" style={{ color: 'var(--danger)' }}>
            ⚠ {conflictCount} conflict{conflictCount > 1 ? 's' : ''}
          </span>
        )}
        <span className="tt-stat mono" style={{ fontSize: '10px' }}>
          {class_id}
        </span>
      </div>
    </div>
  )
}

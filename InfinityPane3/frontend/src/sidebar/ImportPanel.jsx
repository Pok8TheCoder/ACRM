/**
 * ImportPanel — CSV bulk import with drag-drop zone.
 * Sends file to /api/import/csv, previews result, then applies to canvas.
 */

import React, { useState, useRef, useCallback } from 'react'
import { FileUp, CheckCircle2, AlertTriangle, Download } from 'lucide-react'
import useCanvasStore from '../store/canvasStore'
import './Sidebar.css'

const CSV_TEMPLATE = `faculty_id,subject_code,class_id,day,slot,slot_span,room_id
FAC001,CS101,CSE-1A,Monday,0,1,R101
FAC002,CS102_LAB,CSE-1B,Tuesday,2,2,LAB-A`

function downloadTemplate() {
  const blob = new Blob([CSV_TEMPLATE], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'ip3_import_template.csv'
  a.click()
  URL.revokeObjectURL(url)
}

export default function ImportPanel() {
  const { institutionId, applyCanvasPatch } = useCanvasStore()
  const [dragOver, setDragOver] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const fileInput = useRef(null)

  const processFile = useCallback(async (file) => {
    if (!file) return
    setLoading(true)
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch(
        `/api/import/csv?institution_id=${encodeURIComponent(institutionId)}&mode=preview`,
        { method: 'POST', body: formData }
      )
      const data = await res.json()
      setResult(data)
    } catch (e) {
      setResult({ error: e.message })
    } finally {
      setLoading(false)
    }
  }, [institutionId])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) processFile(file)
  }, [processFile])

  const handleApply = useCallback(() => {
    if (!result?.canvas_patch) return
    applyCanvasPatch(result.canvas_patch)
    setResult(null)
  }, [result, applyCanvasPatch])

  return (
    <div className="import-panel">
      {/* Dropzone */}
      <div
        className={`import-dropzone ${dragOver ? 'over' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInput.current?.click()}
      >
        <input
          ref={fileInput}
          type="file"
          accept=".csv,.xlsx"
          style={{ display: 'none' }}
          onChange={e => processFile(e.target.files[0])}
        />
        <div className="import-dropzone-icon">📋</div>
        <div className="import-dropzone-text">
          {loading ? 'Validating…' : 'Drop CSV / XLSX here'}
        </div>
        <div className="import-dropzone-hint">or click to browse</div>
      </div>

      <div className="import-template-link" onClick={downloadTemplate}>
        <Download size={10} style={{ display: 'inline', marginRight: 3 }} />
        Download template CSV
      </div>

      {/* Format guide */}
      <div style={{ fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.6 }}>
        <strong style={{ color: 'var(--text-secondary)' }}>Required columns:</strong><br />
        faculty_id, subject_code, class_id, day, slot<br />
        <strong style={{ color: 'var(--text-secondary)' }}>Optional:</strong> slot_span (2 = lab block), room_id
      </div>

      {/* Result preview */}
      {result && !result.error && (
        <div className="import-result">
          <div className="import-result-header">
            <span>Preview</span>
            <span style={{ color: result.conflict_count > 0 ? 'var(--warning)' : 'var(--success)' }}>
              {result.valid_count} valid · {result.conflict_count} conflicts
            </span>
          </div>
          <div className="import-result-body">
            {result.valid_count > 0 && (
              <div style={{ color: 'var(--success)', display: 'flex', gap: 5, alignItems: 'center' }}>
                <CheckCircle2 size={12} />
                {result.valid_count} assignments ready to import
              </div>
            )}
            {result.canvas_patch?.length > 0 && (
              <div style={{ color: 'var(--text-secondary)', fontSize: 11 }}>
                Will create {result.canvas_patch.length} timetable node{result.canvas_patch.length > 1 ? 's' : ''} on canvas
              </div>
            )}
            {result.conflicts?.slice(0, 5).map((c, i) => (
              <div key={i} style={{ color: 'var(--warning)', display: 'flex', gap: 5, alignItems: 'flex-start', fontSize: 10 }}>
                <AlertTriangle size={11} style={{ flexShrink: 0, marginTop: 1 }} />
                Row {c.row}: {c.errors?.join(', ')}
              </div>
            ))}
            {result.conflicts?.length > 5 && (
              <div style={{ color: 'var(--text-muted)', fontSize: 10 }}>
                …and {result.conflicts.length - 5} more conflicts
              </div>
            )}
          </div>
        </div>
      )}

      {result?.error && (
        <div style={{ color: 'var(--danger)', fontSize: 11, padding: 8, background: 'rgba(239,68,68,0.1)', borderRadius: 6 }}>
          Error: {result.error}
        </div>
      )}

      {result?.valid_count > 0 && (
        <div className="import-apply-btn" onClick={handleApply}>
          <FileUp size={13} style={{ display: 'inline', marginRight: 5 }} />
          Apply {result.valid_count} assignments to canvas
        </div>
      )}
    </div>
  )
}

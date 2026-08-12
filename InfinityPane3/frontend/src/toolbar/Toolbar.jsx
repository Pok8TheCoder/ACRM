/**
 * Toolbar — top bar with tool selector, save, session info, and connection status.
 */

import React, { useState, useCallback } from 'react'
import { MousePointer2, Hand, LayoutGrid, Save, Undo2, Redo2, Wifi, WifiOff, Plus } from 'lucide-react'
import useCanvasStore from '../store/canvasStore'
import useCollabStore from '../store/collabStore'
import UserBadges from '../presence/UserBadges'
import './Toolbar.css'

const TOOLS = [
  { id: 'select', icon: <MousePointer2 size={15} />, label: 'Select (V)' },
  { id: 'pan',    icon: <Hand size={15} />,            label: 'Pan (Space)' },
]

export default function Toolbar() {
  const { activeTool, setActiveTool, undo, redo, saveSession, sessionName, setSessionName, history, historyIndex } = useCanvasStore()
  const { connected, users } = useCollabStore()
  const [saving, setSaving] = useState(false)
  const [editingName, setEditingName] = useState(false)

  const handleSave = useCallback(async () => {
    setSaving(true)
    try { await saveSession() } finally { setSaving(false) }
  }, [saveSession])

  return (
    <div className="toolbar">
      {/* Brand */}
      <div className="toolbar-brand">
        <div className="toolbar-logo">IP3</div>
        {editingName ? (
          <input
            className="toolbar-session-name-input"
            autoFocus
            defaultValue={sessionName}
            onBlur={e => { setSessionName(e.target.value); setEditingName(false) }}
            onKeyDown={e => { if (e.key === 'Enter') e.target.blur() }}
          />
        ) : (
          <span className="toolbar-session-name" onDoubleClick={() => setEditingName(true)} title="Double-click to rename">
            {sessionName}
          </span>
        )}
      </div>

      {/* Tool selector */}
      <div className="toolbar-tools">
        {TOOLS.map(t => (
          <button
            key={t.id}
            className={`toolbar-tool ${activeTool === t.id ? 'active' : ''}`}
            onClick={() => setActiveTool(t.id)}
            title={t.label}
          >
            {t.icon}
          </button>
        ))}
      </div>

      <div className="toolbar-divider" />

      {/* Undo / Redo */}
      <div className="toolbar-tools">
        <button className="toolbar-tool" onClick={undo} disabled={historyIndex <= 0} title="Undo (Ctrl+Z)">
          <Undo2 size={15} />
        </button>
        <button className="toolbar-tool" onClick={redo} disabled={historyIndex >= history.length - 1} title="Redo (Ctrl+Y)">
          <Redo2 size={15} />
        </button>
      </div>

      <div className="toolbar-divider" />

      {/* Save */}
      <button
        className={`toolbar-save ${saving ? 'saving' : ''}`}
        onClick={handleSave}
        disabled={saving}
        title="Save canvas (Ctrl+S)"
      >
        <Save size={14} />
        {saving ? 'Saving…' : 'Save'}
      </button>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* User presence */}
      <UserBadges />

      {/* Connection status */}
      <div className={`toolbar-conn ${connected ? 'connected' : 'disconnected'}`} title={connected ? 'Connected — real-time collaboration active' : 'Disconnected — reconnecting…'}>
        {connected ? <Wifi size={13} /> : <WifiOff size={13} />}
        <span>{connected ? `${users.length + 1} online` : 'Offline'}</span>
      </div>
    </div>
  )
}

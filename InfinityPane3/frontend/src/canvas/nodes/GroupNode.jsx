/**
 * GroupNode — resizable labelled container for organising timetables.
 */
import React, { useState } from 'react'
import { NodeResizer, useReactFlow } from '@xyflow/react'
import { Folder, Trash2 } from 'lucide-react'
import useCollabStore from '../../store/collabStore'

export default function GroupNode({ id, data, selected }) {
  const { deleteElements, updateNodeData } = useReactFlow()
  const { nodeLocks } = useCollabStore()
  const lock = nodeLocks[id]
  const [editing, setEditing] = useState(false)

  const label = data.label || 'Group'
  const color = data.color || 'rgba(99,102,241,0.1)'

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        borderRadius: 12,
        border: `1.5px dashed ${selected ? 'var(--accent)' : 'var(--border-light)'}`,
        background: color,
        position: 'relative',
        overflow: 'visible',
      }}
    >
      <NodeResizer
        minWidth={180}
        minHeight={120}
        isVisible={selected}
        lineStyle={{ border: '1.5px solid var(--accent)' }}
        handleStyle={{ background: 'var(--accent)', border: 'none', borderRadius: '3px' }}
      />

      {/* Label header */}
      <div style={{
        position: 'absolute',
        top: -14,
        left: 10,
        display: 'flex',
        alignItems: 'center',
        gap: 5,
        background: 'var(--bg-panel)',
        border: '1px solid var(--border)',
        borderRadius: 6,
        padding: '2px 8px',
        fontSize: 12,
        fontWeight: 600,
        color: 'var(--text-primary)',
        cursor: 'pointer',
        whiteSpace: 'nowrap',
      }}>
        <Folder size={11} style={{ color: 'var(--accent-light)' }} />
        {editing ? (
          <input
            autoFocus
            defaultValue={label}
            style={{ background: 'transparent', border: 'none', outline: 'none', width: 100, color: 'inherit', fontSize: 12 }}
            onBlur={e => { updateNodeData(id, { label: e.target.value }); setEditing(false) }}
            onKeyDown={e => { if (e.key === 'Enter') e.target.blur() }}
          />
        ) : (
          <span onDoubleClick={() => setEditing(true)}>{label}</span>
        )}
        <Trash2
          size={11}
          style={{ color: 'var(--text-muted)', cursor: 'pointer', marginLeft: 4 }}
          onClick={() => deleteElements({ nodes: [{ id }] })}
        />
      </div>

      {lock && (
        <div style={{ position: 'absolute', top: 4, right: 4, background: 'var(--warning)', color: '#000', fontSize: 10, borderRadius: 4, padding: '1px 6px', fontWeight: 700 }}>
          🔒 {lock.userName}
        </div>
      )}
    </div>
  )
}

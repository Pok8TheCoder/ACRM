/**
 * CursorOverlay — renders other collaborators' cursors on the canvas.
 * Positioned absolutely over the canvas, matching canvas coordinate space.
 */

import React from 'react'
import useCollabStore from '../store/collabStore'

export default function CursorOverlay() {
  const { users } = useCollabStore()

  if (users.length === 0) return null

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: 'none',
        overflow: 'hidden',
        zIndex: 9999,
      }}
    >
      {users.map(user => {
        const { cursor = {}, color, user_name, user_id } = user
        const x = cursor.x || 0
        const y = cursor.y || 0

        return (
          <div
            key={user_id}
            style={{
              position: 'absolute',
              left: x,
              top: y,
              transform: 'translate(-2px, -2px)',
              pointerEvents: 'none',
              transition: 'left 50ms linear, top 50ms linear',
              zIndex: 9999,
            }}
          >
            {/* Cursor arrow */}
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path
                d="M4 2L16 10L10 11L7 18L4 2Z"
                fill={color}
                stroke="#fff"
                strokeWidth="1"
              />
            </svg>
            {/* Name label */}
            <div
              style={{
                position: 'absolute',
                top: 16,
                left: 10,
                background: color,
                color: '#fff',
                fontSize: 10,
                fontWeight: 700,
                padding: '2px 6px',
                borderRadius: 4,
                whiteSpace: 'nowrap',
                boxShadow: '0 2px 6px rgba(0,0,0,0.4)',
                letterSpacing: '0.02em',
              }}
            >
              {user_name || user_id}
            </div>
          </div>
        )
      })}
    </div>
  )
}

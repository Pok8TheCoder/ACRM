/**
 * UserBadges — avatars of all online users in the toolbar.
 */

import React from 'react'
import useCollabStore from '../store/collabStore'

export default function UserBadges() {
  const { users, myColor, myUserName } = useCollabStore()
  const all = [{ user_id: 'me', user_name: myUserName + ' (you)', color: myColor }, ...users]

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
      {all.slice(0, 6).map(u => (
        <div
          key={u.user_id}
          title={u.user_name || u.user_id}
          style={{
            width: 26,
            height: 26,
            borderRadius: '50%',
            background: u.color,
            border: '2px solid var(--bg-panel)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 10,
            fontWeight: 700,
            color: '#fff',
            flexShrink: 0,
            cursor: 'default',
            letterSpacing: '-0.5px',
          }}
        >
          {(u.user_name || u.user_id || '?').charAt(0).toUpperCase()}
        </div>
      ))}
      {all.length > 6 && (
        <div style={{
          width: 26, height: 26, borderRadius: '50%',
          background: 'var(--bg-active)', border: '2px solid var(--bg-panel)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 9, fontWeight: 700, color: 'var(--text-muted)',
        }}>
          +{all.length - 6}
        </div>
      )}
    </div>
  )
}

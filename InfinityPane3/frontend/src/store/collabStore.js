/**
 * Collaboration Store — presence, cursors, node locks, online users.
 */

import { create } from 'zustand'

const useCollabStore = create((set, get) => ({
  // Who's in the room right now (not including self)
  users: [],        // [{ user_id, user_name, color, cursor }]
  myUserId: `user_${Math.random().toString(36).slice(2, 9)}`,
  myUserName: 'Me',
  myColor: '#6366f1',

  setMyInfo: (userId, userName, color) =>
    set({ myUserId: userId, myUserName: userName, myColor: color }),

  // Update the user list from server
  setUsers: (users) => set({ users }),

  addUser: (user) =>
    set(s => ({
      users: s.users.some(u => u.user_id === user.user_id)
        ? s.users
        : [...s.users, user],
    })),

  removeUser: (userId) =>
    set(s => ({ users: s.users.filter(u => u.user_id !== userId) })),

  updateCursor: (userId, x, y) =>
    set(s => ({
      users: s.users.map(u => u.user_id === userId ? { ...u, cursor: { x, y } } : u),
    })),

  // Node locking — shows which user is holding which node
  nodeLocks: {},   // { nodeId: { userId, userName, color } }

  lockNode: (nodeId, userId, userName, color) =>
    set(s => ({ nodeLocks: { ...s.nodeLocks, [nodeId]: { userId, userName, color } } })),

  unlockNode: (nodeId) =>
    set(s => {
      const next = { ...s.nodeLocks }
      delete next[nodeId]
      return { nodeLocks: next }
    }),

  clearLocksForUser: (userId) =>
    set(s => {
      const next = { ...s.nodeLocks }
      Object.keys(next).forEach(k => { if (next[k].userId === userId) delete next[k] })
      return { nodeLocks: next }
    }),

  // Connection status
  connected: false,
  setConnected: (v) => set({ connected: v }),

  // Apply a collab op from useWebSocket
  applyCollabOp: (op) => {
    const store = get()
    switch (op.type) {
      case 'USER_JOINED':
        store.addUser({ user_id: op.user_id, user_name: op.user_name, color: op.user_color, cursor: { x: 0, y: 0 } })
        break
      case 'USER_LEFT':
        store.removeUser(op.user_id)
        store.clearLocksForUser(op.user_id)
        break
      case 'CURSOR_MOVE':
        store.updateCursor(op.user_id, op.x, op.y)
        break
      case 'LOCK_NODE':
        store.lockNode(op.node_id, op.user_id, op.user_name, op.user_color)
        break
      case 'UNLOCK_NODE':
        store.unlockNode(op.node_id)
        break
      case 'FULL_STATE':
        store.setUsers(op.users || [])
        if (op.you) {
          set({ myUserId: op.you.user_id, myUserName: op.you.user_name, myColor: op.you.color })
        }
        break
      default:
        break
    }
  },
}))

export default useCollabStore

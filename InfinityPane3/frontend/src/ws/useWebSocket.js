/**
 * useWebSocket — manages the WebSocket connection to InfinityPane3 backend.
 * Feeds ops into canvasStore and collabStore.
 */

import { useEffect, useRef, useCallback } from 'react'
import useCanvasStore from '../store/canvasStore'
import useCollabStore from '../store/collabStore'

const CANVAS_OPS = new Set([
  'MOVE_NODE', 'RESIZE_NODE', 'ADD_NODE', 'DELETE_NODE',
  'ADD_EDGE', 'DELETE_EDGE', 'ASSIGN_CELL', 'CLEAR_CELL', 'FULL_STATE',
])
const COLLAB_OPS = new Set([
  'USER_JOINED', 'USER_LEFT', 'CURSOR_MOVE', 'LOCK_NODE', 'UNLOCK_NODE', 'FULL_STATE',
])

// Throttle helper
function throttle(fn, ms) {
  let last = 0
  return (...args) => {
    const now = Date.now()
    if (now - last >= ms) { last = now; fn(...args) }
  }
}

export function useWebSocket() {
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)

  const { institutionId } = useCanvasStore()
  const { myUserId, myUserName, setConnected, applyCollabOp } = useCollabStore()
  const { applyRemoteOp } = useCanvasStore()

  const buildUrl = useCallback(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    return `${proto}://${host}/ws/${institutionId}?user_id=${myUserId}&user_name=${encodeURIComponent(myUserName)}`
  }, [institutionId, myUserId, myUserName])

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(buildUrl())
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      clearTimeout(reconnectTimer.current)
    }

    ws.onmessage = (event) => {
      try {
        const op = JSON.parse(event.data)

        if (CANVAS_OPS.has(op.type)) {
          // Don't apply our own echoed ops (server doesn't echo back, but safety check)
          if (op.user_id !== myUserId || op.type === 'FULL_STATE') {
            applyRemoteOp(op)
          }
        }

        if (COLLAB_OPS.has(op.type)) {
          applyCollabOp(op)
        }
      } catch (e) {
        console.error('WS parse error:', e)
      }
    }

    ws.onclose = () => {
      setConnected(false)
      // Reconnect after 3 seconds
      reconnectTimer.current = setTimeout(connect, 3000)
    }

    ws.onerror = (e) => {
      console.warn('WS error:', e)
      ws.close()
    }
  }, [buildUrl, myUserId, setConnected, applyRemoteOp, applyCollabOp])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  // Send an operation to the server
  const send = useCallback((op) => {
    const ws = wsRef.current
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ ...op, user_id: myUserId, user_name: myUserName, timestamp: Date.now() / 1000 }))
    }
  }, [myUserId, myUserName])

  // Throttled cursor sender (30fps max)
  const sendCursor = useCallback(
    throttle((x, y) => send({ type: 'CURSOR_MOVE', x, y }), 33),
    [send]
  )

  return { send, sendCursor }
}

export default useWebSocket

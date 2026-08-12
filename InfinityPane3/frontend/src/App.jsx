/**
 * App — Root layout component for InfinityPane3.
 * Arranges: Toolbar → [LeftSidebar | Canvas | RightSidebar]
 * Initialises ACRM data fetch and WebSocket on mount.
 */

import React, { useEffect } from 'react'
import Toolbar from './toolbar/Toolbar'
import LeftSidebar from './sidebar/FacultySidebar'
import SubjectSidebar from './sidebar/SubjectSidebar'
import InfiniteCanvas from './canvas/InfiniteCanvas'
import useCanvasStore from './store/canvasStore'
import useWebSocket from './ws/useWebSocket'

function App() {
  const { fetchFaculty, fetchSubjects, fetchClasses, fetchRooms } = useCanvasStore()

  // Prime the WebSocket connection (hook handles reconnection internally)
  useWebSocket()

  // Load ACRM data on startup
  useEffect(() => {
    fetchFaculty()
    fetchSubjects()
    fetchClasses()
    fetchRooms()
  }, [])

  // Ctrl+S → save
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        useCanvasStore.getState().saveSession()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      width: '100vw',
      overflow: 'hidden',
      background: 'var(--bg-canvas)',
    }}>
      {/* Top bar */}
      <Toolbar />

      {/* Main content row */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <LeftSidebar />
        <InfiniteCanvas />
        <SubjectSidebar />
      </div>
    </div>
  )
}

export default App

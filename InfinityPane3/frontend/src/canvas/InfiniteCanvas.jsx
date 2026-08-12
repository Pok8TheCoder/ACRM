/**
 * InfiniteCanvas — React Flow root canvas.
 * Handles:
 *   - Node/edge state synced to Zustand
 *   - Drop events from sidebars (faculty, subject, class → new timetable)
 *   - WebSocket send on node drag stop / cell assign
 *   - Keyboard shortcuts (Del, Ctrl+Z, Ctrl+Shift+Z)
 *   - Presence cursor broadcasting
 */

import React, { useCallback, useEffect, useRef } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  addEdge,
} from '@xyflow/react'

import TimetableNode from './nodes/TimetableNode'
import GroupNode from './nodes/GroupNode'
import CursorOverlay from '../presence/CursorOverlay'
import useCanvasStore from '../store/canvasStore'
import useCollabStore from '../store/collabStore'
import useWebSocket from '../ws/useWebSocket'
import './InfiniteCanvas.css'

// Register custom node types
const nodeTypes = {
  timetable: TimetableNode,
  group: GroupNode,
}

export default function InfiniteCanvas() {
  const {
    nodes: storeNodes,
    edges: storeEdges,
    setNodes: setStoreNodes,
    setEdges: setStoreEdges,
    addTimetableNode,
    classes,
    undo,
    redo,
    applyRemoteOp,
  } = useCanvasStore()

  const { myUserId } = useCollabStore()
  const { send, sendCursor } = useWebSocket()

  // React Flow's own node/edge state (synced to store)
  const [nodes, setNodes, onNodesChange] = useNodesState(storeNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(storeEdges)
  const canvasRef = useRef(null)

  // Keep React Flow state in sync with store (remote ops, undo, CSV import)
  useEffect(() => { setNodes(storeNodes) }, [storeNodes, setNodes])
  useEffect(() => { setEdges(storeEdges) }, [storeEdges, setEdges])

  // Push local node changes back to store
  const handleNodesChange = useCallback((changes) => {
    onNodesChange(changes)
    setStoreNodes(n => {
      let next = [...n]
      changes.forEach(c => {
        if (c.type === 'position' && c.position) {
          next = next.map(node => node.id === c.id ? { ...node, position: c.position } : node)
        } else if (c.type === 'remove') {
          next = next.filter(node => node.id !== c.id)
        } else if (c.type === 'dimensions') {
          next = next.map(node => node.id === c.id ? { ...node, width: c.dimensions?.width, height: c.dimensions?.height } : node)
        }
      })
      return next
    })
  }, [onNodesChange, setStoreNodes])

  // Broadcast node drag stop to collaborators
  const handleNodeDragStop = useCallback((_, node) => {
    send({ type: 'MOVE_NODE', node_id: node.id, x: node.position.x, y: node.position.y })
    send({ type: 'UNLOCK_NODE', node_id: node.id })
  }, [send])

  const handleNodeDragStart = useCallback((_, node) => {
    send({ type: 'LOCK_NODE', node_id: node.id })
  }, [send])

  // Edge connect
  const onConnect = useCallback((params) => {
    const edge = { ...params, type: 'smoothstep', animated: false, style: { stroke: 'var(--border-light)' } }
    setEdges(es => addEdge(edge, es))
    setStoreEdges(es => addEdge(edge, es))
    send({ type: 'ADD_EDGE', edge })
  }, [setEdges, setStoreEdges, send])

  // Drop from sidebar
  const handleDrop = useCallback((e) => {
    e.preventDefault()
    let payload
    try {
      payload = JSON.parse(e.dataTransfer.getData('application/x-ip3'))
    } catch {
      return
    }

    // Convert screen → flow coordinates
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return
    const flowPos = {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    }

    if (payload.type === 'class') {
      // Drop a class → create a new timetable node
      const newNode = addTimetableNode(payload.item.id, payload.item.name, flowPos)
      send({ type: 'ADD_NODE', node: newNode })
    }
    // Faculty/subject drops are handled inside TimetableNode cells directly
  }, [addTimetableNode, send])

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
  }, [])

  // Cursor tracking
  const handleMouseMove = useCallback((e) => {
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return
    sendCursor(e.clientX - rect.left, e.clientY - rect.top)
  }, [sendCursor])

  // Keyboard shortcuts
  useEffect(() => {
    const onKey = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) { e.preventDefault(); undo() }
      if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) { e.preventDefault(); redo() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [undo, redo])

  return (
    <div className="rf-canvas-wrapper" ref={canvasRef} onMouseMove={handleMouseMove}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={handleNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeDragStart={handleNodeDragStart}
        onNodeDragStop={handleNodeDragStop}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.05}
        maxZoom={8}
        deleteKeyCode={['Backspace', 'Delete']}
        multiSelectionKeyCode="Shift"
        selectionKeyCode="Shift"
        style={{ background: 'var(--bg-canvas)' }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={24}
          size={1}
          color="var(--border)"
        />
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor={(n) => {
            if (n.type === 'timetable') return 'var(--accent)'
            if (n.type === 'group') return 'var(--border-light)'
            return 'var(--text-muted)'
          }}
          maskColor="rgba(0,0,0,0.5)"
          style={{ background: 'var(--bg-panel)' }}
        />
      </ReactFlow>

      {/* Collaborator cursors — rendered outside React Flow to avoid transform issues */}
      <CursorOverlay />
    </div>
  )
}

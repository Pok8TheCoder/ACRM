/**
 * Canvas Store — all timetable canvas state, ACRM data, and UI state.
 * Uses Zustand with immer-style updates.
 */

import { create } from 'zustand'

const API = '/api'

// Colour palette for auto-assigned subject colours
const SUBJECT_PALETTE = [
  '#6366f1', '#ec4899', '#f59e0b', '#10b981', '#3b82f6',
  '#8b5cf6', '#ef4444', '#06b6d4', '#84cc16', '#f97316',
]

let _subjectColorMap = {}
const getSubjectColor = (subjectId) => {
  if (!_subjectColorMap[subjectId]) {
    const idx = Object.keys(_subjectColorMap).length
    _subjectColorMap[subjectId] = SUBJECT_PALETTE[idx % SUBJECT_PALETTE.length]
  }
  return _subjectColorMap[subjectId]
}

// ── ID generator ──────────────────────────────────────────────────────────────
const uid = (prefix = 'node') =>
  `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`

// ── Default timetable days ────────────────────────────────────────────────────
const DEFAULT_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

const useCanvasStore = create((set, get) => ({
  // ── Institution context ────────────────────────────────────────────────────
  institutionId: new URLSearchParams(window.location.search).get('institution') || 'iit_delhi',
  sessionId: null,
  sessionName: 'Untitled Session',

  setSessionName: (name) => set({ sessionName: name }),

  // ── ACRM data ──────────────────────────────────────────────────────────────
  faculty: [],
  subjects: [],
  classes: [],
  rooms: [],
  facultyLoading: false,
  subjectsLoading: false,
  classesLoading: false,

  fetchFaculty: async (search = '') => {
    const { institutionId } = get()
    set({ facultyLoading: true })
    try {
      const res = await fetch(`${API}/data/faculty?institution_id=${institutionId}&search=${encodeURIComponent(search)}`)
      const data = await res.json()
      set({ faculty: data, facultyLoading: false })
    } catch (e) {
      console.error('fetchFaculty:', e)
      set({ facultyLoading: false })
    }
  },

  fetchSubjects: async (search = '') => {
    const { institutionId } = get()
    set({ subjectsLoading: true })
    try {
      const res = await fetch(`${API}/data/subjects?institution_id=${institutionId}&search=${encodeURIComponent(search)}`)
      const data = await res.json()
      // Assign colours
      data.forEach(s => { getSubjectColor(s.id) })
      set({ subjects: data, subjectsLoading: false })
    } catch (e) {
      console.error('fetchSubjects:', e)
      set({ subjectsLoading: false })
    }
  },

  fetchClasses: async () => {
    const { institutionId } = get()
    set({ classesLoading: true })
    try {
      const res = await fetch(`${API}/data/classes?institution_id=${institutionId}`)
      const data = await res.json()
      set({ classes: data, classesLoading: false })
    } catch (e) {
      console.error('fetchClasses:', e)
      set({ classesLoading: false })
    }
  },

  fetchRooms: async () => {
    const { institutionId } = get()
    try {
      const res = await fetch(`${API}/data/rooms?institution_id=${institutionId}`)
      const data = await res.json()
      set({ rooms: data })
    } catch (e) {
      console.error('fetchRooms:', e)
    }
  },

  getSubjectColor,

  // ── React Flow nodes & edges ──────────────────────────────────────────────
  nodes: [],
  edges: [],

  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),

  // Add a brand-new timetable node for a given class
  addTimetableNode: (classId, className, position = { x: 0, y: 0 }) => {
    const newNode = {
      id: uid('tt'),
      type: 'timetable',
      position,
      data: {
        class_id: classId,
        class_name: className,
        days: [...DEFAULT_DAYS],
        slots_per_day: 8,
        slot_duration: 60,
        start_time: '09:00',
        break_slots: [],
        cells: {},
        lab_spans: {},
      },
    }
    set(s => ({ nodes: [...s.nodes, newNode] }))
    get().pushHistory()
    return newNode
  },

  // Assign a faculty+subject to a timetable cell
  assignCell: (nodeId, cellKey, assignment, slotSpan = 1) => {
    set(s => ({
      nodes: s.nodes.map(n => {
        if (n.id !== nodeId) return n
        const cells = { ...n.data.cells, [cellKey]: assignment }
        const labSpans = { ...n.data.lab_spans }
        if (slotSpan > 1) labSpans[cellKey] = slotSpan
        else delete labSpans[cellKey]
        return { ...n, data: { ...n.data, cells, lab_spans: labSpans } }
      })
    }))
    get().pushHistory()
  },

  // Clear a cell
  clearCell: (nodeId, cellKey) => {
    set(s => ({
      nodes: s.nodes.map(n => {
        if (n.id !== nodeId) return n
        const cells = { ...n.data.cells }
        const labSpans = { ...n.data.lab_spans }
        delete cells[cellKey]
        delete labSpans[cellKey]
        return { ...n, data: { ...n.data, cells, lab_spans: labSpans } }
      })
    }))
    get().pushHistory()
  },

  // Update timetable config (days, slots, start time, etc.)
  updateTimetableConfig: (nodeId, updates) => {
    set(s => ({
      nodes: s.nodes.map(n =>
        n.id === nodeId ? { ...n, data: { ...n.data, ...updates } } : n
      )
    }))
    get().pushHistory()
  },

  // Batch-apply nodes from CSV import
  applyCanvasPatch: (patchNodes) => {
    set(s => ({ nodes: [...s.nodes, ...patchNodes] }))
    get().pushHistory()
  },

  // Apply a remote op from WebSocket
  applyRemoteOp: (op) => {
    const type = op.type
    if (type === 'MOVE_NODE') {
      set(s => ({
        nodes: s.nodes.map(n =>
          n.id === op.node_id ? { ...n, position: { x: op.x, y: op.y } } : n
        )
      }))
    } else if (type === 'ADD_NODE') {
      set(s => ({ nodes: [...s.nodes, op.node] }))
    } else if (type === 'DELETE_NODE') {
      set(s => ({ nodes: s.nodes.filter(n => n.id !== op.node_id) }))
    } else if (type === 'ASSIGN_CELL') {
      get().assignCell(op.node_id, op.cell_key, op.assignment, op.slot_span || 1)
    } else if (type === 'CLEAR_CELL') {
      get().clearCell(op.node_id, op.cell_key)
    } else if (type === 'FULL_STATE') {
      // Remote full state — replace everything
      const state = op.state || {}
      set({
        nodes: state.nodes || [],
        edges: state.edges || [],
      })
    }
  },

  // ── Drag context (what's being dragged from sidebar) ──────────────────────
  dragging: null, // { type: 'faculty'|'subject', item: {...} }
  setDragging: (item) => set({ dragging: item }),
  clearDragging: () => set({ dragging: null }),

  // ── Active tool ────────────────────────────────────────────────────────────
  activeTool: 'select', // 'select' | 'pan' | 'timetable'
  setActiveTool: (tool) => set({ activeTool: tool }),

  // ── Sidebar visibility ─────────────────────────────────────────────────────
  leftPanelTab: 'faculty',  // 'faculty' | 'classes' | 'import'
  setLeftPanelTab: (tab) => set({ leftPanelTab: tab }),

  // ── History (undo/redo) ────────────────────────────────────────────────────
  history: [],
  historyIndex: -1,
  _ignoreHistory: false,

  pushHistory: () => {
    if (get()._ignoreHistory) return
    const { nodes, edges, history, historyIndex } = get()
    const snapshot = { nodes: JSON.parse(JSON.stringify(nodes)), edges: [...edges] }
    const next = history.slice(0, historyIndex + 1).concat([snapshot])
    const trimmed = next.slice(-60)
    set({ history: trimmed, historyIndex: trimmed.length - 1 })
  },

  undo: () => {
    const { history, historyIndex } = get()
    if (historyIndex <= 0) return
    const target = history[historyIndex - 1]
    set({ _ignoreHistory: true, nodes: target.nodes, edges: target.edges, historyIndex: historyIndex - 1 })
    set({ _ignoreHistory: false })
  },

  redo: () => {
    const { history, historyIndex } = get()
    if (historyIndex >= history.length - 1) return
    const target = history[historyIndex + 1]
    set({ _ignoreHistory: true, nodes: target.nodes, edges: target.edges, historyIndex: historyIndex + 1 })
    set({ _ignoreHistory: false })
  },

  // ── Canvas save/load ───────────────────────────────────────────────────────
  saveSession: async () => {
    const { institutionId, sessionId, sessionName, nodes, edges } = get()
    const body = {
      institution_id: institutionId,
      session_name: sessionName,
      canvas: { institution_id: institutionId, session_name: sessionName, nodes, edges, viewport: {} },
    }
    if (sessionId) {
      await fetch(`${API}/canvas/sessions/${sessionId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
    } else {
      const res = await fetch(`${API}/canvas/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      set({ sessionId: data.session_id })
    }
  },

  loadSession: async (sessionId) => {
    const { institutionId } = get()
    const res = await fetch(`${API}/canvas/sessions/${sessionId}?institution_id=${institutionId}`)
    const data = await res.json()
    const canvas = data.canvas || {}
    set({
      sessionId: data.session_id,
      sessionName: data.session_name,
      nodes: canvas.nodes || [],
      edges: canvas.edges || [],
    })
  },
}))

export default useCanvasStore

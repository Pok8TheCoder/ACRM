/**
 * InfinityPane State Management with Zustand
 * Handles all canvas state, tools, and data
 */

import { create } from 'zustand';

const API_BASE = '/api';

// Helper to generate unique IDs
const generateId = (prefix = 'id') => `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

const useStore = create((set, get) => ({
  // ============== Canvas State ==============
  canvas: {
    x: 0,
    y: 0,
    zoom: 1,
    minZoom: 0.1,
    maxZoom: 10,
    isPanning: false,
    panStart: { x: 0, y: 0 },
  },

  setCanvasPosition: (x, y) => set((state) => ({
    canvas: { ...state.canvas, x, y }
  })),

  setZoom: (zoom) => set((state) => ({
    canvas: { 
      ...state.canvas, 
      zoom: Math.min(Math.max(zoom, state.canvas.minZoom), state.canvas.maxZoom) 
    }
  })),

  setPanning: (isPanning, panStart = null) => set((state) => ({
    canvas: { 
      ...state.canvas, 
      isPanning, 
      panStart: panStart || state.canvas.panStart 
    }
  })),

  resetCanvas: () => set((state) => ({
    canvas: { ...state.canvas, x: 0, y: 0, zoom: 1 }
  })),

  // ============== Active Tool ==============
  activeTool: 'select', // 'select', 'pan', 'arrow', 'timetable', 'group'

  setActiveTool: (tool) => set({ activeTool: tool }),

  // ============== Teachers ==============
  teachers: [],
  teachersLoading: false,
  teacherSearch: '',

  setTeacherSearch: (search) => set({ teacherSearch: search }),

  fetchTeachers: async () => {
    set({ teachersLoading: true });
    try {
      const search = get().teacherSearch;
      const res = await fetch(`${API_BASE}/teachers${search ? `?search=${search}` : ''}`);
      const data = await res.json();
      set({ teachers: data, teachersLoading: false });
    } catch (error) {
      console.error('Failed to fetch teachers:', error);
      set({ teachersLoading: false });
    }
  },

  // ============== Subjects ==============
  subjects: [],
  subjectsLoading: false,
  subjectSearch: '',

  setSubjectSearch: (search) => set({ subjectSearch: search }),

  fetchSubjects: async () => {
    set({ subjectsLoading: true });
    try {
      const search = get().subjectSearch;
      const res = await fetch(`${API_BASE}/subjects${search ? `?search=${search}` : ''}`);
      const data = await res.json();
      set({ subjects: data, subjectsLoading: false });
    } catch (error) {
      console.error('Failed to fetch subjects:', error);
      set({ subjectsLoading: false });
    }
  },

  // ============== Classes ==============
  classes: [],

  fetchClasses: async () => {
    try {
      const res = await fetch(`${API_BASE}/classes`);
      const data = await res.json();
      set({ classes: data });
    } catch (error) {
      console.error('Failed to fetch classes:', error);
    }
  },

  // ============== Canvas Elements ==============
  groups: [],
  timetables: [],
  arrows: [],
  freeArrows: [],
  teacherPlacements: [], // Teachers placed on canvas
  subjectPlacements: [], // Subjects placed on canvas
  textBlocks: [],
  structureBlocks: [],

  // Add a new group
  addGroup: (x, y, parentId = null) => {
    const newGroup = {
      id: generateId('group'),
      name: '',
      x,
      y,
      width: 250,
      height: 180,
      parentId,
      color: `hsl(${Math.random() * 360}, 70%, 85%)`,
      isSelected: false,
      isResizing: false,
    };
    set((state) => ({ groups: [...state.groups, newGroup] }));
      get().pushHistory();
    return newGroup;
  },

  updateGroup: (id, updates) => {
    set((state) => ({
      groups: state.groups.map(g => g.id === id ? { ...g, ...updates } : g)
    }));
    get().pushHistory();
  },

  deleteGroup: (id) => {
    set((state) => ({
      groups: state.groups.filter(g => g.id !== id),
      // Also remove nested items and arrows
      teacherPlacements: state.teacherPlacements.filter(t => t.groupId !== id),
      subjectPlacements: state.subjectPlacements.filter(s => s.groupId !== id),
      arrows: state.arrows.filter(a => a.groupId !== id),
    }));
    get().pushHistory();
  },

  // Add a new timetable
  addTimetable: (x, y, classId, groupId) => {
    const newTimetable = {
      id: generateId('timetable'),
      classId,
      groupId,
      x,
      y,
      days: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
      slotsPerDay: 8,
      slotDuration: 60,
      breakSlots: [], // [{ afterSlot: number, duration: number }]
      startTime: '09:00',
      cells: {}, // { 'Monday-0': { subjectId, teacherId } }
      isSelected: false,
    };
    set((state) => ({ timetables: [...state.timetables, newTimetable] }));
      get().pushHistory();
    return newTimetable;
  },

  updateTimetable: (id, updates) => {
    set((state) => ({
      timetables: state.timetables.map(t => t.id === id ? { ...t, ...updates } : t)
    }));
    get().pushHistory();
  },

  deleteTimetable: (id) => {
    set((state) => ({
      timetables: state.timetables.filter(t => t.id !== id)
    }));
    get().pushHistory();
  },

  // Add arrow connection
  addArrow: (from, to, groupId = null) => {
    const newArrow = {
      id: generateId('arrow'),
      from, // { type: 'teacher'|'subject', id, placementId }
      to,   // { type: 'teacher'|'subject', id, placementId }
      groupId,
      color: '#4361ee',
    };
    set((state) => ({ arrows: [...state.arrows, newArrow] }));
    get().pushHistory();
    return newArrow;
  },

  deleteArrow: (id) => {
    set((state) => ({
      arrows: state.arrows.filter(a => a.id !== id)
    }));
    get().pushHistory();
  },

  addFreeArrow: (from, to) => {
    const newArrow = {
      id: generateId('free_arrow'),
      from, // { x, y }
      to,   // { x, y }
      color: '#4361ee',
      style: 'straight',
    };
    set((state) => ({ freeArrows: [...state.freeArrows, newArrow] }));
    get().pushHistory();
    return newArrow;
  },

  updateFreeArrow: (id, updates) => {
    set((state) => ({
      freeArrows: state.freeArrows.map(a => a.id === id ? { ...a, ...updates } : a)
    }));
    get().pushHistory();
  },

  deleteFreeArrow: (id) => {
    set((state) => ({
      freeArrows: state.freeArrows.filter(a => a.id !== id)
    }));
    get().pushHistory();
  },

  // Text blocks
  addTextBlock: (x, y, text = 'Text') => {
    const newBlock = {
      id: generateId('text'),
      x,
      y,
      text,
      color: '#ffffff',
      opacity: 1,
      zIndex: 30,
      locked: false,
    };
    set((state) => ({ textBlocks: [...state.textBlocks, newBlock] }));
      get().pushHistory();
    return newBlock;
  },

  updateTextBlock: (id, updates) => {
    set((state) => ({
      textBlocks: state.textBlocks.map(b => b.id === id ? { ...b, ...updates } : b)
    }));
    get().pushHistory();
  },

  deleteTextBlock: (id) => {
    set((state) => ({
      textBlocks: state.textBlocks.filter(b => b.id !== id)
    }));
    get().pushHistory();
  },

  // Structure blocks
  addStructureBlock: (x, y, shape = 'rectangle') => {
    const newBlock = {
      id: generateId('structure'),
      x,
      y,
      width: shape === 'square' || shape === 'circle' ? 140 : 220,
      height: shape === 'square' || shape === 'circle' ? 140 : 120,
      label: 'Structure',
      shape,
      color: `hsl(${Math.random() * 360}, 70%, 60%)`,
      opacity: 1,
      zIndex: 10,
      locked: false,
    };
    set((state) => ({ structureBlocks: [...state.structureBlocks, newBlock] }));
    get().pushHistory();
    return newBlock;
  },

  updateStructureBlock: (id, updates) => {
    set((state) => ({
      structureBlocks: state.structureBlocks.map(b => b.id === id ? { ...b, ...updates } : b)
    }));
    get().pushHistory();
  },

  deleteStructureBlock: (id) => {
    set((state) => ({
      structureBlocks: state.structureBlocks.filter(b => b.id !== id)
    }));
    get().pushHistory();
  },

  // Place teacher on canvas
  placeTeacher: (teacherId, x, y, groupId = null) => {
    const teacher = get().teachers.find(t => t.id === teacherId);
    if (!teacher) return null;
    
    const placement = {
      id: generateId('tp'),
      teacherId,
      x,
      y,
      groupId,
      isGlobal: groupId === null,
    };
    set((state) => ({ teacherPlacements: [...state.teacherPlacements, placement] }));
      get().pushHistory();
    return placement;
  },

  updateTeacherPlacement: (id, updates) => {
    set((state) => ({
      teacherPlacements: state.teacherPlacements.map(t => 
        t.id === id ? { ...t, ...updates } : t
      )
    }));
    get().pushHistory();
  },

  deleteTeacherPlacement: (id) => {
    set((state) => ({
      teacherPlacements: state.teacherPlacements.filter(t => t.id !== id),
      arrows: state.arrows.filter(a => 
        a.from.placementId !== id && a.to.placementId !== id
      )
    }));
    get().pushHistory();
  },

  // Place subject on canvas
  placeSubject: (subjectId, x, y, groupId = null) => {
    const subject = get().subjects.find(s => s.id === subjectId);
    if (!subject) return null;
    
    const placement = {
      id: generateId('sp'),
      subjectId,
      x,
      y,
      groupId,
    };
    set((state) => ({ subjectPlacements: [...state.subjectPlacements, placement] }));
      get().pushHistory();
    return placement;
  },

  updateSubjectPlacement: (id, updates) => {
    set((state) => ({
      subjectPlacements: state.subjectPlacements.map(s => 
        s.id === id ? { ...s, ...updates } : s
      )
    }));
    get().pushHistory();
  },

  deleteSubjectPlacement: (id) => {
    set((state) => ({
      subjectPlacements: state.subjectPlacements.filter(s => s.id !== id),
      arrows: state.arrows.filter(a => 
        a.from.placementId !== id && a.to.placementId !== id
      )
    }));
    get().pushHistory();
  },

  // ============== Arrow Drawing State ==============
  arrowDrawing: null, // { from: { type, id, placementId, x, y }, currentX, currentY }
  freeArrowDrawing: null, // { from: { x, y }, currentX, currentY }

  startArrowDrawing: (from) => set({ arrowDrawing: { from, currentX: from.x, currentY: from.y } }),
  
  updateArrowDrawing: (x, y) => set((state) => 
    state.arrowDrawing ? { arrowDrawing: { ...state.arrowDrawing, currentX: x, currentY: y } } : {}
  ),
  
  finishArrowDrawing: (to) => {
    const drawing = get().arrowDrawing;
    if (drawing && to) {
      get().addArrow(drawing.from, to);
    }
    set({ arrowDrawing: null });
  },

  startFreeArrowDrawing: (from) => set({ freeArrowDrawing: { from, currentX: from.x, currentY: from.y } }),

  updateFreeArrowDrawing: (x, y) => set((state) =>
    state.freeArrowDrawing ? { freeArrowDrawing: { ...state.freeArrowDrawing, currentX: x, currentY: y } } : {}
  ),

  finishFreeArrowDrawing: (to) => {
    const drawing = get().freeArrowDrawing;
    if (drawing && to) {
      get().addFreeArrow(drawing.from, to);
    }
    set({ freeArrowDrawing: null });
  },
  
  cancelArrowDrawing: () => set({ arrowDrawing: null, freeArrowDrawing: null }),

  // ============== Selection ==============
  selectedElements: [], // [{ type: 'group'|'timetable'|'teacher'|'subject', id }]

  selectElement: (type, id, multi = false) => set((state) => ({
    selectedElements: multi 
      ? [...state.selectedElements, { type, id }]
      : [{ type, id }]
  })),

  setSelectedElements: (elements) => set({ selectedElements: elements }),

  deselectAll: () => set({ selectedElements: [] }),

  isSelected: (type, id) => {
    return get().selectedElements.some(e => e.type === type && e.id === id);
  },

  // ============== Context Menu ==============
  contextMenu: null, // { x, y, type, targetId, items }

  showContextMenu: (x, y, type, targetId, items) => set({
    contextMenu: { x, y, type, targetId, items }
  }),

  hideContextMenu: () => set({ contextMenu: null }),

  // ============== Modals ==============
  activeModal: null, // { type: 'timetableSettings'|'linkClass', data }

  showModal: (type, data = {}) => set({ activeModal: { type, data } }),
  hideModal: () => set({ activeModal: null }),

  // ============== Clipboard ==============
  clipboard: null,

  copy: () => {
    const selected = get().selectedElements;
    if (selected.length > 0) {
      set({ clipboard: selected });
    }
  },

  paste: (offsetX = 50, offsetY = 50) => {
    const clipboard = get().clipboard;
    if (!clipboard) return;
    
    clipboard.forEach(item => {
      if (item.type === 'group') {
        const group = get().groups.find(g => g.id === item.id);
        if (group) {
          get().addGroup(group.x + offsetX, group.y + offsetY, group.parentId);
        }
      }
    });
  },

  // ============== Undo/Redo (simplified) ==============
  history: [],
  historyIndex: -1,
  isRestoring: false,

  createSnapshot: () => {
    const state = get();
    return {
      canvas: state.canvas,
      activeTool: state.activeTool,
      groups: state.groups,
      timetables: state.timetables,
      arrows: state.arrows,
      freeArrows: state.freeArrows,
      teacherPlacements: state.teacherPlacements,
      subjectPlacements: state.subjectPlacements,
      textBlocks: state.textBlocks,
      structureBlocks: state.structureBlocks,
      selectedElements: state.selectedElements,
    };
  },

  pushHistory: () => {
    if (get().isRestoring) return;
    const snapshot = get().createSnapshot();
    const history = get().history;
    const historyIndex = get().historyIndex;
    const next = history.slice(0, historyIndex + 1).concat([snapshot]);
    const trimmed = next.slice(-50);
    set({ history: trimmed, historyIndex: trimmed.length - 1 });
  },

  undo: () => {
    const { history, historyIndex } = get();
    if (historyIndex <= 0) return;
    const target = history[historyIndex - 1];
    set({ isRestoring: true });
    set({ ...target, historyIndex: historyIndex - 1 });
    set({ isRestoring: false });
  },

  redo: () => {
    const { history, historyIndex } = get();
    if (historyIndex >= history.length - 1) return;
    const target = history[historyIndex + 1];
    set({ isRestoring: true });
    set({ ...target, historyIndex: historyIndex + 1 });
    set({ isRestoring: false });
  },

  // ============== Save/Load ==============
  saveToBackend: async () => {
    const state = get();
    try {
      await fetch(`${API_BASE}/canvas`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          groups: state.groups,
          timetables: state.timetables,
          arrows: state.arrows,
          teacherPlacements: state.teacherPlacements,
          subjectPlacements: state.subjectPlacements,
        })
      });
    } catch (error) {
      console.error('Failed to save:', error);
    }
  },

  loadFromBackend: async () => {
    try {
      const res = await fetch(`${API_BASE}/canvas`);
      const data = await res.json();
      set({
        groups: data.groups || [],
        timetables: data.timetables || [],
        arrows: data.arrows || [],
        teacherPlacements: data.teacherPlacements || [],
        subjectPlacements: data.subjectPlacements || [],
      });
    } catch (error) {
      console.error('Failed to load:', error);
    }
  },
}));

export default useStore;

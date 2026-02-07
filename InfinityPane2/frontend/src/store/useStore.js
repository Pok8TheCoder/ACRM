/**
 * InfinityPane State Management with Zustand
 * Handles all canvas state, tools, and data
 */

import { create } from 'zustand';

let highlightTimer = null;

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

  lastCursor: null, // { x, y } in canvas coords
  setLastCursor: (x, y) => set({ lastCursor: { x, y } }),

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

  centerCanvasOn: (x, y) => set((state) => ({
    canvas: {
      ...state.canvas,
      x: -x * state.canvas.zoom,
      y: -y * state.canvas.zoom,
    }
  })),

  resetCanvas: () => set((state) => ({
    canvas: { ...state.canvas, x: 0, y: 0, zoom: 1 }
  })),

  // ============== Highlight ==============
  highlightTarget: null, // { type, id }

  setHighlightTarget: (type, id, duration = 2000) => {
    if (highlightTimer) {
      clearTimeout(highlightTimer);
    }
    set({ highlightTarget: { type, id } });
    highlightTimer = setTimeout(() => {
      set({ highlightTarget: null });
      highlightTimer = null;
    }, duration);
  },

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
  classSubjects: {}, // { [classId]: [{ id, name, hours }] }
  classWeeks: {}, // { [classId]: number }

  fetchClasses: async () => {
    try {
      const res = await fetch(`${API_BASE}/classes`);
      const data = await res.json();
      set({ classes: data });
    } catch (error) {
      console.error('Failed to fetch classes:', error);
    }
  },

  initializeClassSubjects: (classId) => {
    if (!classId) return;
    const current = get().classSubjects[classId];
    if (current) return;

    const subjects = get().subjects || [];
    const seeded = subjects.map((subject) => ({
      id: generateId('class_subject'),
      name: subject.name || 'Subject',
      hours: 0,
      teacherId: null,
    }));

    set((state) => ({
      classSubjects: { ...state.classSubjects, [classId]: seeded }
    }));
    set((state) => ({
      classWeeks: { ...state.classWeeks, [classId]: state.classWeeks[classId] || 15 }
    }));
    get().pushHistory();
  },

  setClassWeeks: (classId, weeks) => {
    if (!classId) return;
    const safeWeeks = Math.max(1, parseInt(weeks, 10) || 1);
    set((state) => ({
      classWeeks: { ...state.classWeeks, [classId]: safeWeeks }
    }));
    get().pushHistory();
  },

  addClassSubject: (classId) => {
    if (!classId) return;
    const newSubject = {
      id: generateId('class_subject'),
      name: 'New Subject',
      hours: 0,
      teacherId: null,
    };
    set((state) => ({
      classSubjects: {
        ...state.classSubjects,
        [classId]: [...(state.classSubjects[classId] || []), newSubject],
      },
    }));
    get().pushHistory();
  },

  updateClassSubject: (classId, subjectId, updates) => {
    if (!classId || !subjectId) return;
    set((state) => ({
      classSubjects: {
        ...state.classSubjects,
        [classId]: (state.classSubjects[classId] || []).map((subject) =>
          subject.id === subjectId ? { ...subject, ...updates } : subject
        ),
      },
    }));
    get().pushHistory();
  },

  assignTeacherToClassSubject: (classId, subjectId, teacherId) => {
    if (!classId || !subjectId) return;
    set((state) => ({
      classSubjects: {
        ...state.classSubjects,
        [classId]: (state.classSubjects[classId] || []).map((subject) =>
          subject.id === subjectId ? { ...subject, teacherId } : subject
        ),
      },
    }));
    const subjectName = (get().classSubjects[classId] || []).find(s => s.id === subjectId)?.name;
    const teacherName = get().teachers.find(t => t.id === teacherId)?.name || '';
    set((state) => ({
      timetables: state.timetables.map(tt => {
        if (tt.classId !== classId) return tt;
        const nextCells = { ...(tt.cells || {}) };
        Object.entries(nextCells).forEach(([cellKey, cell]) => {
          if (!cell) return;
          const matchesSubject = cell.subjectId === subjectId || (subjectName && cell.subjectName === subjectName);
          if (matchesSubject) {
            nextCells[cellKey] = { ...cell, teacherId, teacherName };
          }
        });
        return { ...tt, cells: nextCells };
      })
    }));
    get().pushHistory();
  },

  removeClassSubject: (classId, subjectId) => {
    if (!classId || !subjectId) return;
    set((state) => ({
      classSubjects: {
        ...state.classSubjects,
        [classId]: (state.classSubjects[classId] || []).filter(
          (subject) => subject.id !== subjectId
        ),
      },
    }));
    get().pushHistory();
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
      locked: false,
    };
    set((state) => ({ groups: [...state.groups, newGroup] }));
      get().pushHistory();
    return newGroup;
  },

  updateGroup: (id, updates, options = {}) => {
    set((state) => ({
      groups: state.groups.map(g => g.id === id ? { ...g, ...updates } : g)
    }));
    if (!options.skipHistory) {
      get().pushHistory();
    }
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
      showSubjects: false,
      locked: false,
      isSelected: false,
    };
    set((state) => ({ timetables: [...state.timetables, newTimetable] }));
      get().pushHistory();
    return newTimetable;
  },

  updateTimetable: (id, updates, options = {}) => {
    set((state) => ({
      timetables: state.timetables.map(t => t.id === id ? { ...t, ...updates } : t)
    }));
    if (!options.skipHistory) {
      get().pushHistory();
    }
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

  updateTextBlock: (id, updates, options = {}) => {
    set((state) => ({
      textBlocks: state.textBlocks.map(b => b.id === id ? { ...b, ...updates } : b)
    }));
    if (!options.skipHistory) {
      get().pushHistory();
    }
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

  updateStructureBlock: (id, updates, options = {}) => {
    set((state) => ({
      structureBlocks: state.structureBlocks.map(b => b.id === id ? { ...b, ...updates } : b)
    }));
    if (!options.skipHistory) {
      get().pushHistory();
    }
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

    const existing = get().teacherPlacements.find(t => t.teacherId === teacherId);
    if (existing) {
      set((state) => ({
        teacherPlacements: state.teacherPlacements.map(t =>
          t.teacherId === teacherId
            ? { ...t, x, y, groupId, isGlobal: groupId === null }
            : t
        )
      }));
      get().pushHistory();
      return { ...existing, x, y, groupId, isGlobal: groupId === null };
    }
    
    const placement = {
      id: generateId('tp'),
      teacherId,
      x,
      y,
      groupId,
      isGlobal: groupId === null,
      locked: false,
    };
    set((state) => ({ teacherPlacements: [...state.teacherPlacements, placement] }));
      get().pushHistory();
    return placement;
  },

  updateTeacherPlacement: (id, updates, options = {}) => {
    set((state) => ({
      teacherPlacements: state.teacherPlacements.map(t => 
        t.id === id ? { ...t, ...updates } : t
      )
    }));
    if (!options.skipHistory) {
      get().pushHistory();
    }
  },

  deleteTeacherPlacement: (id) => {
    const placement = get().teacherPlacements.find(t => t.id === id);
    const teacherId = placement?.teacherId;
    set((state) => ({
      teacherPlacements: state.teacherPlacements.filter(t => t.id !== id),
      arrows: state.arrows.filter(a => 
        a.from.placementId !== id && a.to.placementId !== id
      ),
      classSubjects: teacherId
        ? Object.fromEntries(
            Object.entries(state.classSubjects).map(([classId, subjects]) => [
              classId,
              (subjects || []).map(subject =>
                subject.teacherId === teacherId ? { ...subject, teacherId: null } : subject
              ),
            ])
          )
        : state.classSubjects,
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
      locked: false,
    };
    set((state) => ({ subjectPlacements: [...state.subjectPlacements, placement] }));
      get().pushHistory();
    return placement;
  },

  updateSubjectPlacement: (id, updates, options = {}) => {
    set((state) => ({
      subjectPlacements: state.subjectPlacements.map(s => 
        s.id === id ? { ...s, ...updates } : s
      )
    }));
    if (!options.skipHistory) {
      get().pushHistory();
    }
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

  cutMode: false,

  copy: () => {
    const selected = get().selectedElements;
    if (selected.length > 0) {
      const state = get();
      const payload = selected.map(item => {
        switch (item.type) {
          case 'group':
            return { type: 'group', data: state.groups.find(g => g.id === item.id) };
          case 'timetable':
            return { type: 'timetable', data: state.timetables.find(t => t.id === item.id) };
          case 'teacherPlacement':
            return { type: 'teacherPlacement', data: state.teacherPlacements.find(t => t.id === item.id) };
          case 'subjectPlacement':
            return { type: 'subjectPlacement', data: state.subjectPlacements.find(s => s.id === item.id) };
          case 'textBlock':
            return { type: 'textBlock', data: state.textBlocks.find(t => t.id === item.id) };
          case 'structureBlock':
            return { type: 'structureBlock', data: state.structureBlocks.find(s => s.id === item.id) };
          default:
            return null;
        }
      }).filter(Boolean);
      const placementIds = new Set(
        selected
          .filter(item => item.type === 'teacherPlacement' || item.type === 'subjectPlacement')
          .map(item => item.id)
      );
      const arrows = state.arrows.filter(a =>
        placementIds.has(a.from.placementId) && placementIds.has(a.to.placementId)
      );
      set({ clipboard: { items: payload, arrows }, cutMode: false });
    }
  },

  cut: () => {
    const selected = get().selectedElements;
    if (selected.length === 0) return;
    get().copy();
    set({ cutMode: true });

    selected.forEach(item => {
      switch (item.type) {
        case 'group':
          get().deleteGroup(item.id);
          break;
        case 'timetable':
          get().deleteTimetable(item.id);
          break;
        case 'teacherPlacement':
          get().deleteTeacherPlacement(item.id);
          break;
        case 'subjectPlacement':
          get().deleteSubjectPlacement(item.id);
          break;
        case 'textBlock':
          get().deleteTextBlock(item.id);
          break;
        case 'structureBlock':
          get().deleteStructureBlock(item.id);
          break;
        default:
          break;
      }
    });
  },

  paste: (offsetX = 50, offsetY = 50) => {
    const clipboard = get().clipboard;
    if (!clipboard || !clipboard.items || clipboard.items.length === 0) return;

    const items = clipboard.items;
    const arrows = clipboard.arrows || [];

    let base = items.find(item => item?.data && typeof item.data.x === 'number');
    const cursor = get().lastCursor;
    if (cursor && base?.data) {
      offsetX = cursor.x - base.data.x;
      offsetY = cursor.y - base.data.y;
    }

    const placementMap = new Map();

    items.forEach(item => {
      if (!item?.data) return;
      switch (item.type) {
        case 'group': {
          const group = item.data;
          const newGroup = get().addGroup(group.x + offsetX, group.y + offsetY, group.parentId);
          get().updateGroup(newGroup.id, {
            name: group.name,
            width: group.width,
            height: group.height,
            color: group.color,
            opacity: group.opacity,
            locked: group.locked,
          }, { skipHistory: true });
          break;
        }
        case 'timetable': {
          const tt = item.data;
          const newTimetable = get().addTimetable(tt.x + offsetX, tt.y + offsetY, tt.classId, tt.groupId);
          get().updateTimetable(newTimetable.id, {
            days: tt.days,
            slotsPerDay: tt.slotsPerDay,
            slotDuration: tt.slotDuration,
            breakSlots: tt.breakSlots,
            startTime: tt.startTime,
            cells: tt.cells,
            color: tt.color,
            opacity: tt.opacity,
            locked: tt.locked,
          }, { skipHistory: true });
          break;
        }
        case 'teacherPlacement': {
          const tp = item.data;
          const placement = get().placeTeacher(tp.teacherId, tp.x + offsetX, tp.y + offsetY, tp.groupId);
          if (placement?.id) {
            placementMap.set(tp.id, placement.id);
          }
          break;
        }
        case 'subjectPlacement': {
          const sp = item.data;
          const placement = get().placeSubject(sp.subjectId, sp.x + offsetX, sp.y + offsetY, sp.groupId);
          if (placement?.id) {
            placementMap.set(sp.id, placement.id);
          }
          break;
        }
        case 'textBlock': {
          const tb = item.data;
          const newBlock = get().addTextBlock(tb.x + offsetX, tb.y + offsetY, tb.text);
          get().updateTextBlock(newBlock.id, {
            color: tb.color,
            opacity: tb.opacity,
            zIndex: tb.zIndex,
            locked: tb.locked,
          }, { skipHistory: true });
          break;
        }
        case 'structureBlock': {
          const sb = item.data;
          const newBlock = get().addStructureBlock(sb.x + offsetX, sb.y + offsetY, sb.shape);
          get().updateStructureBlock(newBlock.id, {
            width: sb.width,
            height: sb.height,
            label: sb.label,
            color: sb.color,
            opacity: sb.opacity,
            zIndex: sb.zIndex,
            locked: sb.locked,
          }, { skipHistory: true });
          break;
        }
        default:
          break;
      }
    });

    if (arrows.length > 0) {
      arrows.forEach(arrow => {
        const fromId = placementMap.get(arrow.from.placementId) || arrow.from.placementId;
        const toId = placementMap.get(arrow.to.placementId) || arrow.to.placementId;
        const from = { ...arrow.from, placementId: fromId };
        const to = { ...arrow.to, placementId: toId };
        get().addArrow(from, to, arrow.groupId || null);
      });
    }

    set({ cutMode: false });
    get().pushHistory();
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
      classSubjects: state.classSubjects,
      classWeeks: state.classWeeks,
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

  // ============== Warnings & Scheduling ==============
  computeWarnings: () => {
    const state = get();
    const { teachers, subjects, groups, timetables, teacherPlacements, subjectPlacements, classSubjects } = state;
    const list = [];

    const groupMap = new Map();
    groups.forEach(g => groupMap.set(g.id, g));

    const isGroupAncestor = (ancestorId, childId) => {
      let current = groupMap.get(childId);
      while (current?.parentId) {
        if (current.parentId === ancestorId) return true;
        current = groupMap.get(current.parentId);
      }
      return false;
    };

    teacherPlacements.forEach(tp => {
      if (!tp.groupId) {
        const teacher = teachers.find(t => t.id === tp.teacherId);
        list.push({
          type: 'ungrouped_teacher',
          targetType: 'teacherPlacement',
          targetId: tp.id,
          message: `Teacher ${teacher?.name || tp.teacherId} is placed outside any group.`,
        });
      }
    });

    subjectPlacements.forEach(sp => {
      if (!sp.groupId) {
        const subject = subjects.find(s => s.id === sp.subjectId);
        list.push({
          type: 'ungrouped_subject',
          targetType: 'subjectPlacement',
          targetId: sp.id,
          message: `Subject ${subject?.name || sp.subjectId} is placed outside any group.`,
        });
      }
    });

    timetables.forEach(tt => {
      if (!tt.groupId) {
        const className = tt.classId || 'Unlinked timetable';
        list.push({
          type: 'ungrouped_timetable',
          timetableId: tt.id,
          targetType: 'timetable',
          targetId: tt.id,
          message: `Timetable ${className} is placed outside any group.`,
        });
      }
    });

    timetables.forEach(tt => {
      if (!tt.classId || !tt.groupId) return;
      const subjectsForClass = classSubjects[tt.classId] || [];
      subjectsForClass.forEach(subject => {
        if (!subject.teacherId) return;
        const placements = teacherPlacements.filter(p => p.teacherId === subject.teacherId);
        if (placements.length === 0) {
          const teacherName = teachers.find(t => t.id === subject.teacherId)?.name || subject.teacherId;
          list.push({
            type: 'teacher_unplaced',
            timetableId: tt.id,
            targetType: 'timetable',
            targetId: tt.id,
            message: `Teacher ${teacherName} is assigned to ${subject.name} but not placed in any group.`,
          });
          return;
        }

        const compatible = placements.some(p =>
          p.groupId && (p.groupId === tt.groupId || isGroupAncestor(p.groupId, tt.groupId))
        );

        if (!compatible) {
          const teacherName = teachers.find(t => t.id === subject.teacherId)?.name || subject.teacherId;
          list.push({
            type: 'teacher_group_mismatch',
            timetableId: tt.id,
            targetType: 'timetable',
            targetId: tt.id,
            message: `Teacher ${teacherName} assigned to ${subject.name} is outside the timetable's group.`,
          });
        }
      });
    });

    const slotTeacherMap = new Map();
    timetables.forEach(tt => {
      const cells = tt.cells || {};
      Object.entries(cells).forEach(([cellKey, cell]) => {
        if (!cell?.teacherId) return;
        const key = `${cellKey}||${cell.teacherId}`;
        if (!slotTeacherMap.has(key)) {
          slotTeacherMap.set(key, []);
        }
        slotTeacherMap.get(key).push(tt.id);
      });
    });

    slotTeacherMap.forEach((ttIds, key) => {
      if (ttIds.length <= 1) return;
      const [cellKey, teacherId] = key.split('||');
      const teacherName = teachers.find(t => t.id === teacherId)?.name || teacherId;
      ttIds.forEach(ttId => {
        list.push({
          type: 'teacher_conflict',
          timetableId: ttId,
          targetType: 'timetable',
          targetId: ttId,
          cellKey,
          teacherId,
          message: `Teacher ${teacherName} is scheduled in multiple timetables at ${cellKey}. Try moving one slot or changing the teacher.`,
        });
      });
    });

    return list;
  },

  generateSchedule: (options = {}) => {
    const state = get();
    const warnings = state.computeWarnings();
    if (warnings.length > 0 && !options.ignoreWarnings) {
      return { success: false, warnings };
    }

    const { timetables, classSubjects, classWeeks, teachers } = state;
    const scheduleWarnings = [];

    const occupancy = new Map(); // slotKey -> Set(teacherId)
    const ensureSlotSet = (slotKey) => {
      if (!occupancy.has(slotKey)) {
        occupancy.set(slotKey, new Set());
      }
      return occupancy.get(slotKey);
    };

    const nextTimetables = timetables.map(t => ({
      ...t,
      cells: Object.fromEntries(
        Object.entries(t.cells || {}).filter(([, cell]) => cell?.locked)
      ),
    }));

    // Phase 1: seed locked cells and validate collisions
    nextTimetables.forEach(tt => {
      Object.entries(tt.cells || {}).forEach(([cellKey, cell]) => {
        if (!cell?.locked || !cell.teacherId) return;
        const slotSet = ensureSlotSet(cellKey);
        if (slotSet.has(cell.teacherId)) {
          scheduleWarnings.push({
            type: 'fatal_locked_conflict',
            timetableId: tt.id,
            message: `Fatal conflict: Teacher is locked in multiple timetables at ${cellKey}.`,
          });
        }
        slotSet.add(cell.teacherId);
      });
    });

    if (scheduleWarnings.length > 0) {
      return { success: false, warnings: scheduleWarnings };
    }

    const subjectKey = (ttId, subjectId) => `${ttId}::${subjectId}`;
    const subjectEntries = [];
    const subjectDayCounts = new Map(); // key -> Map(day -> count)

    nextTimetables.forEach(tt => {
      const subjectsForClass = classSubjects[tt.classId] || [];
      const totalWeeks = classWeeks[tt.classId] || 15;

      const lockedCounts = new Map();
      Object.entries(tt.cells || {}).forEach(([cellKey, cell]) => {
        if (!cell?.locked || !cell.subjectId) return;
        lockedCounts.set(cell.subjectId, (lockedCounts.get(cell.subjectId) || 0) + 1);
        const day = cellKey.split('-')[0];
        const key = subjectKey(tt.id, cell.subjectId);
        if (!subjectDayCounts.has(key)) {
          subjectDayCounts.set(key, new Map());
        }
        const dayMap = subjectDayCounts.get(key);
        dayMap.set(day, (dayMap.get(day) || 0) + 1);
      });

      subjectsForClass.forEach(subject => {
        if (!subject.hours || !subject.id) return;
        const required = Math.ceil(subject.hours / totalWeeks);
        const locked = lockedCounts.get(subject.id) || 0;
        const remaining = Math.max(0, required - locked);
        if (remaining === 0) return;
        subjectEntries.push({
          timetableId: tt.id,
          classId: tt.classId,
          subjectId: subject.id,
          subjectName: subject.name,
          teacherId: subject.teacherId || null,
          remaining,
        });
      });
    });

    const teacherUsage = new Map();
    subjectEntries.forEach(entry => {
      if (!entry.teacherId) return;
      teacherUsage.set(entry.teacherId, (teacherUsage.get(entry.teacherId) || 0) + entry.remaining);
    });

    const getTimetable = (id) => nextTimetables.find(t => t.id === id);

    const maxPerDay = 2;

    const buildSlots = (tt) => {
      const slots = [];
      const days = Array.isArray(tt.days) ? tt.days : [];
      const slotsPerDay = tt.slotsPerDay || 0;
      for (let i = 0; i < days.length; i += 1) {
        for (let s = 0; s < slotsPerDay; s += 1) {
          const key = `${days[i]}-${s}`;
          if (tt.cells?.[key]) continue;
          slots.push({ day: days[i], slotIndex: s, key });
        }
      }
      return slots;
    };

    const scoreSlot = (tt, entry, slot) => {
      let score = 0;
      const key = subjectKey(tt.id, entry.subjectId);
      const dayMap = subjectDayCounts.get(key);
      const dayCount = dayMap?.get(slot.day) || 0;
      if (dayCount === 0) score += 2;
      if (dayCount >= 1) score -= 1;

      const prevKey = `${slot.day}-${slot.slotIndex - 1}`;
      const nextKey = `${slot.day}-${slot.slotIndex + 1}`;
      if (tt.cells?.[prevKey] || tt.cells?.[nextKey]) {
        score += 1; // reduce gaps by clustering
      }

      return score;
    };

    const canPlace = (tt, entry, slot) => {
      if (tt.cells?.[slot.key]) return false;
      const key = subjectKey(tt.id, entry.subjectId);
      const dayMap = subjectDayCounts.get(key);
      const dayCount = dayMap?.get(slot.day) || 0;
      if (dayCount >= maxPerDay) return false;
      if (entry.teacherId) {
        const slotSet = ensureSlotSet(slot.key);
        if (slotSet.has(entry.teacherId)) return false;
      }
      return true;
    };

    const place = (tt, entry, slot) => {
      const teacherName = entry.teacherId
        ? (teachers.find(t => t.id === entry.teacherId)?.name || 'Teacher')
        : '';
      tt.cells[slot.key] = {
        subjectId: entry.subjectId,
        subjectName: entry.subjectName,
        teacherId: entry.teacherId,
        teacherName,
      };
      const key = subjectKey(tt.id, entry.subjectId);
      if (!subjectDayCounts.has(key)) {
        subjectDayCounts.set(key, new Map());
      }
      const dayMap = subjectDayCounts.get(key);
      dayMap.set(slot.day, (dayMap.get(slot.day) || 0) + 1);
      if (entry.teacherId) {
        ensureSlotSet(slot.key).add(entry.teacherId);
      }
      entry.remaining -= 1;
    };

    const unplace = (tt, entry, slot) => {
      delete tt.cells[slot.key];
      const key = subjectKey(tt.id, entry.subjectId);
      const dayMap = subjectDayCounts.get(key);
      if (dayMap) {
        dayMap.set(slot.day, Math.max(0, (dayMap.get(slot.day) || 1) - 1));
      }
      if (entry.teacherId) {
        const slotSet = ensureSlotSet(slot.key);
        slotSet.delete(entry.teacherId);
      }
      entry.remaining += 1;
    };

    const pickNextEntry = () => {
      const candidates = subjectEntries.filter(e => e.remaining > 0);
      if (candidates.length === 0) return null;
      candidates.sort((a, b) => {
        const teacherWeightA = teacherUsage.get(a.teacherId) || 0;
        const teacherWeightB = teacherUsage.get(b.teacherId) || 0;
        const scoreA = a.remaining + teacherWeightA * 2;
        const scoreB = b.remaining + teacherWeightB * 2;
        return scoreB - scoreA;
      });
      return candidates[0];
    };

    const backtrack = () => {
      const entry = pickNextEntry();
      if (!entry) return true;

      const tt = getTimetable(entry.timetableId);
      if (!tt) return false;

      const slots = buildSlots(tt)
        .filter(slot => canPlace(tt, entry, slot))
        .sort((a, b) => scoreSlot(tt, entry, b) - scoreSlot(tt, entry, a));

      for (let i = 0; i < slots.length; i += 1) {
        const slot = slots[i];
        place(tt, entry, slot);
        if (backtrack()) return true;
        unplace(tt, entry, slot);
      }

      return false;
    };

    const success = backtrack();

    if (!success) {
      scheduleWarnings.push({
        type: 'slot_collision',
        message: 'Could not fit all subjects without collisions. Increase weeks or reduce hours.',
      });
      return { success: false, warnings: scheduleWarnings };
    }

    set({ timetables: nextTimetables });
    get().pushHistory();
    return { success: true, warnings: [] };
  },

  resetTimetable: (timetableId) => {
    const nextTimetables = get().timetables.map(t => {
      if (t.id !== timetableId) return t;
      const lockedCells = Object.fromEntries(
        Object.entries(t.cells || {}).filter(([, cell]) => cell?.locked)
      );
      return { ...t, cells: lockedCells };
    });
    set({ timetables: nextTimetables });
    get().pushHistory();
  },

  resetAllTimetables: () => {
    const nextTimetables = get().timetables.map(t => ({
      ...t,
      cells: Object.fromEntries(
        Object.entries(t.cells || {}).filter(([, cell]) => cell?.locked)
      ),
    }));
    set({ timetables: nextTimetables });
    get().pushHistory();
  },

  regenerateDay: (timetableId, day) => {
    const state = get();
    const tt = state.timetables.find(t => t.id === timetableId);
    if (!tt) return { success: false, warnings: [{ message: 'Timetable not found.' }] };

    const { classSubjects, classWeeks, teachers } = state;
    const subjectsForClass = classSubjects[tt.classId] || [];
    const totalWeeks = classWeeks[tt.classId] || 15;

    if (!subjectsForClass.length) {
      return { success: false, warnings: [{ message: 'No subjects available to schedule.' }] };
    }

    const days = Array.isArray(tt.days) ? tt.days : [];
    if (!days.includes(day)) {
      return { success: false, warnings: [{ message: `Day ${day} is not part of this timetable.` }] };
    }

    const slotsPerDay = tt.slotsPerDay || 0;
    if (slotsPerDay <= 0) {
      return { success: false, warnings: [{ message: 'No available slots to schedule.' }] };
    }

    const occupancy = new Map();
    const ensureTeacherSet = (teacherId) => {
      if (!occupancy.has(teacherId)) {
        occupancy.set(teacherId, new Set());
      }
      return occupancy.get(teacherId);
    };

    state.timetables.forEach(table => {
      const cells = table.cells || {};
      Object.entries(cells).forEach(([cellKey, cell]) => {
        if (!cell?.teacherId) return;
        if (table.id === timetableId && cellKey.startsWith(`${day}-`) && !cell.locked) {
          return;
        }
        ensureTeacherSet(cell.teacherId).add(cellKey);
      });
    });

    const existingCells = { ...(tt.cells || {}) };
    const lockedSlots = new Set();
    Object.entries(existingCells).forEach(([cellKey, cell]) => {
      if (cell?.locked) {
        lockedSlots.add(cellKey);
      }
    });

    const nextCells = { ...existingCells };
    const clearedKeys = [];
    Object.keys(nextCells).forEach((cellKey) => {
      if (cellKey.startsWith(`${day}-`) && !nextCells[cellKey]?.locked) {
        clearedKeys.push(cellKey);
        delete nextCells[cellKey];
      }
    });

    const lockedSubjectCounts = new Map();
    Object.values(nextCells).forEach(cell => {
      if (cell?.subjectId) {
        lockedSubjectCounts.set(cell.subjectId, (lockedSubjectCounts.get(cell.subjectId) || 0) + 1);
      }
    });

    const subjectNeeds = subjectsForClass
      .filter(subject => (subject.hours || 0) > 0)
      .map(subject => {
        const baseSlots = Math.ceil((subject.hours || 0) / totalWeeks);
        const scheduledCount = lockedSubjectCounts.get(subject.id) || 0;
        return {
          ...subject,
          weeklySlots: Math.max(0, baseSlots - scheduledCount),
        };
      })
      .filter(subject => subject.weeklySlots > 0)
      .sort((a, b) => b.weeklySlots - a.weeklySlots);

    const perDayCounts = new Map();
    Object.entries(nextCells).forEach(([cellKey, cell]) => {
      if (!cell?.subjectId) return;
      const dayName = cellKey.split('-')[0];
      const key = `${cell.subjectId}-${dayName}`;
      perDayCounts.set(key, (perDayCounts.get(key) || 0) + 1);
    });

    const getDayCount = (subjectId, dayName) => perDayCounts.get(`${subjectId}-${dayName}`) || 0;
    const incrementDayCount = (subjectId, dayName) => {
      const key = `${subjectId}-${dayName}`;
      perDayCounts.set(key, getDayCount(subjectId, dayName) + 1);
    };

    const availableSlots = [];
    for (let i = 0; i < slotsPerDay; i += 1) {
      const key = `${day}-${i}`;
      if (!lockedSlots.has(key)) {
        availableSlots.push({ key, slotIndex: i });
      }
    }

    const shuffledSlots = [...availableSlots].sort(() => Math.random() - 0.5);
    const warnings = [];

    subjectNeeds.forEach(subject => {
      for (let i = 0; i < subject.weeklySlots; i += 1) {
        let assigned = false;
        for (let attempt = 0; attempt < shuffledSlots.length; attempt += 1) {
          const slot = shuffledSlots[attempt];
          if (nextCells[slot.key]) continue;
          if (getDayCount(subject.id, day) >= 2) continue;

          if (subject.teacherId) {
            const teacherSet = ensureTeacherSet(subject.teacherId);
            if (teacherSet.has(slot.key)) {
              continue;
            }
            teacherSet.add(slot.key);
          }

          const teacherName = subject.teacherId
            ? (teachers.find(t => t.id === subject.teacherId)?.name || 'Teacher')
            : '';

          nextCells[slot.key] = {
            subjectId: subject.id,
            subjectName: subject.name,
            teacherId: subject.teacherId || null,
            teacherName,
          };
          incrementDayCount(subject.id, day);
          assigned = true;
          break;
        }

        if (!assigned) {
          warnings.push({ message: `Unable to schedule ${subject.name} on ${day}.` });
          break;
        }
      }
    });

    const nextTimetables = state.timetables.map(t =>
      t.id === timetableId ? { ...t, cells: nextCells } : t
    );
    set({ timetables: nextTimetables });
    get().pushHistory();
    return { success: warnings.length === 0, warnings };
  },

  // ============== Save/Load ==============
  saveToBackend: async () => {
    const state = get();
    try {
      await fetch(`${API_BASE}/canvas`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          classSubjects: state.classSubjects,
          classWeeks: state.classWeeks,
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
        classSubjects: data.classSubjects || {},
        classWeeks: data.classWeeks || {},
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

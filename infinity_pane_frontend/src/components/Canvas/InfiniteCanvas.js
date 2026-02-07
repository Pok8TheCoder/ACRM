/**
 * InfiniteCanvas - The main 2D infinite pane
 * Supports unlimited zoom and pan in all directions
 */

import React, { useRef, useCallback, useEffect, useState } from 'react';
import useStore from '../../store/useStore';
import GroupBlock from '../Blocks/GroupBlock';
import TimetableBlock from '../Blocks/TimetableBlock';
import TeacherBlock from '../Blocks/TeacherBlock';
import SubjectBlock from '../Blocks/SubjectBlock';
import TextBlock from '../Blocks/TextBlock';
import StructureBlock from '../Blocks/StructureBlock';
import ArrowConnection from '../Arrows/ArrowConnection';
import FreeArrowConnection from '../Arrows/FreeArrowConnection';
import ArrowDrawing from '../Arrows/ArrowDrawing';
import ClassSubjectArrowConnection from '../Arrows/ClassSubjectArrowConnection';
import GridBackground from './GridBackground';
import { Sparkles } from 'lucide-react';
import './InfiniteCanvas.css';

const InfiniteCanvas = () => {
  const canvasRef = useRef(null);
  const hoveredSubjectRowRef = useRef(null);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [selectionBox, setSelectionBox] = useState(null);
  
  const {
    canvas,
    activeTool,
    setCanvasPosition,
    setZoom,
    setPanning,
    groups,
    timetables,
    arrows,
    freeArrows,
    teacherPlacements,
    subjectPlacements,
    textBlocks,
    structureBlocks,
    classSubjects,
    addGroup,
    addTimetable,
    addTextBlock,
    addStructureBlock,
    setActiveTool,
    placeTeacher,
    placeSubject,
    arrowDrawing,
    updateArrowDrawing,
    freeArrowDrawing,
    startFreeArrowDrawing,
    updateFreeArrowDrawing,
    finishFreeArrowDrawing,
    cancelArrowDrawing,
    assignTeacherToClassSubject,
    selectedElements,
    deselectAll,
    setSelectedElements,
    hideContextMenu,
    showContextMenu,
    classes,
    teachers,
    subjects,
    deleteGroup,
    deleteTimetable,
    deleteTeacherPlacement,
    deleteSubjectPlacement,
    deleteArrow,
    deleteFreeArrow,
    deleteTextBlock,
    deleteStructureBlock,
    undo,
    redo,
    generateSchedule,
    resetAllTimetables,
    copy,
    paste,
    cut,
    setLastCursor,
  } = useStore();

  // Convert screen coordinates to canvas coordinates
  const screenToCanvas = useCallback((screenX, screenY) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    
    return {
      x: (screenX - rect.left - rect.width / 2 - canvas.x) / canvas.zoom,
      y: (screenY - rect.top - rect.height / 2 - canvas.y) / canvas.zoom,
    };
  }, [canvas.x, canvas.y, canvas.zoom]);

  const classSubjectArrows = React.useMemo(() => {
    const entries = [];

    timetables.forEach((timetable) => {
      if (!timetable.classId) return;
      if (!timetable.showSubjects) return;
      const subjects = classSubjects[timetable.classId] || [];
      if (subjects.length === 0) return;

      subjects.forEach((subject) => {
        if (!subject.teacherId) return;

        const placementsForTeacher = teacherPlacements.filter(p => p.teacherId === subject.teacherId);
        if (placementsForTeacher.length === 0) return;

        const preferred = timetable.groupId
          ? placementsForTeacher.find(p => p.groupId === timetable.groupId) || placementsForTeacher[0]
          : placementsForTeacher[0];

        const rowElements = document.querySelectorAll(
          `[data-timetable-id="${timetable.id}"][data-subject-id="${subject.id}"]`
        );
        if (!rowElements.length) return;

        rowElements.forEach((rowElement, index) => {
          const rect = rowElement.getBoundingClientRect();
          const centerX = rect.left + rect.width / 2;
          const centerY = rect.top + rect.height / 2;
          const to = screenToCanvas(centerX, centerY);

          entries.push({
            key: `${timetable.id}-${subject.id}-${preferred.id}-${index}`,
            from: { x: preferred.x, y: preferred.y },
            to,
          });
        });
      });
    });

    return entries;
  }, [timetables, classSubjects, teacherPlacements, screenToCanvas]);

  const handleCanvasDoubleClick = useCallback((e) => {
    const isCanvasBackground = e.target === canvasRef.current || 
                                e.target.classList.contains('canvas-content') ||
                                e.target.classList.contains('grid-background') ||
                                e.target.classList.contains('grid-minor') ||
                                e.target.classList.contains('grid-major');
    if (!isCanvasBackground) return;
    if (activeTool !== 'select') return;

    e.preventDefault();
    deselectAll();
    const rect = canvasRef.current?.getBoundingClientRect();
    const startX = rect ? e.clientX - rect.left : e.clientX;
    const startY = rect ? e.clientY - rect.top : e.clientY;
    setSelectionBox({
      active: true,
      startClientX: e.clientX,
      startClientY: e.clientY,
      x: startX,
      y: startY,
      w: 0,
      h: 0,
    });
  }, [activeTool, deselectAll, setSelectionBox]);

  // Handle wheel for zooming (always zoom, no Ctrl needed)
  const handleWheel = useCallback((e) => {
    e.preventDefault();
    
    // Always zoom with scroll
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    const newZoom = canvas.zoom * delta;
    
    // Zoom towards cursor position
    const rect = canvasRef.current.getBoundingClientRect();
    const cursorX = e.clientX - rect.left - rect.width / 2;
    const cursorY = e.clientY - rect.top - rect.height / 2;
    
    const newX = canvas.x - cursorX * (delta - 1);
    const newY = canvas.y - cursorY * (delta - 1);
    
    setZoom(newZoom);
    setCanvasPosition(newX, newY);
  }, [canvas.x, canvas.y, canvas.zoom, setCanvasPosition, setZoom]);

  // Handle mouse down for panning (default behavior)
  const handleMouseDown = useCallback((e) => {
    // Left click starts panning by default
    if (e.button === 0 || e.button === 1) {
      // Check if clicking on canvas background
      const isCanvasBackground = e.target === canvasRef.current || 
                                  e.target.classList.contains('canvas-content') ||
                                  e.target.classList.contains('grid-background') ||
                                  e.target.classList.contains('grid-minor') ||
                                  e.target.classList.contains('grid-major');
      
      if (isCanvasBackground) {
        if (activeTool === 'select' && e.detail === 2) {
          return;
        }
        if (activeTool === 'arrow' && e.button === 0) {
          const pos = screenToCanvas(e.clientX, e.clientY);
          startFreeArrowDrawing({ x: pos.x, y: pos.y });
          return;
        }
        if (selectionBox?.active) {
          return;
        }
        e.preventDefault();
        setPanning(true, { x: e.clientX - canvas.x, y: e.clientY - canvas.y });
        deselectAll();
        hideContextMenu();
        
        if (arrowDrawing) {
          cancelArrowDrawing();
        }
      }
    }
  }, [activeTool, canvas.x, canvas.y, setPanning, deselectAll, hideContextMenu, arrowDrawing, cancelArrowDrawing, screenToCanvas, startFreeArrowDrawing, selectionBox]);

  // Handle mouse move
  const handleMouseMove = useCallback((e) => {
    if (canvas.isPanning) {
      setCanvasPosition(e.clientX - canvas.panStart.x, e.clientY - canvas.panStart.y);
    }
    
    if (arrowDrawing) {
      const pos = screenToCanvas(e.clientX, e.clientY);
      updateArrowDrawing(pos.x, pos.y);
    }
    if (freeArrowDrawing) {
      const pos = screenToCanvas(e.clientX, e.clientY);
      updateFreeArrowDrawing(pos.x, pos.y);
    }
    const cursorPos = screenToCanvas(e.clientX, e.clientY);
    setLastCursor(cursorPos.x, cursorPos.y);
    if (arrowDrawing?.from?.type === 'teacher') {
      const target = document.elementFromPoint(e.clientX, e.clientY);
      const row = target?.closest?.('.timetable-subject-row');
      const current = hoveredSubjectRowRef.current;

      if (current && current !== row) {
        current.classList.remove('subject-row-hover');
      }

      if (row && row !== current) {
        row.classList.add('subject-row-hover');
        hoveredSubjectRowRef.current = row;
      }

      if (!row) {
        hoveredSubjectRowRef.current = null;
      }
    }
    if (selectionBox?.active) {
      const rect = canvasRef.current?.getBoundingClientRect();
      const currentX = rect ? e.clientX - rect.left : e.clientX;
      const currentY = rect ? e.clientY - rect.top : e.clientY;
      const startX = rect ? selectionBox.startClientX - rect.left : selectionBox.startClientX;
      const startY = rect ? selectionBox.startClientY - rect.top : selectionBox.startClientY;
      const x = Math.min(startX, currentX);
      const y = Math.min(startY, currentY);
      const w = Math.abs(currentX - startX);
      const h = Math.abs(currentY - startY);
      setSelectionBox({ ...selectionBox, x, y, w, h, endClientX: e.clientX, endClientY: e.clientY });
    }
  }, [canvas.isPanning, canvas.panStart, setCanvasPosition, arrowDrawing, updateArrowDrawing, freeArrowDrawing, updateFreeArrowDrawing, screenToCanvas, selectionBox]);

  // Handle mouse up
  const handleMouseUp = useCallback((e) => {
    if (canvas.isPanning) {
      setPanning(false);
    }
    if (arrowDrawing && e && arrowDrawing.from?.type === 'teacher') {
      const row = hoveredSubjectRowRef.current;
      const classId = row?.dataset?.classId;
      const subjectId = row?.dataset?.subjectId;
      if (classId && subjectId) {
        assignTeacherToClassSubject(classId, subjectId, arrowDrawing.from.id);
        cancelArrowDrawing();
      }
    }
    if (freeArrowDrawing && e) {
      const pos = screenToCanvas(e.clientX, e.clientY);
      finishFreeArrowDrawing({ x: pos.x, y: pos.y });
    }
    if (selectionBox?.active) {
      const start = screenToCanvas(selectionBox.startClientX, selectionBox.startClientY);
      const end = screenToCanvas(selectionBox.endClientX ?? selectionBox.startClientX, selectionBox.endClientY ?? selectionBox.startClientY);

      const minX = Math.min(start.x, end.x);
      const maxX = Math.max(start.x, end.x);
      const minY = Math.min(start.y, end.y);
      const maxY = Math.max(start.y, end.y);

      const rectsIntersect = (ax, ay, aw, ah) => {
        return ax < maxX && ax + aw > minX && ay < maxY && ay + ah > minY;
      };

      const selected = [];

      groups.forEach(g => {
        if (rectsIntersect(g.x, g.y, g.width, g.height)) {
          selected.push({ type: 'group', id: g.id });
        }
      });

      timetables.forEach(t => {
        const breakCount = Array.isArray(t.breakSlots) ? t.breakSlots.length : 0;
        const rows = t.slotsPerDay + breakCount;
        const totalWidth = 60 + (t.days.length * 100);
        const totalHeight = 36 + 30 + rows * 40;
        if (rectsIntersect(t.x, t.y, totalWidth, totalHeight)) {
          selected.push({ type: 'timetable', id: t.id });
        }
      });

      teacherPlacements.forEach(tp => {
        if (rectsIntersect(tp.x - 60, tp.y - 25, 140, 50)) {
          selected.push({ type: 'teacherPlacement', id: tp.id });
        }
      });

      subjectPlacements.forEach(sp => {
        if (rectsIntersect(sp.x - 50, sp.y - 20, 120, 40)) {
          selected.push({ type: 'subjectPlacement', id: sp.id });
        }
      });

      textBlocks.forEach(tb => {
        if (rectsIntersect(tb.x, tb.y, 220, 30)) {
          selected.push({ type: 'textBlock', id: tb.id });
        }
      });

      structureBlocks.forEach(sb => {
        if (rectsIntersect(sb.x, sb.y, sb.width, sb.height)) {
          selected.push({ type: 'structureBlock', id: sb.id });
        }
      });

      setSelectedElements(selected);
      setSelectionBox(null);
    }
  }, [canvas.isPanning, setPanning, arrowDrawing, assignTeacherToClassSubject, cancelArrowDrawing, freeArrowDrawing, screenToCanvas, finishFreeArrowDrawing, selectionBox, groups, timetables, teacherPlacements, subjectPlacements, textBlocks, structureBlocks, setSelectedElements]);

  useEffect(() => {
    if (!arrowDrawing) {
      const current = hoveredSubjectRowRef.current;
      if (current) {
        current.classList.remove('subject-row-hover');
      }
      hoveredSubjectRowRef.current = null;
    }
  }, [arrowDrawing]);

  // Handle context menu (right-click)
  const handleContextMenu = useCallback((e) => {
    e.preventDefault();
    const pos = screenToCanvas(e.clientX, e.clientY);
    
    showContextMenu(e.clientX, e.clientY, 'canvas', null, [
      { 
        label: 'Add Group', 
        icon: '📦', 
        action: () => addGroup(pos.x, pos.y) 
      },
      { 
        label: 'Add Timetable', 
        icon: '📅', 
        action: () => {
          if (classes.length > 0) {
            addTimetable(pos.x, pos.y, classes[0].id, null);
          }
        },
        disabled: classes.length === 0,
      },
      { type: 'divider' },
      { 
        label: 'Reset View', 
        icon: '🔄', 
        action: () => {
          setCanvasPosition(0, 0);
          setZoom(1);
        }
      },
    ]);
  }, [screenToCanvas, showContextMenu, addGroup, addTimetable, classes, setCanvasPosition, setZoom]);

  // Handle drop from sidebars
  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDraggingOver(false);
    
    const data = e.dataTransfer.getData('application/json');
    if (!data) return;
    
    const item = JSON.parse(data);
    const pos = screenToCanvas(e.clientX, e.clientY);
    
    // Check if dropped on a group
    const targetGroup = groups.find(g => {
      const inX = pos.x >= g.x && pos.x <= g.x + g.width;
      const inY = pos.y >= g.y && pos.y <= g.y + g.height;
      return inX && inY;
    });
    
    if (item.type === 'tool') {
      if (item.tool === 'group') {
        addGroup(pos.x, pos.y);
      } else if (item.tool === 'timetable') {
        if (classes.length > 0) {
          addTimetable(pos.x, pos.y, classes[0].id, null);
        }
      } else if (item.tool === 'arrow') {
        setActiveTool('arrow');
      } else if (item.tool === 'text') {
        addTextBlock(pos.x, pos.y);
      } else if (item.tool === 'structure') {
        addStructureBlock(pos.x, pos.y, item.shape || 'rectangle');
      }
      return;
    }

    if (item.type === 'teacher') {
      placeTeacher(item.id, pos.x, pos.y, targetGroup?.id || null);
    } else if (item.type === 'subject') {
      placeSubject(item.id, pos.x, pos.y, targetGroup?.id || null);
    } else if (item.type === 'class') {
      addTimetable(pos.x, pos.y, item.id, targetGroup?.id || null);
    }
  }, [screenToCanvas, groups, placeTeacher, placeSubject, addGroup, addTimetable, addTextBlock, addStructureBlock, classes, setActiveTool]);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDraggingOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDraggingOver(false);
  }, []);

  const handleZoomIn = useCallback(() => {
    setZoom(canvas.zoom * 1.2);
  }, [canvas.zoom, setZoom]);

  const handleZoomOut = useCallback(() => {
    setZoom(canvas.zoom / 1.2);
  }, [canvas.zoom, setZoom]);

  const handleFitToScreen = useCallback(() => {
    setCanvasPosition(0, 0);
    setZoom(1);
  }, [setCanvasPosition, setZoom]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      
      switch (e.key) {
        case 'Escape':
          cancelArrowDrawing();
          deselectAll();
          break;
        case 'Delete':
        case 'Backspace':
          // Delete selected elements
          selectedElements.forEach(item => {
            switch (item.type) {
              case 'group':
                deleteGroup(item.id);
                break;
              case 'timetable':
                deleteTimetable(item.id);
                break;
              case 'teacherPlacement':
                deleteTeacherPlacement(item.id);
                break;
              case 'subjectPlacement':
                deleteSubjectPlacement(item.id);
                break;
              case 'arrow':
                deleteArrow(item.id);
                break;
              case 'freeArrow':
                deleteFreeArrow(item.id);
                break;
              case 'textBlock':
                deleteTextBlock(item.id);
                break;
              case 'structureBlock':
                deleteStructureBlock(item.id);
                break;
              default:
                break;
            }
          });
          deselectAll();
          break;
        case '0':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            setCanvasPosition(0, 0);
            setZoom(1);
          }
          break;
        case 'z':
        case 'Z':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            undo();
          }
          break;
        case 'c':
        case 'C':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            copy();
          }
          break;
        case 'x':
        case 'X':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            cut();
          }
          break;
        case 'v':
        case 'V':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            paste();
          }
          break;
        case 'r':
        case 'R':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            redo();
          }
          break;
        case 'y':
        case 'Y':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            redo();
          }
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [cancelArrowDrawing, deselectAll, selectedElements, deleteGroup, deleteTimetable, deleteTeacherPlacement, deleteSubjectPlacement, deleteArrow, deleteFreeArrow, deleteTextBlock, deleteStructureBlock, setCanvasPosition, setZoom, undo, redo]);

  // Attach wheel listener with passive: false
  useEffect(() => {
    const element = canvasRef.current;
    if (element) {
      element.addEventListener('wheel', handleWheel, { passive: false });
      return () => element.removeEventListener('wheel', handleWheel);
    }
  }, [handleWheel]);

  // Get teacher/subject data for placements
  const getTeacherData = (teacherId) => teachers.find(t => t.id === teacherId);
  const getSubjectData = (subjectId) => subjects.find(s => s.id === subjectId);

  return (
    <div 
      ref={canvasRef}
      className={`infinite-canvas ${isDraggingOver ? 'dragging-over' : ''} ${canvas.isPanning ? 'panning' : ''}`}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onDoubleClick={handleCanvasDoubleClick}
      onContextMenu={handleContextMenu}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
    >
      {/* Grid Background */}
      <GridBackground zoom={canvas.zoom} x={canvas.x} y={canvas.y} />
      
      {/* Transformed Content */}
      <div 
        className="canvas-content"
        style={{
          transform: `translate(${canvas.x}px, ${canvas.y}px) scale(${canvas.zoom})`,
        }}
      >
        {/* Arrow Connections (rendered first, below blocks) */}
        <svg className="arrows-layer">
          {arrows.map(arrow => (
            <ArrowConnection 
              key={arrow.id}
              arrow={arrow} 
              teacherPlacements={teacherPlacements}
              subjectPlacements={subjectPlacements}
            />
          ))}
          {classSubjectArrows.map((entry) => (
            <ClassSubjectArrowConnection
              key={entry.key}
              from={entry.from}
              to={entry.to}
            />
          ))}
          {freeArrows.map(arrow => (
            <FreeArrowConnection key={arrow.id} arrow={arrow} />
          ))}
          {arrowDrawing && <ArrowDrawing drawing={arrowDrawing} label="Click target to connect" />}
          {freeArrowDrawing && <ArrowDrawing drawing={freeArrowDrawing} label="Release to place arrow" />}
        </svg>
        
        {/* Groups */}
        {groups.map(group => (
          <GroupBlock 
            key={group.id} 
            group={group}
            screenToCanvas={screenToCanvas}
          />
        ))}
        
        {/* Timetables */}
        {timetables.map(timetable => (
          <TimetableBlock 
            key={timetable.id} 
            timetable={timetable}
            screenToCanvas={screenToCanvas}
          />
        ))}

        {/* Text Blocks */}
        {textBlocks.map(block => (
          <TextBlock key={block.id} block={block} />
        ))}

        {/* Structure Blocks */}
        {structureBlocks.map(block => (
          <StructureBlock key={block.id} block={block} />
        ))}
        
        {/* Teacher Placements */}
        {teacherPlacements.map(placement => (
          <TeacherBlock
            key={placement.id}
            placement={placement}
            teacher={getTeacherData(placement.teacherId)}
            screenToCanvas={screenToCanvas}
          />
        ))}
        
        {/* Subject Placements */}
        {subjectPlacements.map(placement => (
          <SubjectBlock
            key={placement.id}
            placement={placement}
            subject={getSubjectData(placement.subjectId)}
            screenToCanvas={screenToCanvas}
          />
        ))}
      </div>
      
      {/* Top left panel */}
      <div className="top-panel">
        <div className="zoom-controls">
          <button className="zoom-btn" onClick={handleZoomOut} title="Zoom Out">
            −
          </button>
          <div className="zoom-indicator" onClick={handleFitToScreen} title="Click to reset">
            {Math.round(canvas.zoom * 100)}%
          </div>
          <button className="zoom-btn" onClick={handleZoomIn} title="Zoom In">
            +
          </button>
        </div>
        <div className="coords-indicator">
          x: {Math.round(-canvas.x / canvas.zoom)}, y: {Math.round(-canvas.y / canvas.zoom)}
        </div>
      </div>

      {/* Bottom right panel */}
      <div className="bottom-panel">
        <button
          className="auto-schedule-btn reset"
          onClick={() => resetAllTimetables()}
          title="Reset All Timetables"
        >
          Reset Timetables
        </button>
        <button
          className="auto-schedule-btn"
          onClick={() => {
            const result = generateSchedule();
            if (!result.success) {
              const shouldOverride = window.confirm(
                `Warnings found:\n\n${result.warnings.map(w => w.message).join('\n')}\n\nOverride and re-generate?`
              );
              if (shouldOverride) {
                generateSchedule({ ignoreWarnings: true });
              }
            }
          }}
          title="Auto-Schedule"
        >
          <Sparkles size={16} />
          Auto-Schedule
        </button>
      </div>

      {selectionBox?.active && (
        <div
          className="selection-rect"
          style={{ left: selectionBox.x, top: selectionBox.y, width: selectionBox.w, height: selectionBox.h }}
        />
      )}
    </div>
  );
};

export default InfiniteCanvas;

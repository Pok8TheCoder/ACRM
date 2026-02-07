/**
 * TeacherBlock - Draggable teacher placement on canvas
 */

import React, { useState, useCallback, useRef } from 'react';
import useStore from '../../store/useStore';
import { Trash2, ArrowUpRight, Info, Palette, Lock, Unlock } from 'lucide-react';
import './Blocks.css';

const TeacherBlock = ({ placement, teacher }) => {
  const [isDragging, setIsDragging] = useState(false);
  const blockRef = useRef(null);

  const {
    updateTeacherPlacement,
    deleteTeacherPlacement,
    selectElement,
    isSelected,
    showContextMenu,
    showModal,
    startArrowDrawing,
    arrowDrawing,
    finishArrowDrawing,
    canvas,
    setPanning,
    pushHistory,
    highlightTarget,
  } = useStore();

  const selected = isSelected('teacherPlacement', placement.id);
  const isGlobal = placement.groupId === null;
  const displayColor = placement.color || teacher?.color || '#90caf9';

  // Handle dragging
  const handleMouseDown = useCallback((e) => {
    if (!teacher) return;
    if (e.button !== 0) return;

    // If we're drawing an arrow, finish it here
    if (arrowDrawing) {
      finishArrowDrawing({
        type: 'teacher',
        id: teacher.id,
        placementId: placement.id,
        x: placement.x,
        y: placement.y,
      });
      return;
    }

    if (placement.locked) {
      setPanning(true, { x: e.clientX - canvas.x, y: e.clientY - canvas.y });
      return;
    }

    e.stopPropagation();

    selectElement('teacherPlacement', placement.id, e.shiftKey);

    const startX = e.clientX;
    const startY = e.clientY;
    const startPlaceX = placement.x;
    const startPlaceY = placement.y;

    setIsDragging(true);

    const handleMouseMove = (moveEvent) => {
      const zoom = useStore.getState().canvas.zoom;
      const deltaX = (moveEvent.clientX - startX) / zoom;
      const deltaY = (moveEvent.clientY - startY) / zoom;
      
      updateTeacherPlacement(placement.id, {
        x: startPlaceX + deltaX,
        y: startPlaceY + deltaY,
      }, { skipHistory: true });
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      
      // Check if dropped on a group
      const state = useStore.getState();
      const tp = state.teacherPlacements.find(t => t.id === placement.id);
      if (!tp) return;
      
      const pos = { x: tp.x, y: tp.y };
      const targetGroup = state.groups.find(g => {
        const inX = pos.x >= g.x && pos.x <= g.x + g.width;
        const inY = pos.y >= g.y && pos.y <= g.y + g.height;
        return inX && inY;
      });
      
      if (targetGroup && targetGroup.id !== placement.groupId) {
        updateTeacherPlacement(placement.id, { groupId: targetGroup.id, isGlobal: false });
      } else if (!targetGroup && placement.groupId) {
        updateTeacherPlacement(placement.id, { groupId: null, isGlobal: true });
      }
      
      pushHistory();
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [placement, teacher, arrowDrawing, finishArrowDrawing, selectElement, updateTeacherPlacement, setPanning, canvas.x, canvas.y]);

  // Handle double-click to start arrow
  const handleDoubleClick = useCallback((e) => {
    if (!teacher) return;
    e.stopPropagation();
    startArrowDrawing({
      type: 'teacher',
      id: teacher.id,
      placementId: placement.id,
      x: placement.x,
      y: placement.y,
    });
  }, [teacher, placement, startArrowDrawing]);

  // Handle context menu
  const handleContextMenu = useCallback((e) => {
    if (!teacher) return;
    e.preventDefault();
    e.stopPropagation();
    
    showContextMenu(e.clientX, e.clientY, 'teacherPlacement', placement.id, [
      {
        label: 'Draw Arrow',
        icon: <ArrowUpRight size={14} />,
        action: () => {
          startArrowDrawing({
            type: 'teacher',
            id: teacher.id,
            placementId: placement.id,
            x: placement.x,
            y: placement.y,
          });
        },
      },
      {
        label: 'View Details',
        icon: <Info size={14} />,
        action: () => console.log('View teacher:', teacher),
      },
      {
        label: 'Style...',
        icon: <Palette size={14} />,
        action: () => showModal('stylePicker', { targetType: 'teacherPlacement', targetId: placement.id }),
      },
      {
        label: placement.locked ? 'Unlock Position' : 'Lock Position',
        action: () => updateTeacherPlacement(placement.id, { locked: !placement.locked }),
      },
      { type: 'divider' },
      {
        label: 'Remove from Canvas',
        icon: <Trash2 size={14} />,
        action: () => deleteTeacherPlacement(placement.id),
        danger: true,
      },
    ]);
  }, [placement, teacher, showContextMenu, showModal, deleteTeacherPlacement, startArrowDrawing]);

  if (!teacher) return null;

  const isHighlighted = highlightTarget?.type === 'teacherPlacement' && highlightTarget?.id === placement.id;

  return (
    <div
      ref={blockRef}
      className={`teacher-block ${selected ? 'selected' : ''} ${isDragging ? 'dragging' : ''} ${isGlobal ? 'global' : ''} ${placement.locked ? 'locked' : ''} ${isHighlighted ? 'highlighted' : ''}`}
      style={{
        left: placement.x - 60,
        top: placement.y - 25,
        borderColor: displayColor,
        opacity: placement.opacity ?? 1,
        zIndex: selected ? 200 : 50,
      }}
      onMouseDown={handleMouseDown}
      onDoubleClick={handleDoubleClick}
      onContextMenu={handleContextMenu}
    >
      <div 
        className="teacher-avatar"
        style={{ backgroundColor: displayColor }}
      >
        {teacher.name.charAt(0)}
      </div>
      <div className="teacher-info">
        <span className="teacher-name">{teacher.name}</span>
        <span className="teacher-subjects">
          {teacher.subjectDetails?.map(s => s.name).join(', ') || 'No subjects'}
        </span>
      </div>

      <button
        className="lock-toggle-btn lock-toggle-overlay"
        onClick={(e) => {
          e.stopPropagation();
          updateTeacherPlacement(placement.id, { locked: !placement.locked });
        }}
        title={placement.locked ? 'Unlock position' : 'Lock position'}
      >
        {placement.locked ? <Lock size={12} /> : <Unlock size={12} />}
      </button>
      
      {/* Connection point for arrows */}
      <div className="connection-point right" />
      <div className="connection-point left" />
      
      {/* Global indicator */}
      {isGlobal && (
        <div className="global-badge" title="Works globally across all groups">
          🌐
        </div>
      )}
    </div>
  );
};

export default TeacherBlock;

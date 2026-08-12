/**
 * SubjectBlock - Draggable subject placement on canvas
 */

import React, { useState, useCallback, useRef } from 'react';
import useStore from '../../store/useStore';
import { BookOpen, Trash2, ArrowUpRight, Info, Palette } from 'lucide-react';
import './Blocks.css';

const SubjectBlock = ({ placement, subject }) => {
  const [isDragging, setIsDragging] = useState(false);
  const blockRef = useRef(null);

  const {
    updateSubjectPlacement,
    deleteSubjectPlacement,
    selectElement,
    isSelected,
    showContextMenu,
    showModal,
    startArrowDrawing,
    finishArrowDrawing,
    arrowDrawing,
  } = useStore();

  const selected = isSelected('subjectPlacement', placement.id);
  const displayColor = placement.color || subject?.color || '#90caf9';

  // Handle dragging or arrow connection
  const handleMouseDown = useCallback((e) => {
    if (!subject) return;
    if (e.button !== 0) return;
    e.stopPropagation();

    // If we're in the middle of drawing an arrow, finish it here
    if (arrowDrawing) {
      finishArrowDrawing({
        type: 'subject',
        id: subject.id,
        placementId: placement.id,
        x: placement.x,
        y: placement.y,
      });
      return;
    }

    selectElement('subjectPlacement', placement.id, e.shiftKey);

    const startX = e.clientX;
    const startY = e.clientY;
    const startPlaceX = placement.x;
    const startPlaceY = placement.y;

    setIsDragging(true);

    const handleMouseMove = (moveEvent) => {
      const zoom = useStore.getState().canvas.zoom;
      const deltaX = (moveEvent.clientX - startX) / zoom;
      const deltaY = (moveEvent.clientY - startY) / zoom;
      
      updateSubjectPlacement(placement.id, {
        x: startPlaceX + deltaX,
        y: startPlaceY + deltaY,
      });
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      
      // Check if dropped on a group
      const state = useStore.getState();
      const sp = state.subjectPlacements.find(s => s.id === placement.id);
      if (!sp) return;
      
      const pos = { x: sp.x, y: sp.y };
      const targetGroup = state.groups.find(g => {
        const inX = pos.x >= g.x && pos.x <= g.x + g.width;
        const inY = pos.y >= g.y && pos.y <= g.y + g.height;
        return inX && inY;
      });
      
      if (targetGroup && targetGroup.id !== placement.groupId) {
        updateSubjectPlacement(placement.id, { groupId: targetGroup.id });
      } else if (!targetGroup && placement.groupId) {
        updateSubjectPlacement(placement.id, { groupId: null });
      }
      
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [placement, subject, arrowDrawing, selectElement, updateSubjectPlacement, finishArrowDrawing]);

  // Handle double-click to start arrow
  const handleDoubleClick = useCallback((e) => {
    if (!subject) return;
    e.stopPropagation();
    startArrowDrawing({
      type: 'subject',
      id: subject.id,
      placementId: placement.id,
      x: placement.x,
      y: placement.y,
    });
  }, [subject, placement, startArrowDrawing]);

  // Handle context menu
  const handleContextMenu = useCallback((e) => {
    if (!subject) return;
    e.preventDefault();
    e.stopPropagation();
    
    showContextMenu(e.clientX, e.clientY, 'subjectPlacement', placement.id, [
      {
        label: 'Connect to Teacher',
        icon: <ArrowUpRight size={14} />,
        action: () => {
          startArrowDrawing({
            type: 'subject',
            id: subject.id,
            placementId: placement.id,
            x: placement.x,
            y: placement.y,
          });
        },
      },
      {
        label: 'View Details',
        icon: <Info size={14} />,
        action: () => console.log('View subject:', subject),
      },
      {
        label: 'Style...',
        icon: <Palette size={14} />,
        action: () => showModal('stylePicker', { targetType: 'subjectPlacement', targetId: placement.id }),
      },
      { type: 'divider' },
      {
        label: 'Remove from Canvas',
        icon: <Trash2 size={14} />,
        action: () => deleteSubjectPlacement(placement.id),
        danger: true,
      },
    ]);
  }, [placement, subject, showContextMenu, showModal, deleteSubjectPlacement, startArrowDrawing]);

  if (!subject) return null;

  return (
    <div
      ref={blockRef}
      className={`subject-block ${selected ? 'selected' : ''} ${isDragging ? 'dragging' : ''} ${arrowDrawing ? 'arrow-target' : ''}`}
      style={{
        left: placement.x - 50,
        top: placement.y - 20,
        borderLeftColor: displayColor,
        opacity: placement.opacity ?? 1,
        zIndex: selected ? 200 : 50,
      }}
      onMouseDown={handleMouseDown}
      onDoubleClick={handleDoubleClick}
      onContextMenu={handleContextMenu}
    >
      <div 
        className="subject-icon"
        style={{ color: displayColor }}
      >
        <BookOpen size={16} />
      </div>
      <div className="subject-info">
        <span className="subject-name">{subject.name}</span>
        <span className="subject-code">{subject.code}</span>
      </div>
      
      {/* Connection point for arrows */}
      <div className="connection-point right" />
      <div className="connection-point left" />
    </div>
  );
};

export default SubjectBlock;

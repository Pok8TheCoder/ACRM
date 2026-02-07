/**
 * GroupBlock - Expandable, nestable group container
 */

import React, { useState, useCallback, useRef } from 'react';
import useStore from '../../store/useStore';
import { Edit2, Trash2, Copy, Palette, Lock, Unlock } from 'lucide-react';
import './Blocks.css';

const GroupBlock = ({ group }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [name, setName] = useState(group.name);
  const [isResizing, setIsResizing] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const startPosRef = useRef({ x: 0, y: 0, width: 0, height: 0 });
  const inputRef = useRef(null);

  const {
    updateGroup,
    deleteGroup,
    selectElement,
    isSelected,
    showContextMenu,
    showModal,
    canvas,
    setPanning,
    groups,
    timetables,
    updateTimetable,
    teacherPlacements,
    updateTeacherPlacement,
    subjectPlacements,
    updateSubjectPlacement,
    pushHistory,
    highlightTarget,
  } = useStore();

  const selected = isSelected('group', group.id);

  const getGroupDepth = useCallback((groupId) => {
    let depth = 0;
    let current = groups.find(g => g.id === groupId);
    while (current?.parentId) {
      depth += 1;
      current = groups.find(g => g.id === current.parentId);
      if (depth > 20) break;
    }
    return depth;
  }, [groups]);

  const getDescendantGroupIds = useCallback((groupId) => {
    const ids = [];
    const stack = [groupId];
    while (stack.length) {
      const currentId = stack.pop();
      const children = groups.filter(g => g.parentId === currentId);
      children.forEach(child => {
        ids.push(child.id);
        stack.push(child.id);
      });
    }
    return ids;
  }, [groups]);

  // Handle dragging the group
  const handleMouseDown = useCallback((e) => {
    if (e.target.closest('.resize-handle') || isEditing) return;
    if (e.button !== 0) return;

    if (group.locked) {
      setPanning(true, { x: e.clientX - canvas.x, y: e.clientY - canvas.y });
      return;
    }

    e.stopPropagation();
    selectElement('group', group.id, e.shiftKey);

    setIsDragging(true);
    document.body.classList.add('group-dragging');

    const startX = e.clientX;
    const startY = e.clientY;
    const startGroupX = group.x;
    const startGroupY = group.y;

    const descendantGroupIds = getDescendantGroupIds(group.id);
    const groupIdSet = new Set([group.id, ...descendantGroupIds]);

    // Find all items inside this group (including nested groups) at the start
    const nestedGroups = groups.filter(g => descendantGroupIds.includes(g.id)).map(g => ({
      id: g.id,
      startX: g.x,
      startY: g.y,
    }));
    const nestedTimetables = timetables.filter(t => groupIdSet.has(t.groupId)).map(t => ({
      id: t.id,
      startX: t.x,
      startY: t.y,
    }));
    const nestedTeachers = teacherPlacements.filter(t => groupIdSet.has(t.groupId)).map(t => ({
      id: t.id,
      startX: t.x,
      startY: t.y,
    }));
    const nestedSubjects = subjectPlacements.filter(s => groupIdSet.has(s.groupId)).map(s => ({
      id: s.id,
      startX: s.x,
      startY: s.y,
    }));

    const handleMouseMove = (moveEvent) => {
      const deltaX = (moveEvent.clientX - startX) / useStore.getState().canvas.zoom;
      const deltaY = (moveEvent.clientY - startY) / useStore.getState().canvas.zoom;
      
      // Move the group
      updateGroup(group.id, {
        x: startGroupX + deltaX,
        y: startGroupY + deltaY,
      }, { skipHistory: true });

      // Move all nested groups
      nestedGroups.forEach(item => {
        updateGroup(item.id, {
          x: item.startX + deltaX,
          y: item.startY + deltaY,
        }, { skipHistory: true });
      });

      // Move all nested items
      nestedTimetables.forEach(item => {
        updateTimetable(item.id, {
          x: item.startX + deltaX,
          y: item.startY + deltaY,
        }, { skipHistory: true });
      });
      nestedTeachers.forEach(item => {
        updateTeacherPlacement(item.id, {
          x: item.startX + deltaX,
          y: item.startY + deltaY,
        }, { skipHistory: true });
      });
      nestedSubjects.forEach(item => {
        updateSubjectPlacement(item.id, {
          x: item.startX + deltaX,
          y: item.startY + deltaY,
        }, { skipHistory: true });
      });
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      document.body.classList.remove('group-dragging');
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);

      // Check if this group was dropped on another group (for nesting)
      const state = useStore.getState();
      const currentGroup = state.groups.find(g => g.id === group.id);
      if (!currentGroup) return;

      const pos = { x: currentGroup.x + currentGroup.width / 2, y: currentGroup.y + currentGroup.height / 2 };
      
      // Find potential parent group (must be larger and different)
      const targetGroup = state.groups.find(g => {
        if (g.id === group.id || g.parentId === group.id) return false; // Can't nest in self or child
        
        const inX = pos.x >= g.x && pos.x <= g.x + g.width;
        const inY = pos.y >= g.y && pos.y <= g.y + g.height;
        
        // Only nest if the target is larger
        const isLarger = (g.width * g.height) > (currentGroup.width * currentGroup.height);
        
        return inX && inY && isLarger;
      });
      
      if (targetGroup && targetGroup.id !== currentGroup.parentId) {
        updateGroup(group.id, { parentId: targetGroup.id });
      } else if (!targetGroup && currentGroup.parentId) {
        updateGroup(group.id, { parentId: null });
      }

      pushHistory();
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [group.id, group.x, group.y, group.width, group.height, group.locked, isEditing, selectElement, updateGroup, groups, timetables, updateTimetable, teacherPlacements, updateTeacherPlacement, subjectPlacements, updateSubjectPlacement, getDescendantGroupIds, setPanning, canvas.x, canvas.y]);

  // Handle resizing
  const handleResizeStart = useCallback((e, handle) => {
    if (group.locked) return;
    e.stopPropagation();
    e.preventDefault();
    
    setIsResizing(true);
    startPosRef.current = {
      x: e.clientX,
      y: e.clientY,
      width: group.width,
      height: group.height,
      groupX: group.x,
      groupY: group.y,
    };

    const handleMouseMove = (moveEvent) => {
      const zoom = useStore.getState().canvas.zoom;
      const deltaX = (moveEvent.clientX - startPosRef.current.x) / zoom;
      const deltaY = (moveEvent.clientY - startPosRef.current.y) / zoom;

      let updates = {};

      if (handle.includes('e')) {
        updates.width = Math.max(100, startPosRef.current.width + deltaX);
      }
      if (handle.includes('w')) {
        const newWidth = Math.max(100, startPosRef.current.width - deltaX);
        updates.width = newWidth;
        updates.x = startPosRef.current.groupX + (startPosRef.current.width - newWidth);
      }
      if (handle.includes('s')) {
        updates.height = Math.max(80, startPosRef.current.height + deltaY);
      }
      if (handle.includes('n')) {
        const newHeight = Math.max(80, startPosRef.current.height - deltaY);
        updates.height = newHeight;
        updates.y = startPosRef.current.groupY + (startPosRef.current.height - newHeight);
      }

      updateGroup(group.id, updates, { skipHistory: true });
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      pushHistory();
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [group.id, group.width, group.height, group.x, group.y, group.locked, updateGroup]);

  // Handle context menu
  const handleContextMenu = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    
    showContextMenu(e.clientX, e.clientY, 'group', group.id, [
      {
        label: 'Rename',
        icon: <Edit2 size={14} />,
        action: () => {
          setIsEditing(true);
          setTimeout(() => inputRef.current?.focus(), 50);
        },
      },
      {
        label: 'Style...',
        icon: <Palette size={14} />,
        action: () => showModal('stylePicker', { targetType: 'group', targetId: group.id }),
      },
      {
        label: group.locked ? 'Unlock Position' : 'Lock Position',
        action: () => updateGroup(group.id, { locked: !group.locked }),
      },
      {
        label: 'Duplicate',
        icon: <Copy size={14} />,
        action: () => {
          useStore.getState().addGroup(group.x + 30, group.y + 30, group.parentId);
        },
      },
      { type: 'divider' },
      {
        label: 'Delete',
        icon: <Trash2 size={14} />,
        action: () => deleteGroup(group.id),
        danger: true,
      },
    ]);
  }, [group.id, group.x, group.y, group.parentId, group.locked, showContextMenu, showModal, updateGroup, deleteGroup]);

  // Handle name edit
  const handleNameSubmit = useCallback(() => {
    updateGroup(group.id, { name });
    setIsEditing(false);
  }, [group.id, name, updateGroup]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter') {
      handleNameSubmit();
    } else if (e.key === 'Escape') {
      setName(group.name);
      setIsEditing(false);
    }
  }, [group.name, handleNameSubmit]);

  // Handle double-click to edit name
  const handleDoubleClick = useCallback((e) => {
    if (e.target.closest('.group-header')) {
      setIsEditing(true);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, []);

  // Get parent group name if nested
  const parentGroup = groups.find(g => g.id === group.parentId);
  const depth = getGroupDepth(group.id);

  const isHighlighted = highlightTarget?.type === 'group' && highlightTarget?.id === group.id;

  return (
    <div
      className={`group-block ${selected ? 'selected' : ''} ${isResizing ? 'resizing' : ''} ${isDragging ? 'dragging' : ''} ${group.locked ? 'locked' : ''} ${isHighlighted ? 'highlighted' : ''}`}
      style={{
        left: group.x,
        top: group.y,
        width: group.width,
        height: group.height,
        backgroundColor: group.color,
        opacity: group.opacity ?? 1,
        zIndex: 1 + depth * 2 + (selected ? 1 : 0), // Groups stay behind items but preserve nesting order
      }}
      onMouseDown={handleMouseDown}
      onContextMenu={handleContextMenu}
      onDoubleClick={handleDoubleClick}
    >
      {/* Nested group indicator */}
      {parentGroup && (
        <div className="group-nested-badge" style={{ backgroundColor: parentGroup.color }}>
          📦 {parentGroup.name}
        </div>
      )}
      {/* Header */}
      <div className="group-header">
        {isEditing ? (
          <input
            ref={inputRef}
            type="text"
            className="group-name-input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={handleNameSubmit}
            onKeyDown={handleKeyDown}
            placeholder="Group name..."
          />
        ) : (
          <span className="group-name">
            {group.name || 'Unnamed Group'}
          </span>
        )}
        <button
          className="lock-toggle-btn"
          onMouseDown={(e) => e.stopPropagation()}
          onClick={(e) => {
            e.stopPropagation();
            updateGroup(group.id, { locked: !group.locked });
          }}
          title={group.locked ? 'Unlock position' : 'Lock position'}
        >
          {group.locked ? <Lock size={12} /> : <Unlock size={12} />}
        </button>
      </div>

      {/* Content area (for nested elements) */}
      <div className="group-content">
        {/* Nested groups and items will render here via z-index */}
      </div>

      {/* Resize handles */}
      {selected && (
        <>
          <div className="resize-handle n" onMouseDown={(e) => handleResizeStart(e, 'n')} />
          <div className="resize-handle s" onMouseDown={(e) => handleResizeStart(e, 's')} />
          <div className="resize-handle e" onMouseDown={(e) => handleResizeStart(e, 'e')} />
          <div className="resize-handle w" onMouseDown={(e) => handleResizeStart(e, 'w')} />
          <div className="resize-handle ne" onMouseDown={(e) => handleResizeStart(e, 'ne')} />
          <div className="resize-handle nw" onMouseDown={(e) => handleResizeStart(e, 'nw')} />
          <div className="resize-handle se" onMouseDown={(e) => handleResizeStart(e, 'se')} />
          <div className="resize-handle sw" onMouseDown={(e) => handleResizeStart(e, 'sw')} />
        </>
      )}

      {/* Visual indicator for drop zone */}
      <div className="group-drop-indicator" />
    </div>
  );
};

export default GroupBlock;

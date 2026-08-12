/**
 * TimetableBlock - Customizable timetable grid
 */

import React, { useState, useCallback } from 'react';
import useStore from '../../store/useStore';
import { 
  Settings, 
  Trash2, 
  Link, 
  Calendar,
  Clock,
  Palette,
} from 'lucide-react';
import './Blocks.css';

const TimetableBlock = ({ timetable }) => {
  const [isDragging, setIsDragging] = useState(false);

  const {
    updateTimetable,
    deleteTimetable,
    selectElement,
    isSelected,
    showContextMenu,
    showModal,
    classes,
    groups,
    updateGroup,
  } = useStore();

  const selected = isSelected('timetable', timetable.id);
  const linkedClass = classes.find(c => c.id === timetable.classId);
  const linkedGroup = groups.find(g => g.id === timetable.groupId);
  const breakSlots = Array.isArray(timetable.breakSlots) ? timetable.breakSlots : [];

  const cellWidth = 100;
  const cellHeight = 40;
  const timeColumnWidth = 60;

  const totalWidth = timeColumnWidth + (timetable.days.length * cellWidth);
  const totalRows = timetable.slotsPerDay + breakSlots.length;

  // Generate time slots
  const getTimeSlots = () => {
    const slots = [];
    const [startHour, startMin] = timetable.startTime.split(':').map(Number);
    const breakMap = new Map();
    breakSlots.forEach(b => {
      if (Number.isInteger(b.afterSlot)) {
        breakMap.set(b.afterSlot, b.duration || 30);
      }
    });
    let breakOffset = 0;

    for (let i = 0; i < timetable.slotsPerDay; i++) {
      const totalMinutes = (startHour * 60 + startMin) + (i * timetable.slotDuration) + breakOffset;
      const hour = Math.floor(totalMinutes / 60) % 24;
      const min = totalMinutes % 60;
      slots.push(`${hour.toString().padStart(2, '0')}:${min.toString().padStart(2, '0')}`);

      if (breakMap.has(i)) {
        breakOffset += breakMap.get(i);
      }
    }
    return slots;
  };

  const timeSlots = getTimeSlots();

  const getRows = () => {
    const rows = [];
    const breakMap = new Map();
    breakSlots.forEach(b => {
      if (Number.isInteger(b.afterSlot)) {
        breakMap.set(b.afterSlot, b.duration || 30);
      }
    });

    for (let i = 0; i < timetable.slotsPerDay; i++) {
      rows.push({ type: 'slot', slotIndex: i, time: timeSlots[i] });
      if (breakMap.has(i)) {
        rows.push({ type: 'break', afterSlot: i, duration: breakMap.get(i) });
      }
    }
    return rows;
  };

  const rows = getRows();

  // Handle dragging
  const handleMouseDown = useCallback((e) => {
    if (e.target.closest('.timetable-cell') || e.target.closest('button')) return;
    if (e.button !== 0) return;

    e.stopPropagation();
    selectElement('timetable', timetable.id, e.shiftKey);

    const startX = e.clientX;
    const startY = e.clientY;
    const startTableX = timetable.x;
    const startTableY = timetable.y;

    setIsDragging(true);

    const handleMouseMove = (moveEvent) => {
      const zoom = useStore.getState().canvas.zoom;
      const deltaX = (moveEvent.clientX - startX) / zoom;
      const deltaY = (moveEvent.clientY - startY) / zoom;
      updateTimetable(timetable.id, {
        x: startTableX + deltaX,
        y: startTableY + deltaY,
      });
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      
      // Check if dropped on a group - auto-link and expand group
      const state = useStore.getState();
      const tt = state.timetables.find(t => t.id === timetable.id);
      if (!tt) return;
      
      const pos = { x: tt.x, y: tt.y };
      const targetGroup = state.groups.find(g => {
        const inX = pos.x >= g.x && pos.x <= g.x + g.width;
        const inY = pos.y >= g.y && pos.y <= g.y + g.height;
        return inX && inY;
      });
      
      if (targetGroup && targetGroup.id !== timetable.groupId) {
        // Auto-link to group
        updateTimetable(timetable.id, { groupId: targetGroup.id });
        
        // Expand group to fit timetable if needed
        const ttRight = pos.x + totalWidth + 20;
        const ttBottom = pos.y + (totalRows * cellHeight) + 80;
        const groupRight = targetGroup.x + targetGroup.width;
        const groupBottom = targetGroup.y + targetGroup.height;
        
        if (ttRight > groupRight || ttBottom > groupBottom) {
          updateGroup(targetGroup.id, {
            width: Math.max(targetGroup.width, ttRight - targetGroup.x + 20),
            height: Math.max(targetGroup.height, ttBottom - targetGroup.y + 20),
          });
        }
      }
      
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [timetable.id, timetable.x, timetable.y, timetable.groupId, timetable.slotsPerDay, selectElement, updateTimetable, updateGroup, totalWidth, cellHeight, totalRows]);

  // Handle context menu
  const handleContextMenu = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    
    showContextMenu(e.clientX, e.clientY, 'timetable', timetable.id, [
      {
        label: 'Configure Days & Slots',
        icon: <Settings size={14} />,
        action: () => showModal('timetableSettings', { timetableId: timetable.id }),
      },
      {
        label: 'Link to Class',
        icon: <Link size={14} />,
        action: () => showModal('linkClass', { timetableId: timetable.id }),
      },
      {
        label: 'Link to Group',
        icon: <Link size={14} />,
        action: () => showModal('linkGroup', { timetableId: timetable.id }),
      },
      {
        label: 'Style...',
        icon: <Palette size={14} />,
        action: () => showModal('stylePicker', { targetType: 'timetable', targetId: timetable.id }),
      },
      { type: 'divider' },
      {
        label: 'Delete',
        icon: <Trash2 size={14} />,
        action: () => deleteTimetable(timetable.id),
        danger: true,
      },
    ]);
  }, [timetable.id, showContextMenu, showModal, deleteTimetable]);

  // Handle cell click
  const handleCellClick = useCallback((day, slotIndex) => {
    // Open cell assignment modal (future enhancement)
    console.log('Cell clicked:', day, slotIndex);
  }, []);

  return (
    <div
      className={`timetable-block ${selected ? 'selected' : ''} ${isDragging ? 'dragging' : ''}`}
      style={{
        left: timetable.x,
        top: timetable.y,
        width: totalWidth,
        borderColor: timetable.color || 'var(--border-color)',
        opacity: timetable.opacity ?? 1,
        zIndex: selected ? 100 : 20,
      }}
      onMouseDown={handleMouseDown}
      onContextMenu={handleContextMenu}
    >
      {/* Title Bar */}
      <div className="timetable-title">
        <div className="timetable-title-left">
          <Calendar size={14} />
          <span>{linkedClass?.name || 'Unlinked Timetable'}</span>
        </div>
        <div className="timetable-title-right">
          {linkedGroup && (
            <span className="timetable-group-badge" style={{ backgroundColor: linkedGroup.color }}>
              {linkedGroup.name || 'Group'}
            </span>
          )}
          <button 
            className="timetable-settings-btn"
            onClick={(e) => {
              e.stopPropagation();
              showModal('timetableSettings', { timetableId: timetable.id });
            }}
            title="Configure"
          >
            <Settings size={14} />
          </button>
        </div>
      </div>

      {/* Timetable Grid */}
      <div className="timetable-grid">
        {/* Header Row */}
        <div className="timetable-header-row">
          <div className="timetable-corner-cell">
            <Clock size={12} />
          </div>
          {timetable.days.map((day) => (
            <div key={day} className="timetable-header-cell">
              {day.substring(0, 3)}
            </div>
          ))}
        </div>

        {/* Time Slots */}
        {rows.map((row, rowIndex) => (
          <div key={rowIndex} className={`timetable-row ${row.type === 'break' ? 'break-row' : ''}`}>
            <div className="timetable-time-cell">
              {row.type === 'break' ? `Break ${row.duration}m` : row.time}
            </div>
            {timetable.days.map((day) => {
              if (row.type === 'break') {
                return (
                  <div
                    key={`${day}-break-${rowIndex}`}
                    className="timetable-cell break-cell"
                    style={{ width: cellWidth, height: cellHeight }}
                  />
                );
              }

              const cellKey = `${day}-${row.slotIndex}`;
              const cellData = timetable.cells?.[cellKey];

              return (
                <div
                  key={cellKey}
                  className={`timetable-cell ${cellData ? 'filled' : ''}`}
                  onClick={() => handleCellClick(day, row.slotIndex)}
                  style={{
                    width: cellWidth,
                    height: cellHeight,
                  }}
                >
                  {cellData && (
                    <div className="cell-content">
                      <span className="cell-subject">{cellData.subjectName}</span>
                      <span className="cell-teacher">{cellData.teacherName}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
};

export default TimetableBlock;

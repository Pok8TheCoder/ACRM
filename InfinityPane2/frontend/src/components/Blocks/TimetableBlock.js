/**
 * TimetableBlock - Customizable timetable grid
 */

import React, { useState, useCallback, useEffect } from 'react';
import useStore from '../../store/useStore';
import { 
  Settings, 
  Trash2, 
  Link, 
  Calendar,
  Clock,
  Palette,
  ChevronRight,
  ChevronLeft,
  Lock,
  Unlock,
  AlertTriangle,
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
    teachers,
    groups,
    updateGroup,
    classSubjects,
    classWeeks,
    initializeClassSubjects,
    assignTeacherToClassSubject,
    arrowDrawing,
    cancelArrowDrawing,
    canvas,
    setPanning,
    pushHistory,
    computeWarnings,
    regenerateDay,
    resetTimetable,
    highlightTarget,
  } = useStore();

  const selected = isSelected('timetable', timetable.id);
  const linkedClass = classes.find(c => c.id === timetable.classId);
  const linkedGroup = groups.find(g => g.id === timetable.groupId);
  const linkedClassId = linkedClass?.id;
  const breakSlots = Array.isArray(timetable.breakSlots) ? timetable.breakSlots : [];
  const drawerOpen = Boolean(timetable.showSubjects);
  const drawerWidth = 260;
  const totalWeeks = linkedClassId ? (classWeeks[linkedClassId] || 15) : 15;
  const warnings = computeWarnings();
  const timetableWarnings = warnings.filter(w => w.timetableId === timetable.id);
  const warningTooltip = timetableWarnings.map(w => w.message).join('\n');

  useEffect(() => {
    if (linkedClassId) {
      initializeClassSubjects(linkedClassId);
    }
  }, [linkedClassId, initializeClassSubjects]);

  const cellWidth = 100;
  const cellHeight = 40;
  const timeColumnWidth = 60;

  const baseWidth = timeColumnWidth + (timetable.days.length * cellWidth);
  const totalWidth = baseWidth + (drawerOpen ? drawerWidth : 0);
  const totalRows = timetable.slotsPerDay + breakSlots.length;
  const subjectsForClass = linkedClassId ? (classSubjects[linkedClassId] || []) : [];

  const handleSubjectAssign = useCallback((subjectId) => {
    if (!linkedClassId || !arrowDrawing) return;
    if (arrowDrawing.from?.type !== 'teacher') return;
    assignTeacherToClassSubject(linkedClassId, subjectId, arrowDrawing.from.id);
    cancelArrowDrawing();
  }, [linkedClassId, arrowDrawing, assignTeacherToClassSubject, cancelArrowDrawing]);

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
    if (e.target.closest('.timetable-cell') || e.target.closest('button') || e.target.closest('.timetable-subject-drawer')) return;
    if (e.button !== 0) return;

    if (timetable.locked) {
      setPanning(true, { x: e.clientX - canvas.x, y: e.clientY - canvas.y });
      return;
    }

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
      }, { skipHistory: true });
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
      
      pushHistory();
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [timetable.id, timetable.x, timetable.y, timetable.groupId, timetable.slotsPerDay, timetable.locked, selectElement, updateTimetable, updateGroup, totalWidth, cellHeight, totalRows, setPanning, canvas.x, canvas.y]);

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
        label: 'Link to Group',
        icon: <Link size={14} />,
        action: () => showModal('linkGroup', { timetableId: timetable.id }),
      },
      {
        label: 'Edit Class Subjects',
        icon: <Calendar size={14} />,
        action: () => showModal('classSubjects', { timetableId: timetable.id }),
        disabled: !linkedClassId,
      },
      {
        label: 'Reset Timetable',
        action: () => resetTimetable(timetable.id),
      },
      {
        label: timetable.locked ? 'Unlock Position' : 'Lock Position',
        action: () => updateTimetable(timetable.id, { locked: !timetable.locked }),
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
  }, [timetable.id, timetable.locked, showContextMenu, showModal, deleteTimetable]);

  // Handle cell click
  const handleCellClick = useCallback((day, slotIndex) => {
    // Open cell assignment modal (future enhancement)
    console.log('Cell clicked:', day, slotIndex);
  }, []);

  const handleCellDragStart = useCallback((e, cellKey) => {
    const cellData = timetable.cells?.[cellKey];
    if (!cellData || cellData.locked) return;
    e.dataTransfer.setData('application/json', JSON.stringify({
      type: 'timetable-cell',
      timetableId: timetable.id,
      cellKey,
    }));
    e.dataTransfer.effectAllowed = 'move';
  }, [timetable]);

  const handleCellDrop = useCallback((e, targetKey) => {
    e.preventDefault();
    const data = e.dataTransfer.getData('application/json');
    if (!data) return;
    const payload = JSON.parse(data);
    if (payload.type !== 'timetable-cell') return;

    const sourceId = payload.timetableId;
    const sourceKey = payload.cellKey;

    const state = useStore.getState();
    const sourceTimetable = state.timetables.find(t => t.id === sourceId);
    const targetTimetable = state.timetables.find(t => t.id === timetable.id);
    if (!sourceTimetable || !targetTimetable) return;

    const sourceCell = sourceTimetable.cells?.[sourceKey];
    const targetCell = targetTimetable.cells?.[targetKey];
    if (!sourceCell || sourceCell.locked) return;
    if (targetCell?.locked) return;

    const nextSourceCells = { ...(sourceTimetable.cells || {}) };
    const nextTargetCells = sourceId === timetable.id
      ? nextSourceCells
      : { ...(targetTimetable.cells || {}) };

    nextTargetCells[targetKey] = { ...sourceCell, locked: true };
    if (targetCell) {
      nextSourceCells[sourceKey] = { ...targetCell, locked: true };
    } else {
      delete nextSourceCells[sourceKey];
    }

    state.updateTimetable(sourceId, { cells: nextSourceCells });
    if (sourceId !== timetable.id) {
      state.updateTimetable(timetable.id, { cells: nextTargetCells });
    }
  }, [timetable.id]);

  const handleCellDoubleClick = useCallback((e, cellKey) => {
    e.stopPropagation();
    const cellData = timetable.cells?.[cellKey];
    if (!cellData) {
      updateTimetable(timetable.id, {
        cells: {
          ...(timetable.cells || {}),
          [cellKey]: { locked: true, empty: true, subjectName: '', teacherName: '' },
        },
      });
      return;
    }
    updateTimetable(timetable.id, {
      cells: {
        ...(timetable.cells || {}),
        [cellKey]: { ...cellData, locked: !cellData.locked },
      },
    });
  }, [timetable, updateTimetable]);

  const handleCellContextMenu = useCallback((e, cellKey) => {
    e.preventDefault();
    e.stopPropagation();
    showContextMenu(e.clientX, e.clientY, 'timetableCell', cellKey, [
      {
        label: 'Edit Slot',
        icon: <Settings size={14} />,
        action: () => showModal('editSlot', { timetableId: timetable.id, cellKey }),
      },
      {
        label: 'Clear Slot',
        action: () => {
          const nextCells = { ...(timetable.cells || {}) };
          delete nextCells[cellKey];
          updateTimetable(timetable.id, { cells: nextCells });
        },
      },
      {
        label: 'Lock Empty Slot',
        action: () => {
          if (timetable.cells?.[cellKey]) return;
          updateTimetable(timetable.id, {
            cells: {
              ...(timetable.cells || {}),
              [cellKey]: { locked: true, empty: true, subjectName: '', teacherName: '' },
            },
          });
        },
      },
      {
        label: timetable.cells?.[cellKey]?.locked ? 'Unlock Slot' : 'Lock Slot',
        action: () => {
          const cellData = timetable.cells?.[cellKey];
          if (!cellData) return;
          updateTimetable(timetable.id, {
            cells: {
              ...(timetable.cells || {}),
              [cellKey]: { ...cellData, locked: !cellData.locked },
            },
          });
        }
      }
    ]);
  }, [timetable, showContextMenu, showModal, updateTimetable]);

  const isHighlighted = highlightTarget?.type === 'timetable' && highlightTarget?.id === timetable.id;

  return (
    <div
      className={`timetable-block ${selected ? 'selected' : ''} ${isDragging ? 'dragging' : ''} ${timetable.locked ? 'locked' : ''} ${isHighlighted ? 'highlighted' : ''}`}
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
          {timetableWarnings.length > 0 && (
            <div className="timetable-warning" title={warningTooltip}>
              <AlertTriangle size={14} />
            </div>
          )}
          <button
            className="timetable-settings-btn"
            onMouseDown={(e) => e.stopPropagation()}
            onClick={(e) => {
              e.stopPropagation();
              updateTimetable(timetable.id, { locked: !timetable.locked });
            }}
            title={timetable.locked ? 'Unlock position' : 'Lock position'}
          >
            {timetable.locked ? <Lock size={14} /> : <Unlock size={14} />}
          </button>
          <button
            className="timetable-settings-btn"
            onClick={(e) => {
              e.stopPropagation();
              if (!linkedClassId) {
                showModal('linkClass', { timetableId: timetable.id });
                return;
              }
              updateTimetable(timetable.id, { showSubjects: !drawerOpen });
            }}
            title={drawerOpen ? 'Hide subjects' : 'Show subjects'}
          >
            {drawerOpen ? <ChevronLeft size={14} /> : <ChevronRight size={14} />}
          </button>
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

      <div className="timetable-body">
        {/* Timetable Grid */}
        <div className="timetable-grid">
          {/* Header Row */}
          <div className="timetable-header-row">
            <div className="timetable-corner-cell">
              <Clock size={12} />
            </div>
            {timetable.days.map((day) => (
              <div
                key={day}
                className="timetable-header-cell"
                onContextMenu={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  showContextMenu(e.clientX, e.clientY, 'timetableDay', day, [
                    {
                      label: `Regenerate ${day}`,
                      icon: <Settings size={14} />,
                      action: () => {
                        const result = regenerateDay(timetable.id, day);
                        if (!result.success && result.warnings?.length) {
                          window.alert(result.warnings.map(w => w.message).join('\n'));
                        }
                      }
                    }
                  ]);
                }}
              >
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
                    onDoubleClick={(e) => handleCellDoubleClick(e, cellKey)}
                    onContextMenu={(e) => handleCellContextMenu(e, cellKey)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => handleCellDrop(e, cellKey)}
                    style={{
                      width: cellWidth,
                      height: cellHeight,
                    }}
                    draggable={Boolean(cellData && !cellData.locked)}
                    onDragStart={(e) => handleCellDragStart(e, cellKey)}
                  >
                    {cellData && (
                      <div className={`cell-content ${cellData.locked ? 'locked' : ''}`}>
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

        {drawerOpen && (
          <div className="timetable-subject-drawer">
            <div className="timetable-subject-drawer-header">
              <span>Class Subjects ({totalWeeks} weeks)</span>
              <button
                className="timetable-drawer-edit"
                onClick={(e) => {
                  e.stopPropagation();
                  showModal('classSubjects', { timetableId: timetable.id });
                }}
              >
                Edit
              </button>
            </div>
            <div className="timetable-subject-drawer-body">
              {linkedClassId ? (
                subjectsForClass.length > 0 ? (
                  <div className="timetable-subject-list">
                    {subjectsForClass.map((subject) => (
                      <div
                        key={subject.id}
                        className={`timetable-subject-row ${arrowDrawing?.from?.type === 'teacher' ? 'assignable' : ''}`}
                        onMouseDown={(e) => {
                          e.stopPropagation();
                        }}
                        onMouseUp={(e) => {
                          e.stopPropagation();
                          handleSubjectAssign(subject.id);
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSubjectAssign(subject.id);
                        }}
                        data-class-id={linkedClassId}
                        data-subject-id={subject.id}
                        data-timetable-id={timetable.id}
                      >
                        <div className="timetable-subject-meta">
                          <span className="timetable-subject-name">{subject.name}</span>
                          <span className="timetable-subject-teacher">
                            {subject.teacherId
                              ? (teachers.find(t => t.id === subject.teacherId)?.name || 'Assigned')
                              : 'Unassigned'}
                          </span>
                        </div>
                        <span className="timetable-subject-hours">{subject.hours}h</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="timetable-subject-empty">No subjects yet.</div>
                )
              ) : (
                <div className="timetable-subject-empty">Link a class to manage subjects.</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TimetableBlock;

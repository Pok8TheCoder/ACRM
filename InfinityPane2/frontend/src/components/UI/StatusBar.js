/**
 * StatusBar - Bottom status bar with helpful information
 */

import React from 'react';
import useStore from '../../store/useStore';
import { CheckCircle2 } from 'lucide-react';
import './UI.css';

const StatusBar = () => {
  const {
    activeTool,
    groups,
    timetables,
    arrows,
    teacherPlacements,
    subjectPlacements,
    selectedElements,
  } = useStore();

  const toolNames = {
    select: 'Select',
    pan: 'Pan',
    arrow: 'Arrow',
    timetable: 'Timetable',
    group: 'Group',
  };

  const toolHints = {
    select: 'Click to select, drag to move. Shift+click for multi-select.',
    pan: 'Drag to pan the canvas. Use scroll wheel to pan.',
    arrow: 'Click a teacher or subject, then click another to connect.',
    timetable: 'Click to place a timetable. Right-click to configure.',
    group: 'Click to place a group. Drag corners to resize.',
  };

  const stats = [
    { label: 'Groups', value: groups.length },
    { label: 'Timetables', value: timetables.length },
    { label: 'Teachers', value: teacherPlacements.length },
    { label: 'Subjects', value: subjectPlacements.length },
    { label: 'Connections', value: arrows.length },
  ];

  return (
    <div className="status-bar">
      {/* Current Tool */}
      <div className="status-section">
        <span className="status-label">Tool:</span>
        <span className="status-value">{toolNames[activeTool]}</span>
      </div>

      {/* Tool Hint */}
      <div className="status-section hint">
        <span className="status-hint">{toolHints[activeTool]}</span>
      </div>

      {/* Spacer */}
      <div className="status-spacer" />

      {/* Selection Info */}
      {selectedElements.length > 0 && (
        <div className="status-section">
          <span className="status-label">Selected:</span>
          <span className="status-value">{selectedElements.length} item(s)</span>
        </div>
      )}

      {/* Stats */}
      <div className="status-section stats">
        {stats.map(stat => (
          <span key={stat.label} className="status-stat">
            <span className="stat-value">{stat.value}</span>
            <span className="stat-label">{stat.label}</span>
          </span>
        ))}
      </div>

      {/* Connection Status */}
      <div className="status-section connection">
        <CheckCircle2 size={12} className="status-icon success" />
        <span>Ready</span>
      </div>
    </div>
  );
};

export default StatusBar;

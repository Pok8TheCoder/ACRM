/**
 * Modal - Modal dialogs for settings and configurations
 */

import React, { useState } from 'react';
import useStore from '../../store/useStore';
import { X, Check, Plus, Minus } from 'lucide-react';
import './UI.css';

const Modal = () => {
  const { activeModal, hideModal } = useStore();
  
  if (!activeModal) return null;

  return (
    <div className="modal-overlay" onClick={hideModal}>
      <div className="modal-container" onClick={(e) => e.stopPropagation()}>
        {activeModal.type === 'timetableSettings' && (
          <TimetableSettingsModal 
            timetableId={activeModal.data.timetableId}
            onClose={hideModal}
          />
        )}
        {activeModal.type === 'linkClass' && (
          <LinkClassModal 
            timetableId={activeModal.data.timetableId}
            onClose={hideModal}
          />
        )}
        {activeModal.type === 'linkGroup' && (
          <LinkGroupModal 
            timetableId={activeModal.data.timetableId}
            onClose={hideModal}
          />
        )}
        {activeModal.type === 'stylePicker' && (
          <StylePickerModal
            targetType={activeModal.data.targetType}
            targetId={activeModal.data.targetId}
            onClose={hideModal}
          />
        )}
      </div>
    </div>
  );
};

// Timetable Settings Modal
const TimetableSettingsModal = ({ timetableId, onClose }) => {
  const { timetables, updateTimetable } = useStore();
  const timetable = timetables.find(t => t.id === timetableId);
  
  const [days, setDays] = useState(timetable?.days || []);
  const [slotsPerDay, setSlotsPerDay] = useState(timetable?.slotsPerDay || 8);
  const [slotDuration, setSlotDuration] = useState(timetable?.slotDuration || 60);
  const [breakSlots, setBreakSlots] = useState(timetable?.breakSlots || []);
  const [startTime, setStartTime] = useState(timetable?.startTime || '09:00');

  const allDays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

  const toggleDay = (day) => {
    if (days.includes(day)) {
      setDays(days.filter(d => d !== day));
    } else {
      setDays([...days, day].sort((a, b) => allDays.indexOf(a) - allDays.indexOf(b)));
    }
  };

  const handleSave = () => {
    updateTimetable(timetableId, {
      days,
      slotsPerDay,
      slotDuration,
      breakSlots: breakSlots.filter(b => Number.isInteger(b.afterSlot) && b.afterSlot >= 0 && b.afterSlot < slotsPerDay),
      startTime,
    });
    onClose();
  };

  const addBreakSlot = () => {
    setBreakSlots([...breakSlots, { afterSlot: 0, duration: 30 }]);
  };

  const updateBreakSlot = (index, updates) => {
    setBreakSlots(breakSlots.map((b, i) => i === index ? { ...b, ...updates } : b));
  };

  const removeBreakSlot = (index) => {
    setBreakSlots(breakSlots.filter((_, i) => i !== index));
  };

  const presets = [
    { label: 'Mon-Fri', days: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'] },
    { label: 'Mon-Sat', days: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'] },
    { label: 'Weekdays', days: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'] },
    { label: 'All Week', days: allDays },
  ];

  if (!timetable) return null;

  return (
    <div className="modal">
      <div className="modal-header">
        <h2>Timetable Settings</h2>
        <button className="modal-close" onClick={onClose}>
          <X size={18} />
        </button>
      </div>
      
      <div className="modal-body">
        {/* Days Selection */}
        <div className="form-group">
          <label>Days</label>
          <div className="days-presets">
            {presets.map(preset => (
              <button
                key={preset.label}
                className={`preset-btn ${JSON.stringify(days) === JSON.stringify(preset.days) ? 'active' : ''}`}
                onClick={() => setDays(preset.days)}
              >
                {preset.label}
              </button>
            ))}
          </div>
          <div className="days-grid">
            {allDays.map(day => (
              <button
                key={day}
                className={`day-btn ${days.includes(day) ? 'active' : ''}`}
                onClick={() => toggleDay(day)}
              >
                {day.substring(0, 3)}
              </button>
            ))}
          </div>
        </div>

        {/* Slots Per Day */}
        <div className="form-group">
          <label>Slots Per Day</label>
          <div className="number-input">
            <button onClick={() => setSlotsPerDay(Math.max(1, slotsPerDay - 1))}>
              <Minus size={14} />
            </button>
            <input
              type="number"
              value={slotsPerDay}
              onChange={(e) => setSlotsPerDay(Math.max(1, parseInt(e.target.value) || 1))}
              min={1}
              max={24}
            />
            <button onClick={() => setSlotsPerDay(Math.min(24, slotsPerDay + 1))}>
              <Plus size={14} />
            </button>
          </div>
        </div>

        {/* Slot Duration */}
        <div className="form-group">
          <label>Slot Duration (minutes)</label>
          <div className="duration-presets">
            {[30, 45, 60, 90, 120].map(duration => (
              <button
                key={duration}
                className={`preset-btn ${slotDuration === duration ? 'active' : ''}`}
                onClick={() => setSlotDuration(duration)}
              >
                {duration}m
              </button>
            ))}
          </div>
        </div>

        {/* Break Slots */}
        <div className="form-group">
          <label>Break Slots</label>
          <div className="break-slots">
            {breakSlots.map((b, index) => (
              <div key={index} className="break-slot-row">
                <select
                  value={b.afterSlot}
                  onChange={(e) => updateBreakSlot(index, { afterSlot: parseInt(e.target.value, 10) })}
                >
                  {Array.from({ length: slotsPerDay }).map((_, i) => (
                    <option key={i} value={i}>
                      After Slot {i + 1}
                    </option>
                  ))}
                </select>
                <input
                  type="number"
                  min={5}
                  max={180}
                  value={b.duration || 30}
                  onChange={(e) => updateBreakSlot(index, { duration: parseInt(e.target.value, 10) || 30 })}
                />
                <span className="break-slot-unit">min</span>
                <button className="break-remove-btn" onClick={() => removeBreakSlot(index)}>Remove</button>
              </div>
            ))}
            <button className="add-break-btn" onClick={addBreakSlot}>+ Add Break</button>
          </div>
        </div>

        {/* Start Time */}
        <div className="form-group">
          <label>Start Time</label>
          <input
            type="time"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
            className="time-input"
          />
        </div>
      </div>

      <div className="modal-footer">
        <button className="btn btn-secondary" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary" onClick={handleSave}>
          <Check size={16} />
          Save Changes
        </button>
      </div>
    </div>
  );
};

// Style Picker Modal
const StylePickerModal = ({ targetType, targetId, onClose }) => {
  const {
    groups,
    timetables,
    teacherPlacements,
    subjectPlacements,
    textBlocks,
    structureBlocks,
    freeArrows,
    updateGroup,
    updateTimetable,
    updateTeacherPlacement,
    updateSubjectPlacement,
    updateTextBlock,
    updateStructureBlock,
    updateFreeArrow,
  } = useStore();

  const getTarget = () => {
    switch (targetType) {
      case 'group':
        return groups.find(g => g.id === targetId);
      case 'timetable':
        return timetables.find(t => t.id === targetId);
      case 'teacherPlacement':
        return teacherPlacements.find(t => t.id === targetId);
      case 'subjectPlacement':
        return subjectPlacements.find(s => s.id === targetId);
      case 'textBlock':
        return textBlocks.find(t => t.id === targetId);
      case 'structureBlock':
        return structureBlocks.find(s => s.id === targetId);
      case 'freeArrow':
        return freeArrows.find(a => a.id === targetId);
      default:
        return null;
    }
  };

  const target = getTarget();
  const [color, setColor] = useState(target?.color || '#4361ee');
  const [opacity, setOpacity] = useState(target?.opacity ?? 1);
  const [applyAll, setApplyAll] = useState(false);

  const applyStyle = (updates) => {
    if (applyAll) {
      groups.forEach(g => updateGroup(g.id, updates));
      timetables.forEach(t => updateTimetable(t.id, updates));
      teacherPlacements.forEach(t => updateTeacherPlacement(t.id, updates));
      subjectPlacements.forEach(s => updateSubjectPlacement(s.id, updates));
      textBlocks.forEach(t => updateTextBlock(t.id, updates));
      structureBlocks.forEach(s => updateStructureBlock(s.id, updates));
      freeArrows.forEach(a => updateFreeArrow(a.id, updates));
      return;
    }

    switch (targetType) {
      case 'group':
        updateGroup(targetId, updates);
        break;
      case 'timetable':
        updateTimetable(targetId, updates);
        break;
      case 'teacherPlacement':
        updateTeacherPlacement(targetId, updates);
        break;
      case 'subjectPlacement':
        updateSubjectPlacement(targetId, updates);
        break;
      case 'textBlock':
        updateTextBlock(targetId, updates);
        break;
      case 'structureBlock':
        updateStructureBlock(targetId, updates);
        break;
      case 'freeArrow':
        updateFreeArrow(targetId, updates);
        break;
      default:
        break;
    }
  };

  if (!target) return null;

  return (
    <div className="modal">
      <div className="modal-header">
        <h2>Style</h2>
        <button className="modal-close" onClick={onClose}>
          <X size={18} />
        </button>
      </div>

      <div className="modal-body">
        <div className="form-group">
          <label>Color</label>
          <input
            type="color"
            value={color}
            onChange={(e) => setColor(e.target.value)}
            className="color-input"
          />
        </div>

        <div className="form-group">
          <label>Opacity</label>
          <div className="opacity-row">
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={opacity}
              onChange={(e) => setOpacity(parseFloat(e.target.value))}
            />
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={opacity}
              onChange={(e) => setOpacity(parseFloat(e.target.value) || 0)}
            />
          </div>
        </div>

        <label className="apply-all">
          <input
            type="checkbox"
            checked={applyAll}
            onChange={(e) => setApplyAll(e.target.checked)}
          />
          Apply to all elements
        </label>
      </div>

      <div className="modal-footer">
        <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button
          className="btn btn-primary"
          onClick={() => {
            applyStyle({ color, opacity });
            onClose();
          }}
        >
          Apply
        </button>
      </div>
    </div>
  );
};

// Link Class Modal
const LinkClassModal = ({ timetableId, onClose }) => {
  const { timetables, updateTimetable, classes } = useStore();
  const timetable = timetables.find(t => t.id === timetableId);
  const [selectedClass, setSelectedClass] = useState(timetable?.classId || '');

  const handleSave = () => {
    updateTimetable(timetableId, { classId: selectedClass });
    onClose();
  };

  return (
    <div className="modal modal-small">
      <div className="modal-header">
        <h2>Link to Class</h2>
        <button className="modal-close" onClick={onClose}>
          <X size={18} />
        </button>
      </div>
      
      <div className="modal-body">
        <div className="form-group">
          <label>Select Class</label>
          <select
            value={selectedClass}
            onChange={(e) => setSelectedClass(e.target.value)}
            className="select-input"
          >
            <option value="">-- Select a class --</option>
            {classes.map(cls => (
              <option key={cls.id} value={cls.id}>
                {cls.name} - Section {cls.section}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="modal-footer">
        <button className="btn btn-secondary" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary" onClick={handleSave} disabled={!selectedClass}>
          <Check size={16} />
          Link Class
        </button>
      </div>
    </div>
  );
};

// Link Group Modal
const LinkGroupModal = ({ timetableId, onClose }) => {
  const { timetables, updateTimetable, groups } = useStore();
  const timetable = timetables.find(t => t.id === timetableId);
  const [selectedGroup, setSelectedGroup] = useState(timetable?.groupId || '');

  const handleSave = () => {
    updateTimetable(timetableId, { groupId: selectedGroup || null });
    onClose();
  };

  return (
    <div className="modal modal-small">
      <div className="modal-header">
        <h2>Link to Group</h2>
        <button className="modal-close" onClick={onClose}>
          <X size={18} />
        </button>
      </div>
      
      <div className="modal-body">
        <div className="form-group">
          <label>Select Group</label>
          <select
            value={selectedGroup}
            onChange={(e) => setSelectedGroup(e.target.value)}
            className="select-input"
          >
            <option value="">-- No group (standalone) --</option>
            {groups.map(group => (
              <option key={group.id} value={group.id}>
                {group.name || 'Unnamed Group'}
              </option>
            ))}
          </select>
          <p className="form-hint">
            Timetables should be linked to groups to organize faculty assignments.
          </p>
        </div>
      </div>

      <div className="modal-footer">
        <button className="btn btn-secondary" onClick={onClose}>
          Cancel
        </button>
        <button className="btn btn-primary" onClick={handleSave}>
          <Check size={16} />
          Link Group
        </button>
      </div>
    </div>
  );
};

export default Modal;

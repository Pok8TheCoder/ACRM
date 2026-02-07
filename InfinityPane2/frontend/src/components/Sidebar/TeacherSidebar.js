/**
 * TeacherSidebar - Left sidebar with teacher list
 */

import React, { useEffect, useCallback, useMemo } from 'react';
import useStore from '../../store/useStore';
import { Search, User, GripVertical, AlertTriangle, MapPin } from 'lucide-react';
import './Sidebar.css';

const TeacherSidebar = () => {
  const {
    teachers,
    teachersLoading,
    teacherSearch,
    setTeacherSearch,
    fetchTeachers,
    subjects,
    groups,
    timetables,
    teacherPlacements,
    subjectPlacements,
    classSubjects,
    centerCanvasOn,
    computeWarnings,
    setHighlightTarget,
  } = useStore();

  // Debounced search
  useEffect(() => {
    const timeout = setTimeout(() => {
      fetchTeachers();
    }, 300);
    return () => clearTimeout(timeout);
  }, [teacherSearch, fetchTeachers]);

  const handleDragStart = useCallback((e, teacher) => {
    e.dataTransfer.setData('application/json', JSON.stringify({
      type: 'teacher',
      id: teacher.id,
      name: teacher.name,
    }));
    e.dataTransfer.effectAllowed = 'copy';
    
    // Create custom drag image
    const dragImage = document.createElement('div');
    dragImage.className = 'drag-preview teacher-drag-preview';
    dragImage.innerHTML = `
      <div class="drag-preview-content">
        <span class="drag-preview-icon">👨‍🏫</span>
        <span>${teacher.name}</span>
      </div>
    `;
    dragImage.style.position = 'absolute';
    dragImage.style.top = '-1000px';
    document.body.appendChild(dragImage);
    e.dataTransfer.setDragImage(dragImage, 60, 20);
    
    setTimeout(() => document.body.removeChild(dragImage), 0);
  }, []);

  const getSubjectName = (subjectId) => {
    const subject = subjects.find(s => s.id === subjectId);
    return subject?.name || subjectId;
  };

  const { availableTeachers, assignedTeachers } = useMemo(() => {
    const assignedIds = new Set(teacherPlacements.map(t => t.teacherId));
    return {
      availableTeachers: teachers.filter(t => !assignedIds.has(t.id)),
      assignedTeachers: teacherPlacements
        .map(tp => ({ placement: tp, teacher: teachers.find(t => t.id === tp.teacherId) }))
        .filter(item => item.teacher),
    };
  }, [teachers, teacherPlacements]);

  const warnings = useMemo(() => computeWarnings(), [computeWarnings, groups, timetables, teacherPlacements, subjectPlacements, classSubjects]);

  return (
    <div className="sidebar sidebar-left">
      <div className="sidebar-header">
        <h3 className="sidebar-title">
          <User size={16} />
          Teachers
        </h3>
        <span className="sidebar-count">{availableTeachers.length}</span>
      </div>

      {/* Search */}
      <div className="sidebar-search">
        <Search size={14} className="search-icon" />
        <input
          type="text"
          placeholder="Search by name, subject, or ID..."
          value={teacherSearch}
          onChange={(e) => setTeacherSearch(e.target.value)}
        />
      </div>

      {/* Teacher List */}
      <div className="sidebar-list">
        {teachersLoading ? (
          <div className="loading-spinner" />
        ) : availableTeachers.length === 0 ? (
          <div className="empty-state">
            <User size={32} />
            <p>No teachers found</p>
          </div>
        ) : (
          availableTeachers.map((teacher) => (
            <div
              key={teacher.id}
              className="sidebar-item teacher-item"
              draggable
              onDragStart={(e) => handleDragStart(e, teacher)}
            >
              <div className="item-drag-handle">
                <GripVertical size={14} />
              </div>
              <div 
                className="item-avatar"
                style={{ backgroundColor: teacher.color }}
              >
                {teacher.name.charAt(0)}
              </div>
              <div className="item-content">
                <div className="item-name">{teacher.name}</div>
                <div className="item-meta">
                  {teacher.subjects?.slice(0, 2).map(sid => getSubjectName(sid)).join(', ')}
                  {teacher.subjects?.length > 2 && ` +${teacher.subjects.length - 2}`}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Assigned Teachers */}
      <div className="sidebar-section">
        <div className="sidebar-header small">
          <h4 className="sidebar-title">
            <MapPin size={14} />
            Assigned Teachers
          </h4>
          <span className="sidebar-count">{assignedTeachers.length}</span>
        </div>
        <div className="sidebar-list compact">
          {assignedTeachers.length === 0 ? (
            <div className="empty-state compact">No assigned teachers</div>
          ) : (
            assignedTeachers.map(({ placement, teacher }) => {
              const group = placement.groupId ? groups.find(g => g.id === placement.groupId) : null;
              return (
                <div
                  key={placement.id}
                  className="sidebar-item assigned-item compact"
                  onClick={() => {
                    centerCanvasOn(placement.x, placement.y);
                    setHighlightTarget('teacherPlacement', placement.id);
                  }}
                >
                  <div 
                    className="item-avatar"
                    style={{ backgroundColor: teacher.color }}
                  >
                    {teacher.name.charAt(0)}
                  </div>
                  <div className="item-content">
                    <div className="item-name">{teacher.name}</div>
                    <div className="item-meta">
                      {group ? `Group ${group.name || group.id}` : 'No group'}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Warnings */}
      <div className="sidebar-section">
        <div className="sidebar-header small">
          <h4 className="sidebar-title warning-title">
            <AlertTriangle size={14} />
            Warnings
          </h4>
          <span className="sidebar-count">{warnings.length}</span>
        </div>
        <div className="sidebar-list compact warnings-list">
          {warnings.length === 0 ? (
            <div className="empty-state compact">No warnings</div>
          ) : (
            warnings.map((warning, index) => (
              <div
                key={index}
                className="warning-item"
                onClick={() => {
                  if (warning.targetType && warning.targetId) {
                    const type = warning.targetType;
                    if (type === 'teacherPlacement') {
                      const placement = teacherPlacements.find(t => t.id === warning.targetId);
                      if (placement) {
                        centerCanvasOn(placement.x, placement.y);
                        setHighlightTarget(type, placement.id);
                      }
                      return;
                    }
                    if (type === 'subjectPlacement') {
                      const placement = subjectPlacements.find(s => s.id === warning.targetId);
                      if (placement) {
                        centerCanvasOn(placement.x, placement.y);
                        setHighlightTarget(type, placement.id);
                      }
                      return;
                    }
                    if (type === 'timetable') {
                      const timetable = timetables.find(t => t.id === warning.targetId);
                      if (timetable) {
                        centerCanvasOn(timetable.x, timetable.y);
                        setHighlightTarget(type, timetable.id);
                      }
                      return;
                    }
                  }
                  if (!warning.timetableId) return;
                  const timetable = timetables.find(t => t.id === warning.timetableId);
                  if (timetable) {
                    centerCanvasOn(timetable.x, timetable.y);
                    setHighlightTarget('timetable', timetable.id);
                  }
                }}
              >
                {warning.message}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Footer hint */}
      <div className="sidebar-footer">
        <span>Drag teachers into groups (no duplicates)</span>
      </div>
    </div>
  );
};

export default TeacherSidebar;

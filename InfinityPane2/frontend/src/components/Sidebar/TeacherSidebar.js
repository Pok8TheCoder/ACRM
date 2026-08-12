/**
 * TeacherSidebar - Left sidebar with teacher list
 */

import React, { useEffect, useCallback } from 'react';
import useStore from '../../store/useStore';
import { Search, User, GripVertical } from 'lucide-react';
import './Sidebar.css';

const TeacherSidebar = () => {
  const {
    teachers,
    teachersLoading,
    teacherSearch,
    setTeacherSearch,
    fetchTeachers,
    subjects,
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

  return (
    <div className="sidebar sidebar-left">
      <div className="sidebar-header">
        <h3 className="sidebar-title">
          <User size={16} />
          Teachers
        </h3>
        <span className="sidebar-count">{teachers.length}</span>
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
        ) : teachers.length === 0 ? (
          <div className="empty-state">
            <User size={32} />
            <p>No teachers found</p>
          </div>
        ) : (
          teachers.map((teacher) => (
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

      {/* Footer hint */}
      <div className="sidebar-footer">
        <span>Drag teachers to canvas or groups</span>
      </div>
    </div>
  );
};

export default TeacherSidebar;

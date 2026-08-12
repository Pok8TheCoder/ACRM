/**
 * SubjectSidebar - Right sidebar with subject list
 */

import React, { useEffect, useCallback } from 'react';
import useStore from '../../store/useStore';
import { Search, BookOpen, GripVertical, Layers } from 'lucide-react';
import './Sidebar.css';

const SubjectSidebar = () => {
  const {
    subjects,
    subjectsLoading,
    subjectSearch,
    setSubjectSearch,
    fetchSubjects,
    classes,
  } = useStore();

  // Debounced search
  useEffect(() => {
    const timeout = setTimeout(() => {
      fetchSubjects();
    }, 300);
    return () => clearTimeout(timeout);
  }, [subjectSearch, fetchSubjects]);

  const handleDragStart = useCallback((e, subject) => {
    e.dataTransfer.setData('application/json', JSON.stringify({
      type: 'subject',
      id: subject.id,
      name: subject.name,
    }));
    e.dataTransfer.effectAllowed = 'copy';
    
    // Create custom drag image
    const dragImage = document.createElement('div');
    dragImage.className = 'drag-preview subject-drag-preview';
    dragImage.innerHTML = `
      <div class="drag-preview-content">
        <span class="drag-preview-icon">📚</span>
        <span>${subject.name}</span>
      </div>
    `;
    dragImage.style.position = 'absolute';
    dragImage.style.top = '-1000px';
    document.body.appendChild(dragImage);
    e.dataTransfer.setDragImage(dragImage, 60, 20);
    
    setTimeout(() => document.body.removeChild(dragImage), 0);
  }, []);

  return (
    <div className="sidebar sidebar-right">
      <div className="sidebar-header">
        <h3 className="sidebar-title">
          <BookOpen size={16} />
          Subjects
        </h3>
        <span className="sidebar-count">{subjects.length}</span>
      </div>

      {/* Search */}
      <div className="sidebar-search">
        <Search size={14} className="search-icon" />
        <input
          type="text"
          placeholder="Search subjects..."
          value={subjectSearch}
          onChange={(e) => setSubjectSearch(e.target.value)}
        />
      </div>

      {/* Subject List */}
      <div className="sidebar-list">
        {subjectsLoading ? (
          <div className="loading-spinner" />
        ) : subjects.length === 0 ? (
          <div className="empty-state">
            <BookOpen size={32} />
            <p>No subjects found</p>
          </div>
        ) : (
          subjects.map((subject) => (
            <div
              key={subject.id}
              className="sidebar-item subject-item"
              draggable
              onDragStart={(e) => handleDragStart(e, subject)}
            >
              <div className="item-drag-handle">
                <GripVertical size={14} />
              </div>
              <div 
                className="item-color-bar"
                style={{ backgroundColor: subject.color }}
              />
              <div className="item-content">
                <div className="item-name">{subject.name}</div>
                <div className="item-meta">{subject.code}</div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Classes Section */}
      <div className="sidebar-section">
        <div className="sidebar-header small">
          <h4 className="sidebar-title">
            <Layers size={14} />
            Classes
          </h4>
          <span className="sidebar-count">{classes.length}</span>
        </div>
        <div className="sidebar-list compact">
          {classes.map((cls) => (
            <div key={cls.id} className="sidebar-item class-item compact">
              <div className="item-content">
                <div className="item-name">{cls.name}</div>
                <div className="item-meta">Section {cls.section} • {cls.strength} students</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Footer hint */}
      <div className="sidebar-footer">
        <span>Drag subjects into groups, then link with arrows</span>
      </div>
    </div>
  );
};

export default SubjectSidebar;

/**
 * InfinityPane - Main Application Component
 * An infinite canvas scheduling application
 */

import React, { useEffect } from 'react';
import useStore from './store/useStore';
import InfiniteCanvas from './components/Canvas/InfiniteCanvas';
import Toolbar from './components/Toolbar/Toolbar';
import TeacherSidebar from './components/Sidebar/TeacherSidebar';
import SubjectSidebar from './components/Sidebar/SubjectSidebar';
import ContextMenu from './components/UI/ContextMenu';
import Modal from './components/UI/Modal';
import StatusBar from './components/UI/StatusBar';
import './App.css';

function App() {
  const { 
    fetchTeachers, 
    fetchSubjects, 
    fetchClasses, 
    loadFromBackend,
    contextMenu,
    activeModal,
  } = useStore();

  // Initial data fetch
  useEffect(() => {
    fetchTeachers();
    fetchSubjects();
    fetchClasses();
    loadFromBackend();
  }, [fetchTeachers, fetchSubjects, fetchClasses, loadFromBackend]);

  return (
    <div className="app">
      {/* Top Toolbar */}
      <Toolbar />
      
      {/* Main Content Area */}
      <div className="main-content">
        {/* Left Sidebar - Teachers */}
        <TeacherSidebar />
        
        {/* Infinite Canvas */}
        <InfiniteCanvas />
        
        {/* Right Sidebar - Subjects */}
        <SubjectSidebar />
      </div>
      
      {/* Status Bar */}
      <StatusBar />
      
      {/* Context Menu (rendered at root for proper positioning) */}
      {contextMenu && <ContextMenu />}
      
      {/* Modal */}
      {activeModal && <Modal />}
    </div>
  );
}

export default App;

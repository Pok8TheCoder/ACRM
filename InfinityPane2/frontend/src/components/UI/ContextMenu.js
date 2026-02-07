/**
 * ContextMenu - Right-click context menu
 */

import React, { useEffect, useRef } from 'react';
import useStore from '../../store/useStore';
import './UI.css';

const ContextMenu = () => {
  const { contextMenu, hideContextMenu } = useStore();
  const menuRef = useRef(null);

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        hideContextMenu();
      }
    };

    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        hideContextMenu();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [hideContextMenu]);

  // Adjust position if menu goes off screen
  useEffect(() => {
    if (menuRef.current && contextMenu) {
      const rect = menuRef.current.getBoundingClientRect();
      const { innerWidth, innerHeight } = window;
      
      let adjustedX = contextMenu.x;
      let adjustedY = contextMenu.y;
      
      if (rect.right > innerWidth) {
        adjustedX = innerWidth - rect.width - 10;
      }
      if (rect.bottom > innerHeight) {
        adjustedY = innerHeight - rect.height - 10;
      }
      
      menuRef.current.style.left = `${adjustedX}px`;
      menuRef.current.style.top = `${adjustedY}px`;
    }
  }, [contextMenu]);

  if (!contextMenu) return null;

  const handleItemClick = (item) => {
    if (item.disabled) return;
    if (item.action) {
      item.action();
    }
    hideContextMenu();
  };

  return (
    <div
      ref={menuRef}
      className="context-menu"
      style={{ left: contextMenu.x, top: contextMenu.y }}
    >
      {contextMenu.items.map((item, index) => {
        if (item.type === 'divider') {
          return <div key={index} className="context-menu-divider" />;
        }

        return (
          <div
            key={index}
            className={`context-menu-item ${item.danger ? 'danger' : ''} ${item.disabled ? 'disabled' : ''}`}
            onClick={() => handleItemClick(item)}
          >
            {item.icon && <span className="context-menu-icon">{item.icon}</span>}
            <span className="context-menu-label">{item.label}</span>
            {item.shortcut && <span className="context-menu-shortcut">{item.shortcut}</span>}
          </div>
        );
      })}
    </div>
  );
};

export default ContextMenu;

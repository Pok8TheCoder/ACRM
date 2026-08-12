/**
 * Toolbar - Top toolbar with tools and actions
 */

import React, { useState } from 'react';
import useStore from '../../store/useStore';
import { 
  MousePointer2,
  ArrowUpRight, 
  Table2, 
  Square, 
  Type,
  LayoutGrid,
  Save, 
  Download,
  Undo,
  Redo,
  HelpCircle,
} from 'lucide-react';
import './Toolbar.css';

const Toolbar = () => {
  const [showShapes, setShowShapes] = useState(false);
  const {
    activeTool,
    setActiveTool,
    saveToBackend,
    addGroup,
    addTimetable,
    addTextBlock,
    addStructureBlock,
    classes,
    undo,
    redo,
    history,
    historyIndex,
  } = useStore();

  const tools = [
    { id: 'select', icon: MousePointer2, label: 'Select (V)', shortcut: 'V', draggable: false },
    { id: 'arrow', icon: ArrowUpRight, label: 'Arrow (A)', shortcut: 'A', draggable: true },
    { id: 'timetable', icon: Table2, label: 'Timetable (T)', shortcut: 'T', draggable: true },
    { id: 'group', icon: Square, label: 'Group (G)', shortcut: 'G', draggable: true },
    { id: 'text', icon: Type, label: 'Text (X)', shortcut: 'X', draggable: true },
    { id: 'structure', icon: LayoutGrid, label: 'Shapes (B)', shortcut: 'B', draggable: false },
  ];

  const shapes = [
    { id: 'rectangle', label: 'Rectangle' },
    { id: 'square', label: 'Square' },
    { id: 'circle', label: 'Circle' },
    { id: 'diamond', label: 'Diamond' },
  ];

  const handleToolDragStart = (e, toolId) => {
    e.dataTransfer.setData('application/json', JSON.stringify({
      type: 'tool',
      tool: toolId,
    }));
    e.dataTransfer.effectAllowed = 'copy';
  };

  const handleToolClick = (toolId) => {
    if (toolId === 'select') {
      setActiveTool('select');
    } else if (toolId === 'group') {
      // Clicking group tool adds a group at center
      addGroup(0, 0);
      setActiveTool('select');
    } else if (toolId === 'timetable') {
      // Clicking timetable tool adds a timetable at center
      if (classes.length > 0) {
        addTimetable(100, 0, classes[0].id, null);
      }
      setActiveTool('select');
    } else if (toolId === 'text') {
      addTextBlock(0, 0);
      setActiveTool('select');
    } else if (toolId === 'structure') {
      setShowShapes((prev) => !prev);
    } else {
      setActiveTool(toolId);
    }
  };

  const handleSave = () => {
    saveToBackend();
  };

  return (
    <div className="toolbar">
      {/* Left */}
      <div className="toolbar-left">
        <div className="toolbar-brand">
        <span className="brand-icon">∞</span>
        <span className="brand-name">InfinityPane</span>
        </div>
      </div>

      {/* Center */}
      <div className="toolbar-center">
        <div className="toolbar-group tools-group">
          {tools.map((tool) => (
            <button
              key={tool.id}
              className={`toolbar-button ${activeTool === tool.id ? 'active' : ''}`}
              onClick={() => handleToolClick(tool.id)}
              title={tool.label}
              draggable={tool.draggable}
              onDragStart={(e) => handleToolDragStart(e, tool.id)}
            >
              <tool.icon size={18} />
            </button>
          ))}
          {showShapes && (
            <div className="toolbar-submenu">
              {shapes.map((shape) => (
                <button
                  key={shape.id}
                  className="toolbar-submenu-item"
                  draggable
                  onDragStart={(e) => {
                    e.dataTransfer.setData('application/json', JSON.stringify({
                      type: 'tool',
                      tool: 'structure',
                      shape: shape.id,
                    }));
                    e.dataTransfer.effectAllowed = 'copy';
                  }}
                  onClick={() => {
                    addStructureBlock(0, 0, shape.id);
                    setShowShapes(false);
                  }}
                  title={shape.label}
                >
                  {shape.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right */}
      <div className="toolbar-right">

      {/* History Controls (placeholder) */}
      <div className="toolbar-group">
        <button
          className={`toolbar-button ${historyIndex <= 0 ? 'disabled' : ''}`}
          title="Undo (Ctrl+Z)"
          onClick={undo}
          disabled={historyIndex <= 0}
        >
          <Undo size={18} />
        </button>
        <button
          className={`toolbar-button ${historyIndex >= history.length - 1 ? 'disabled' : ''}`}
          title="Redo (Ctrl+R)"
          onClick={redo}
          disabled={historyIndex >= history.length - 1}
        >
          <Redo size={18} />
        </button>
      </div>

      {/* Divider */}
      <div className="toolbar-divider" />

      {/* Actions */}
      <div className="toolbar-group">
        <button 
          className="toolbar-button"
          onClick={handleSave}
          title="Save (Ctrl+S)"
        >
          <Save size={18} />
        </button>
        <button className="toolbar-button" title="Export">
          <Download size={18} />
        </button>
      </div>

      {/* Divider */}
      <div className="toolbar-divider" />

      {/* Help */}
      <button className="toolbar-button" title="Help & Shortcuts">
        <HelpCircle size={18} />
      </button>
      </div>
    </div>
  );
};

export default Toolbar;

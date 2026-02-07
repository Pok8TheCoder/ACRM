/**
 * StructureBlock - Simple structural rectangle block
 */

import React, { useState, useCallback } from 'react';
import useStore from '../../store/useStore';
import { Trash2, Edit2, Lock, Unlock } from 'lucide-react';
import './Blocks.css';

const StructureBlock = ({ block }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [label, setLabel] = useState(block.label || 'Structure');

  const {
    updateStructureBlock,
    deleteStructureBlock,
    selectElement,
    isSelected,
    showContextMenu,
    showModal,
    canvas,
    setPanning,
    pushHistory,
    highlightTarget,
  } = useStore();

  const selected = isSelected('structureBlock', block.id);

  const handleMouseDown = useCallback((e) => {
    if (block.locked) {
      setPanning(true, { x: e.clientX - canvas.x, y: e.clientY - canvas.y });
      return;
    }
    if (isEditing) return;
    if (e.button !== 0) return;
    e.stopPropagation();

    selectElement('structureBlock', block.id, e.shiftKey);

    const startX = e.clientX;
    const startY = e.clientY;
    const startBlockX = block.x;
    const startBlockY = block.y;

    const handleMouseMove = (moveEvent) => {
      const zoom = useStore.getState().canvas.zoom;
      const deltaX = (moveEvent.clientX - startX) / zoom;
      const deltaY = (moveEvent.clientY - startY) / zoom;
      updateStructureBlock(block.id, {
        x: startBlockX + deltaX,
        y: startBlockY + deltaY,
      }, { skipHistory: true });
    };

    const handleMouseUp = () => {
      pushHistory();
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [block.id, block.x, block.y, block.locked, isEditing, selectElement, updateStructureBlock, setPanning, canvas.x, canvas.y]);

  const handleContextMenu = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();

    showContextMenu(e.clientX, e.clientY, 'structureBlock', block.id, [
      {
        label: 'Edit Label',
        icon: <Edit2 size={14} />,
        action: () => setIsEditing(true),
      },
      {
        label: 'Style...',
        icon: <Edit2 size={14} />,
        action: () => showModal('stylePicker', { targetType: 'structureBlock', targetId: block.id }),
      },
      {
        label: block.locked ? 'Unlock Position' : 'Lock Position',
        action: () => updateStructureBlock(block.id, { locked: !block.locked }),
      },
      {
        label: 'Send Back',
        action: () => updateStructureBlock(block.id, { zIndex: (block.zIndex || 10) - 1 }),
      },
      {
        label: 'Bring Forward',
        action: () => updateStructureBlock(block.id, { zIndex: (block.zIndex || 10) + 1 }),
      },
      { type: 'divider' },
      {
        label: 'Delete',
        icon: <Trash2 size={14} />,
        action: () => deleteStructureBlock(block.id),
        danger: true,
      },
    ]);
  }, [block.id, showContextMenu, showModal, deleteStructureBlock]);

  const handleLabelSave = useCallback(() => {
    updateStructureBlock(block.id, { label });
    setIsEditing(false);
  }, [block.id, label, updateStructureBlock]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter') {
      handleLabelSave();
    } else if (e.key === 'Escape') {
      setLabel(block.label || 'Structure');
      setIsEditing(false);
    }
  }, [block.label, handleLabelSave]);

  const isHighlighted = highlightTarget?.type === 'structureBlock' && highlightTarget?.id === block.id;

  return (
    <div
      className={`structure-block ${selected ? 'selected' : ''} shape-${block.shape || 'rectangle'} ${block.locked ? 'locked' : ''} ${isHighlighted ? 'highlighted' : ''}`}
      style={{ 
        left: block.x, 
        top: block.y, 
        width: block.width, 
        height: block.height,
        background: block.color,
        opacity: block.opacity ?? 0.6,
        zIndex: block.zIndex ?? 10,
      }}
      onMouseDown={handleMouseDown}
      onContextMenu={handleContextMenu}
      onDoubleClick={() => setIsEditing(true)}
    >
      <button
        className="lock-toggle-btn lock-toggle-overlay"
        onClick={(e) => {
          e.stopPropagation();
          updateStructureBlock(block.id, { locked: !block.locked });
        }}
        title={block.locked ? 'Unlock position' : 'Lock position'}
      >
        {block.locked ? <Lock size={12} /> : <Unlock size={12} />}
      </button>
      <div className="structure-block-content">
        {isEditing ? (
          <input
            className="structure-block-input"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            onBlur={handleLabelSave}
            onKeyDown={handleKeyDown}
          />
        ) : (
          <span className="structure-block-label">{block.label || 'Structure'}</span>
        )}
      </div>
    </div>
  );
};

export default StructureBlock;

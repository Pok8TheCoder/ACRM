/**
 * TextBlock - Simple editable text element
 */

import React, { useState, useCallback, useRef } from 'react';
import useStore from '../../store/useStore';
import { Trash2, Edit2, Lock, Unlock } from 'lucide-react';
import './Blocks.css';

const TextBlock = ({ block }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [text, setText] = useState(block.text || 'Text');
  const inputRef = useRef(null);

  const {
    updateTextBlock,
    deleteTextBlock,
    selectElement,
    isSelected,
    showContextMenu,
    showModal,
    canvas,
    setPanning,
    pushHistory,
    highlightTarget,
  } = useStore();

  const selected = isSelected('textBlock', block.id);

  const handleMouseDown = useCallback((e) => {
    if (block.locked) {
      setPanning(true, { x: e.clientX - canvas.x, y: e.clientY - canvas.y });
      return;
    }
    if (isEditing) return;
    if (e.button !== 0) return;
    e.stopPropagation();

    selectElement('textBlock', block.id, e.shiftKey);

    const startX = e.clientX;
    const startY = e.clientY;
    const startBlockX = block.x;
    const startBlockY = block.y;

    const handleMouseMove = (moveEvent) => {
      const zoom = useStore.getState().canvas.zoom;
      const deltaX = (moveEvent.clientX - startX) / zoom;
      const deltaY = (moveEvent.clientY - startY) / zoom;
      updateTextBlock(block.id, {
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
  }, [block.id, block.x, block.y, block.locked, isEditing, selectElement, updateTextBlock, setPanning, canvas.x, canvas.y]);

  const handleContextMenu = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();

    showContextMenu(e.clientX, e.clientY, 'textBlock', block.id, [
      {
        label: 'Edit Text',
        icon: <Edit2 size={14} />,
        action: () => {
          setIsEditing(true);
          setTimeout(() => inputRef.current?.focus(), 50);
        },
      },
      {
        label: 'Style...',
        icon: <Edit2 size={14} />,
        action: () => showModal('stylePicker', { targetType: 'textBlock', targetId: block.id }),
      },
      {
        label: block.locked ? 'Unlock Position' : 'Lock Position',
        action: () => updateTextBlock(block.id, { locked: !block.locked }),
      },
      {
        label: 'Send Back',
        action: () => updateTextBlock(block.id, { zIndex: (block.zIndex || 30) - 1 }),
      },
      {
        label: 'Bring Forward',
        action: () => updateTextBlock(block.id, { zIndex: (block.zIndex || 30) + 1 }),
      },
      { type: 'divider' },
      {
        label: 'Delete',
        icon: <Trash2 size={14} />,
        action: () => deleteTextBlock(block.id),
        danger: true,
      },
    ]);
  }, [block.id, showContextMenu, showModal, deleteTextBlock]);

  const handleBlur = useCallback(() => {
    updateTextBlock(block.id, { text });
    setIsEditing(false);
  }, [block.id, text, updateTextBlock]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter') {
      handleBlur();
    } else if (e.key === 'Escape') {
      setText(block.text || 'Text');
      setIsEditing(false);
    }
  }, [block.text, handleBlur]);

  const isHighlighted = highlightTarget?.type === 'textBlock' && highlightTarget?.id === block.id;

  return (
    <div
      className={`text-block ${selected ? 'selected' : ''} ${block.locked ? 'locked' : ''} ${isHighlighted ? 'highlighted' : ''}`}
      style={{ 
        left: block.x, 
        top: block.y,
        color: block.color || '#ffffff',
        opacity: block.opacity ?? 1,
        zIndex: block.zIndex ?? 30,
      }}
      onMouseDown={handleMouseDown}
      onContextMenu={handleContextMenu}
      onDoubleClick={() => {
        setIsEditing(true);
        setTimeout(() => inputRef.current?.focus(), 50);
      }}
    >
      <button
        className="lock-toggle-btn lock-toggle-overlay"
        onClick={(e) => {
          e.stopPropagation();
          updateTextBlock(block.id, { locked: !block.locked });
        }}
        title={block.locked ? 'Unlock position' : 'Lock position'}
      >
        {block.locked ? <Lock size={12} /> : <Unlock size={12} />}
      </button>
      {isEditing ? (
        <input
          ref={inputRef}
          className="text-block-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
        />
      ) : (
        <span className="text-block-content">{block.text || 'Text'}</span>
      )}
    </div>
  );
};

export default TextBlock;

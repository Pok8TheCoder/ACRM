/**
 * FreeArrowConnection - Rendered SVG arrow between two points
 */

import React, { useCallback } from 'react';
import useStore from '../../store/useStore';
import './Arrows.css';

const FreeArrowConnection = ({ arrow }) => {
  const { updateFreeArrow, selectElement, isSelected, showContextMenu, showModal } = useStore();

  const from = arrow?.from;
  const to = arrow?.to;
  const arrowId = arrow?.id;

  const selected = arrowId ? isSelected('freeArrow', arrowId) : false;

  const isBlocky = arrow.style === 'blocky';
  const mid = { x: to.x, y: from.y };

  const path = isBlocky
    ? `M ${from.x + 100000} ${from.y + 100000} L ${mid.x + 100000} ${mid.y + 100000} L ${to.x + 100000} ${to.y + 100000}`
    : `M ${from.x + 100000} ${from.y + 100000} L ${to.x + 100000} ${to.y + 100000}`;

  const angle = isBlocky
    ? Math.atan2(to.y - mid.y, to.x - mid.x)
    : Math.atan2(to.y - from.y, to.x - from.x);

  const handleMouseDown = useCallback((e) => {
    if (!arrowId || !from || !to) return;
    if (e.button !== 0) return;
    e.stopPropagation();
    selectElement('freeArrow', arrowId, e.shiftKey);

    const startX = e.clientX;
    const startY = e.clientY;
    const startFrom = { ...from };
    const startTo = { ...to };

    const handleMouseMove = (moveEvent) => {
      const zoom = useStore.getState().canvas.zoom;
      const deltaX = (moveEvent.clientX - startX) / zoom;
      const deltaY = (moveEvent.clientY - startY) / zoom;
      updateFreeArrow(arrowId, {
        from: { x: startFrom.x + deltaX, y: startFrom.y + deltaY },
        to: { x: startTo.x + deltaX, y: startTo.y + deltaY },
      });
    };

    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [arrowId, from, to, selectElement, updateFreeArrow]);

  const handleContextMenu = useCallback((e) => {
    if (!arrowId) return;
    e.preventDefault();
    e.stopPropagation();

    showContextMenu(e.clientX, e.clientY, 'freeArrow', arrowId, [
      {
        label: 'Style...',
        action: () => showModal('stylePicker', { targetType: 'freeArrow', targetId: arrowId }),
      },
      { type: 'divider' },
      {
        label: 'Style: Straight',
        action: () => updateFreeArrow(arrowId, { style: 'straight' }),
      },
      {
        label: 'Style: Blocky',
        action: () => updateFreeArrow(arrowId, { style: 'blocky' }),
      },
    ]);
  }, [arrowId, showContextMenu, showModal, updateFreeArrow]);

  if (!from || !to) return null;

  return (
    <g className={`arrow-connection ${selected ? 'selected' : ''}`}>
      <path
        d={path}
        fill="none"
        stroke="transparent"
        strokeWidth={20}
        onMouseDown={handleMouseDown}
        onContextMenu={handleContextMenu}
        style={{ cursor: 'pointer' }}
      />
      <path
        d={path}
        fill="none"
        stroke={arrow.color || '#4361ee'}
        strokeOpacity={arrow.opacity ?? 1}
        strokeWidth={selected ? 3 : 2}
        strokeLinecap="round"
        style={{ pointerEvents: 'none' }}
      />
      <polygon
        points="-8,-5 0,0 -8,5"
        fill={arrow.color || '#4361ee'}
        opacity={arrow.opacity ?? 1}
        transform={`translate(${to.x + 100000}, ${to.y + 100000}) rotate(${angle * 180 / Math.PI})`}
      />
    </g>
  );
};

export default FreeArrowConnection;

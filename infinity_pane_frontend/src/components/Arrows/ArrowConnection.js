/**
 * ArrowConnection - Rendered SVG arrow between two elements
 */

import React, { useMemo, useCallback } from 'react';
import useStore from '../../store/useStore';
import './Arrows.css';

const ArrowConnection = ({ arrow, teacherPlacements, subjectPlacements }) => {
  const { deleteArrow, selectElement, isSelected, showContextMenu } = useStore();

  // Find the positions of from and to elements
  const positions = useMemo(() => {
    let fromPos = null;
    let toPos = null;

    // Find from position
    if (arrow.from.type === 'teacher') {
      const placement = teacherPlacements.find(p => p.id === arrow.from.placementId);
      if (placement) fromPos = { x: placement.x, y: placement.y };
    } else if (arrow.from.type === 'subject') {
      const placement = subjectPlacements.find(p => p.id === arrow.from.placementId);
      if (placement) fromPos = { x: placement.x, y: placement.y };
    }

    // Find to position
    if (arrow.to.type === 'teacher') {
      const placement = teacherPlacements.find(p => p.id === arrow.to.placementId);
      if (placement) toPos = { x: placement.x, y: placement.y };
    } else if (arrow.to.type === 'subject') {
      const placement = subjectPlacements.find(p => p.id === arrow.to.placementId);
      if (placement) toPos = { x: placement.x, y: placement.y };
    }

    return { from: fromPos, to: toPos };
  }, [arrow, teacherPlacements, subjectPlacements]);

  const handleContextMenu = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    
    showContextMenu(e.clientX, e.clientY, 'arrow', arrow.id, [
      {
        label: 'Delete Connection',
        icon: '🗑️',
        action: () => deleteArrow(arrow.id),
        danger: true,
      },
    ]);
  }, [arrow.id, showContextMenu, deleteArrow]);

  const handleClick = useCallback((e) => {
    e.stopPropagation();
    selectElement('arrow', arrow.id, e.shiftKey);
  }, [arrow.id, selectElement]);

  if (!positions.from || !positions.to) return null;

  const selected = isSelected('arrow', arrow.id);

  // Calculate control points for curved arrow
  const dx = positions.to.x - positions.from.x;
  const dy = positions.to.y - positions.from.y;
  const distance = Math.sqrt(dx * dx + dy * dy);
  
  // Create a nice bezier curve
  const curvature = Math.min(50, distance * 0.3);
  const midX = (positions.from.x + positions.to.x) / 2;
  const midY = (positions.from.y + positions.to.y) / 2;
  
  // Perpendicular offset for the control point
  const perpX = -dy / distance * curvature;
  const perpY = dx / distance * curvature;
  
  const controlX = midX + perpX;
  const controlY = midY + perpY;

  // SVG path for quadratic bezier curve
  const path = `M ${positions.from.x + 100000} ${positions.from.y + 100000} 
                Q ${controlX + 100000} ${controlY + 100000} 
                  ${positions.to.x + 100000} ${positions.to.y + 100000}`;

  // Calculate arrow head angle
  const t = 0.95; // Position along the curve for arrow head
  
  // Tangent at arrow head
  const tangentX = 2*(1-t)*(controlX - positions.from.x) + 2*t*(positions.to.x - controlX);
  const tangentY = 2*(1-t)*(controlY - positions.from.y) + 2*t*(positions.to.y - controlY);
  const angle = Math.atan2(tangentY, tangentX);

  return (
    <g className={`arrow-connection ${selected ? 'selected' : ''}`}>
      {/* Invisible wider path for easier selection */}
      <path
        d={path}
        fill="none"
        stroke="transparent"
        strokeWidth={20}
        style={{ cursor: 'pointer' }}
        onClick={handleClick}
        onContextMenu={handleContextMenu}
      />
      
      {/* Visible path */}
      <path
        d={path}
        fill="none"
        stroke={selected ? 'var(--accent-primary)' : arrow.color || '#4361ee'}
        strokeWidth={selected ? 3 : 2}
        strokeLinecap="round"
        style={{ pointerEvents: 'none' }}
      />
      
      {/* Arrow head */}
      <polygon
        points="-8,-5 0,0 -8,5"
        fill={selected ? 'var(--accent-primary)' : arrow.color || '#4361ee'}
        transform={`translate(${positions.to.x + 100000}, ${positions.to.y + 100000}) rotate(${angle * 180 / Math.PI})`}
      />
      
      {/* Selection indicator dots */}
      {selected && (
        <>
          <circle
            cx={positions.from.x + 100000}
            cy={positions.from.y + 100000}
            r={5}
            fill="var(--accent-primary)"
          />
          <circle
            cx={positions.to.x + 100000}
            cy={positions.to.y + 100000}
            r={5}
            fill="var(--accent-primary)"
          />
        </>
      )}
    </g>
  );
};

export default ArrowConnection;

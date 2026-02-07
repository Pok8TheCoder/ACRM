/**
 * ClassSubjectArrowConnection - Arrow between teacher placement and class subject row
 */

import React from 'react';
import './Arrows.css';

const ClassSubjectArrowConnection = ({ from, to, color = '#5b7cfa' }) => {
  if (!from || !to) return null;

  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const distance = Math.sqrt(dx * dx + dy * dy);
  if (!Number.isFinite(distance) || distance === 0) return null;

  const curvature = Math.min(50, distance * 0.3);
  const midX = (from.x + to.x) / 2;
  const midY = (from.y + to.y) / 2;
  const perpX = -dy / distance * curvature;
  const perpY = dx / distance * curvature;
  const controlX = midX + perpX;
  const controlY = midY + perpY;

  const path = `M ${from.x + 100000} ${from.y + 100000} 
                Q ${controlX + 100000} ${controlY + 100000} 
                  ${to.x + 100000} ${to.y + 100000}`;

  const t = 0.95;
  const tangentX = 2 * (1 - t) * (controlX - from.x) + 2 * t * (to.x - controlX);
  const tangentY = 2 * (1 - t) * (controlY - from.y) + 2 * t * (to.y - controlY);
  const angle = Math.atan2(tangentY, tangentX);

  return (
    <g className="arrow-connection class-subject-arrow">
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeDasharray="5 4"
      />
      <polygon
        points="-8,-5 0,0 -8,5"
        fill={color}
        transform={`translate(${to.x + 100000}, ${to.y + 100000}) rotate(${angle * 180 / Math.PI})`}
      />
    </g>
  );
};

export default ClassSubjectArrowConnection;

/**
 * ArrowDrawing - Visual feedback while drawing an arrow
 */

import React from 'react';
import './Arrows.css';

const ArrowDrawing = ({ drawing, label = 'Click target to connect' }) => {
  if (!drawing) return null;

  const { from, currentX, currentY } = drawing;

  // Simple straight line while drawing
  const path = `M ${from.x + 100000} ${from.y + 100000} L ${currentX + 100000} ${currentY + 100000}`;

  return (
    <g className="arrow-drawing">
      {/* Main line */}
      <path
        d={path}
        fill="none"
        stroke="var(--accent-primary)"
        strokeWidth={2}
        strokeDasharray="8 4"
        strokeLinecap="round"
      />
      
      {/* Start point */}
      <circle
        cx={from.x + 100000}
        cy={from.y + 100000}
        r={6}
        fill="var(--accent-primary)"
      />
      
      {/* End point (cursor position) */}
      <circle
        cx={currentX + 100000}
        cy={currentY + 100000}
        r={6}
        fill="none"
        stroke="var(--accent-primary)"
        strokeWidth={2}
        strokeDasharray="4 2"
      />
      
      {/* Label */}
      <text
        x={currentX + 100000 + 15}
        y={currentY + 100000 - 15}
        fill="var(--text-secondary)"
        fontSize={12}
        fontFamily="sans-serif"
      >
        {label}
      </text>
    </g>
  );
};

export default ArrowDrawing;

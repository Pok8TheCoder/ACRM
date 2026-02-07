/**
 * GridBackground - Infinite grid pattern that moves with canvas
 */

import React, { useMemo } from 'react';
import './GridBackground.css';

const GridBackground = ({ zoom, x, y }) => {
  // Calculate grid properties based on zoom level
  const gridConfig = useMemo(() => {
    // Base grid size
    let gridSize = 50;
    let majorGridEvery = 5;
    
    // Adjust grid size based on zoom
    if (zoom < 0.2) {
      gridSize = 200;
      majorGridEvery = 5;
    } else if (zoom < 0.5) {
      gridSize = 100;
      majorGridEvery = 5;
    } else if (zoom > 3) {
      gridSize = 25;
      majorGridEvery = 4;
    } else if (zoom > 6) {
      gridSize = 10;
      majorGridEvery = 5;
    }
    
    return { gridSize, majorGridEvery };
  }, [zoom]);

  const { gridSize, majorGridEvery } = gridConfig;
  const majorGridSize = gridSize * majorGridEvery;

  // Calculate offset for seamless scrolling
  const offsetX = ((x % (majorGridSize * zoom)) + majorGridSize * zoom) % (majorGridSize * zoom);
  const offsetY = ((y % (majorGridSize * zoom)) + majorGridSize * zoom) % (majorGridSize * zoom);

  return (
    <div className="grid-background">
      {/* Minor grid */}
      <div 
        className="grid-minor"
        style={{
          backgroundSize: `${gridSize * zoom}px ${gridSize * zoom}px`,
          backgroundPosition: `${offsetX}px ${offsetY}px`,
        }}
      />
      
      {/* Major grid */}
      <div 
        className="grid-major"
        style={{
          backgroundSize: `${majorGridSize * zoom}px ${majorGridSize * zoom}px`,
          backgroundPosition: `${offsetX}px ${offsetY}px`,
        }}
      />
      
      {/* Origin crosshair */}
      <div 
        className="origin-marker"
        style={{
          transform: `translate(calc(50% + ${x}px), calc(50% + ${y}px))`,
        }}
      >
        <div className="origin-x" />
        <div className="origin-y" />
        <div className="origin-dot" />
      </div>
    </div>
  );
};

export default GridBackground;

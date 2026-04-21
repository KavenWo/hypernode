import React from 'react';

export default function HealthGauge({ 
  value, 
  min = 0, 
  max = 100, 
  low, 
  high, 
  unit = "", 
  color = "var(--green)" 
}) {
  // Calculate percentage for the marker
  const percentage = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));
  
  // Calculate thresholds for background segments
  const lowPercent = low ? ((low - min) / (max - min)) * 100 : 0;
  const highPercent = high ? ((high - min) / (max - min)) * 100 : 100;

  return (
    <div className="health-gauge">
      <div className="gauge-track">
        {/* Background segments for range context */}
        <div className="gauge-segment normal" style={{ left: `${lowPercent}%`, width: `${highPercent - lowPercent}%` }}></div>
        {low && <div className="gauge-segment warn-low" style={{ left: 0, width: `${lowPercent}%` }}></div>}
        {high && <div className="gauge-segment warn-high" style={{ left: `${highPercent}%`, width: `${100 - highPercent}%` }}></div>}
        
        {/* Current value marker */}
        <div 
          className="gauge-marker" 
          style={{ 
            left: `${percentage}%`,
            background: color,
            boxShadow: `0 0 8px ${color}`
          }}
        ></div>
      </div>
    </div>
  );
}

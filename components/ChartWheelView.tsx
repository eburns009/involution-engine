'use client';

import { useState } from 'react';
import type { CalculateResponse } from '@/lib/astroTypes';

interface Props {
  data: CalculateResponse;
}

const ZODIAC_SIGNS = [
  { name: 'Aries', symbol: '♈', start: 0 },
  { name: 'Taurus', symbol: '♉', start: 30 },
  { name: 'Gemini', symbol: '♊', start: 60 },
  { name: 'Cancer', symbol: '♋', start: 90 },
  { name: 'Leo', symbol: '♌', start: 120 },
  { name: 'Virgo', symbol: '♍', start: 150 },
  { name: 'Libra', symbol: '♎', start: 180 },
  { name: 'Scorpio', symbol: '♏', start: 210 },
  { name: 'Sagittarius', symbol: '♐', start: 240 },
  { name: 'Capricorn', symbol: '♑', start: 270 },
  { name: 'Aquarius', symbol: '♒', start: 300 },
  { name: 'Pisces', symbol: '♓', start: 330 },
];

const PLANET_SYMBOLS: Record<string, string> = {
  Sun: '☉',
  Moon: '☽',
  Mercury: '☿',
  Venus: '♀',
  Mars: '♂',
  Jupiter: '♃',
  Saturn: '♄',
};

const PLANET_COLORS: Record<string, string> = {
  Sun: '#FFA500',
  Moon: '#C0C0C0',
  Mercury: '#FFD700',
  Venus: '#FF69B4',
  Mars: '#DC143C',
  Jupiter: '#4169E1',
  Saturn: '#8B4513',
};

export default function ChartWheelView({ data }: Props) {
  const [showAspectLines, setShowAspectLines] = useState(false);
  const [starHouseView, setStarHouseView] = useState(false);
  const [showLabels, setShowLabels] = useState(true);

  const size = 600;
  const center = size / 2;
  const outerRadius = 280;
  const innerRadius = 220;
  const planetRadius = 180;

  // Convert degrees to SVG coordinates (rotate -90 to start at top)
  const polarToCartesian = (angle: number, radius: number): { x: number; y: number } => {
    const radians = ((angle - 90) * Math.PI) / 180;
    return {
      x: center + radius * Math.cos(radians),
      y: center + radius * Math.sin(radians),
    };
  };

  // Draw arc path for zodiac signs
  const describeArc = (startAngle: number, endAngle: number, radius: number): string => {
    const start = polarToCartesian(endAngle, radius);
    const end = polarToCartesian(startAngle, radius);
    const largeArcFlag = endAngle - startAngle <= 180 ? '0' : '1';
    return [
      'M', start.x, start.y,
      'A', radius, radius, 0, largeArcFlag, 0, end.x, end.y,
    ].join(' ');
  };

  const bodies: Array<keyof typeof data.data> = [
    'Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn'
  ];

  // Calculate aspect lines (simplified - just major aspects)
  const aspects: Array<{ from: string; to: string; type: string; color: string }> = [];

  if (showAspectLines) {
    bodies.forEach((p1, i) => {
      bodies.slice(i + 1).forEach(p2 => {
        const lon1 = data.data[p1].longitude;
        const lon2 = data.data[p2].longitude;
        let diff = Math.abs(lon1 - lon2);
        if (diff > 180) diff = 360 - diff;

        // Check aspects with 8° orb
        const orb = 8;
        if (Math.abs(diff - 0) < orb) {
          aspects.push({ from: p1, to: p2, type: 'conjunction', color: '#FFD700' });
        } else if (Math.abs(diff - 180) < orb) {
          aspects.push({ from: p1, to: p2, type: 'opposition', color: '#DC143C' });
        } else if (Math.abs(diff - 120) < orb) {
          aspects.push({ from: p1, to: p2, type: 'trine', color: '#4169E1' });
        } else if (Math.abs(diff - 90) < orb) {
          aspects.push({ from: p1, to: p2, type: 'square', color: '#FF6347' });
        } else if (Math.abs(diff - 60) < orb) {
          aspects.push({ from: p1, to: p2, type: 'sextile', color: '#32CD32' });
        }
      });
    });
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-muted bg-card p-4">
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <label className="flex items-center gap-2 text-fg cursor-pointer">
            <input
              type="checkbox"
              checked={showAspectLines}
              onChange={(e) => setShowAspectLines(e.target.checked)}
              className="rounded border-muted text-accent focus:ring-accent"
            />
            <span>Show aspect lines</span>
          </label>

          <label className="flex items-center gap-2 text-fg cursor-pointer">
            <input
              type="checkbox"
              checked={showLabels}
              onChange={(e) => setShowLabels(e.target.checked)}
              className="rounded border-muted text-accent focus:ring-accent"
            />
            <span>Show labels</span>
          </label>

          <label className="flex items-center gap-2 text-fg cursor-pointer" title="Reverse wheel for Southern Hemisphere observers">
            <input
              type="checkbox"
              checked={starHouseView}
              onChange={(e) => setStarHouseView(e.target.checked)}
              className="rounded border-muted text-accent focus:ring-accent"
            />
            <span>Southern Hemisphere View</span>
          </label>
        </div>

        <button
          onClick={() => {
            const svg = document.getElementById('chart-wheel-svg');
            if (!svg) return;

            const svgData = new XMLSerializer().serializeToString(svg);
            const blob = new Blob([svgData], { type: 'image/svg+xml' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `chart-wheel-${Date.now()}.svg`;
            a.click();
            URL.revokeObjectURL(url);
          }}
          className="rounded border border-muted bg-bg px-3 py-1.5 text-sm text-fg hover:border-accent hover:bg-accent hover:text-white transition-all"
        >
          📥 Export SVG
        </button>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 rounded-lg border border-muted bg-card p-4 text-xs">
        <span className="font-medium text-fg">Aspects:</span>
        <div className="flex items-center gap-2">
          <span style={{ color: '#FFD700' }}>●</span>
          <span className="text-fg">Conjunction (0°)</span>
        </div>
        <div className="flex items-center gap-2">
          <span style={{ color: '#DC143C' }}>●</span>
          <span className="text-fg">Opposition (180°)</span>
        </div>
        <div className="flex items-center gap-2">
          <span style={{ color: '#4169E1' }}>●</span>
          <span className="text-fg">Trine (120°)</span>
        </div>
        <div className="flex items-center gap-2">
          <span style={{ color: '#FF6347' }}>●</span>
          <span className="text-fg">Square (90°)</span>
        </div>
        <div className="flex items-center gap-2">
          <span style={{ color: '#32CD32' }}>●</span>
          <span className="text-fg">Sextile (60°)</span>
        </div>
      </div>

      {/* Chart Wheel */}
      <div className="flex justify-center rounded-lg border border-muted bg-card p-8">
        <svg
          id="chart-wheel-svg"
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="max-w-full h-auto"
          style={{ transform: starHouseView ? 'scaleX(-1)' : undefined }}
        >
          {/* Background */}
          <circle cx={center} cy={center} r={outerRadius} fill="#f9f9f9" stroke="#333" strokeWidth="2" />

          {/* Zodiac ring */}
          {ZODIAC_SIGNS.map((sign, idx) => {
            const startAngle = sign.start;
            const endAngle = startAngle + 30;
            const midAngle = startAngle + 15;
            const labelPos = polarToCartesian(midAngle, (outerRadius + innerRadius) / 2);

            return (
              <g key={sign.name}>
                {/* Sign sector */}
                <path
                  d={`
                    M ${center} ${center}
                    L ${polarToCartesian(startAngle, outerRadius).x} ${polarToCartesian(startAngle, outerRadius).y}
                    A ${outerRadius} ${outerRadius} 0 0 1 ${polarToCartesian(endAngle, outerRadius).x} ${polarToCartesian(endAngle, outerRadius).y}
                    Z
                    M ${center} ${center}
                    L ${polarToCartesian(startAngle, innerRadius).x} ${polarToCartesian(startAngle, innerRadius).y}
                    A ${innerRadius} ${innerRadius} 0 0 1 ${polarToCartesian(endAngle, innerRadius).x} ${polarToCartesian(endAngle, innerRadius).y}
                    Z
                  `}
                  fill={idx % 2 === 0 ? '#ffffff' : '#f0f0f0'}
                  stroke="#ccc"
                  strokeWidth="1"
                />

                {/* Sign symbol */}
                {showLabels && (
                  <text
                    x={labelPos.x}
                    y={labelPos.y}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize="20"
                    fontWeight="bold"
                    fill="#666"
                    style={{ transform: starHouseView ? `translate(${labelPos.x}px, ${labelPos.y}px) scaleX(-1) translate(-${labelPos.x}px, -${labelPos.y}px)` : undefined }}
                  >
                    {sign.symbol}
                  </text>
                )}

                {/* Degree markers */}
                {[0, 10, 20].map(deg => {
                  const angle = startAngle + deg;
                  const outer = polarToCartesian(angle, outerRadius);
                  const inner = polarToCartesian(angle, outerRadius - 10);
                  return (
                    <line
                      key={deg}
                      x1={outer.x}
                      y1={outer.y}
                      x2={inner.x}
                      y2={inner.y}
                      stroke="#999"
                      strokeWidth="1"
                    />
                  );
                })}
              </g>
            );
          })}

          {/* Inner circle */}
          <circle cx={center} cy={center} r={innerRadius} fill="white" stroke="#333" strokeWidth="2" />

          {/* Aspect lines */}
          {aspects.map((aspect, idx) => {
            const pos1 = polarToCartesian(data.data[aspect.from as keyof typeof data.data].longitude, planetRadius - 40);
            const pos2 = polarToCartesian(data.data[aspect.to as keyof typeof data.data].longitude, planetRadius - 40);
            return (
              <line
                key={idx}
                x1={pos1.x}
                y1={pos1.y}
                x2={pos2.x}
                y2={pos2.y}
                stroke={aspect.color}
                strokeWidth="1"
                strokeDasharray="4,4"
                opacity="0.6"
              />
            );
          })}

          {/* Planets */}
          {bodies.map((body) => {
            const position = data.data[body];
            const pos = polarToCartesian(position.longitude, planetRadius);
            const color = PLANET_COLORS[body] || '#000';

            return (
              <g key={body}>
                {/* Planet marker line */}
                <line
                  x1={polarToCartesian(position.longitude, innerRadius).x}
                  y1={polarToCartesian(position.longitude, innerRadius).y}
                  x2={pos.x}
                  y2={pos.y}
                  stroke={color}
                  strokeWidth="2"
                />

                {/* Planet symbol */}
                <circle cx={pos.x} cy={pos.y} r="18" fill="white" stroke={color} strokeWidth="2" />
                <text
                  x={pos.x}
                  y={pos.y}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fontSize="20"
                  fill={color}
                  fontWeight="bold"
                  style={{ transform: starHouseView ? `translate(${pos.x}px, ${pos.y}px) scaleX(-1) translate(-${pos.x}px, -${pos.y}px)` : undefined }}
                >
                  {PLANET_SYMBOLS[body]}
                </text>

                {/* Planet label */}
                {showLabels && (
                  <text
                    x={polarToCartesian(position.longitude, planetRadius - 30).x}
                    y={polarToCartesian(position.longitude, planetRadius - 30).y}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize="11"
                    fill="#333"
                    fontWeight="600"
                    style={{ transform: starHouseView ? `translate(${polarToCartesian(position.longitude, planetRadius - 30).x}px, ${polarToCartesian(position.longitude, planetRadius - 30).y}px) scaleX(-1) translate(-${polarToCartesian(position.longitude, planetRadius - 30).x}px, -${polarToCartesian(position.longitude, planetRadius - 30).y}px)` : undefined }}
                  >
                    {body}
                  </text>
                )}
              </g>
            );
          })}

          {/* Center info */}
          <text
            x={center}
            y={center - 10}
            textAnchor="middle"
            fontSize="14"
            fill="#666"
            fontWeight="600"
          >
            Sidereal Chart
          </text>
          <text
            x={center}
            y={center + 10}
            textAnchor="middle"
            fontSize="12"
            fill="#999"
          >
            {data.meta.ecliptic_frame}
          </text>
        </svg>
      </div>

      {/* Aspect list */}
      {showAspectLines && aspects.length > 0 && (
        <details className="rounded-lg border border-muted bg-card p-4">
          <summary className="cursor-pointer text-sm font-medium text-fg hover:text-accent">
            Aspects Found ({aspects.length})
          </summary>
          <div className="mt-3 space-y-1">
            {aspects.map((aspect, idx) => (
              <div key={idx} className="text-sm text-fg flex items-center gap-2">
                <span style={{ color: aspect.color }}>●</span>
                <span className="font-medium">{aspect.from}</span>
                <span className="text-muted">{aspect.type}</span>
                <span className="font-medium">{aspect.to}</span>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

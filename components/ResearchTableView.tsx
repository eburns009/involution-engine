'use client';

import { useState } from 'react';
import type { CalculateResponse } from '@/lib/astroTypes';

interface Props {
  data: CalculateResponse;
  onExport?: (format: 'json' | 'csv') => void;
}

type AngleFormat = 'decimal' | 'dms';

function formatAngle(deg: number, format: AngleFormat = 'decimal', precision: number = 4): string {
  // Normalize to [0, 360)
  let normalized = deg % 360;
  if (normalized < 0) normalized += 360;

  if (format === 'decimal') {
    return `${normalized.toFixed(precision)}°`;
  }

  // DMS format
  const d = Math.floor(normalized);
  const minFull = (normalized - d) * 60;
  const m = Math.floor(minFull);
  const s = Math.round((minFull - m) * 60);
  return `${d}° ${String(m).padStart(2, '0')}′ ${String(s).padStart(2, '0')}″`;
}

function formatLatitude(deg: number, format: AngleFormat = 'decimal', precision: number = 4): string {
  if (format === 'decimal') {
    return `${deg >= 0 ? '+' : ''}${deg.toFixed(precision)}°`;
  }

  const abs = Math.abs(deg);
  const d = Math.floor(abs);
  const minFull = (abs - d) * 60;
  const m = Math.floor(minFull);
  const s = Math.round((minFull - m) * 60);
  const dir = deg >= 0 ? '+' : '-';
  return `${dir}${d}° ${String(m).padStart(2, '0')}′ ${String(s).padStart(2, '0')}″`;
}

function getSignAndDegree(lon: number): { sign: string; deg: number } {
  const signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
                 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'];
  let normalized = lon % 360;
  if (normalized < 0) normalized += 360;

  const signIndex = Math.floor(normalized / 30);
  const degInSign = normalized % 30;

  return {
    sign: signs[signIndex],
    deg: degInSign
  };
}

export default function ResearchTableView({ data, onExport }: Props) {
  const [angleFormat, setAngleFormat] = useState<AngleFormat>('decimal');
  const [precision, setPrecision] = useState(4);
  const [showMetadata, setShowMetadata] = useState(true);
  const [columnVisibility, setColumnVisibility] = useState({
    longitude: true,
    latitude: true,
    distance: true,
    sign: true,
  });

  const bodies: Array<keyof typeof data.data> = [
    'Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn'
  ];

  const handleExport = (format: 'json' | 'csv') => {
    if (format === 'json') {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `chart-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } else if (format === 'csv') {
      // CSV export
      const headers = ['Body', 'Longitude (°)', 'Latitude (°)', 'Distance (AU)', 'Sign', 'Deg in Sign'];
      const rows = bodies.map(body => {
        const pos = data.data[body];
        const { sign, deg } = getSignAndDegree(pos.longitude);
        return [
          body,
          pos.longitude.toFixed(precision),
          pos.latitude.toFixed(precision),
          pos.distance.toFixed(precision),
          sign,
          deg.toFixed(2)
        ].join(',');
      });
      const csv = [headers.join(','), ...rows].join('\n');

      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `chart-${Date.now()}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    }

    onExport?.(format);
  };

  const handleCopyJSON = () => {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
  };

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-muted bg-card p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-fg">Format:</label>
            <select
              value={angleFormat}
              onChange={(e) => setAngleFormat(e.target.value as AngleFormat)}
              className="rounded border border-muted bg-bg px-2 py-1 text-sm text-fg outline-none focus:border-accent focus:ring-1 focus:ring-accent"
            >
              <option value="decimal">Decimal</option>
              <option value="dms">DMS (Deg° Min′ Sec″)</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-fg">Precision:</label>
            <input
              type="number"
              min="1"
              max="6"
              value={precision}
              onChange={(e) => setPrecision(Number(e.target.value))}
              className="w-16 rounded border border-muted bg-bg px-2 py-1 text-sm text-fg outline-none focus:border-accent focus:ring-1 focus:ring-accent"
            />
          </div>

          <button
            onClick={() => setShowMetadata(!showMetadata)}
            className="text-sm text-accent hover:underline"
          >
            {showMetadata ? '▼' : '▶'} Metadata
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => handleExport('json')}
            className="rounded border border-muted bg-bg px-3 py-1.5 text-sm text-fg hover:border-accent hover:bg-accent hover:text-white transition-all"
            title="Export as JSON"
          >
            📥 JSON
          </button>
          <button
            onClick={() => handleExport('csv')}
            className="rounded border border-muted bg-bg px-3 py-1.5 text-sm text-fg hover:border-accent hover:bg-accent hover:text-white transition-all"
            title="Export as CSV"
          >
            📥 CSV
          </button>
          <button
            onClick={handleCopyJSON}
            className="rounded border border-muted bg-bg px-3 py-1.5 text-sm text-fg hover:border-accent hover:bg-accent hover:text-white transition-all"
            title="Copy JSON to clipboard"
          >
            📋 Copy
          </button>
        </div>
      </div>

      {/* Metadata */}
      {showMetadata && (
        <div className="rounded-lg border border-muted bg-card p-4 text-sm">
          <h3 className="mb-2 font-semibold text-fg">Technical Metadata</h3>
          <dl className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <dt className="font-medium text-muted">Ecliptic Frame:</dt>
              <dd className="text-fg">{data.meta.ecliptic_frame}</dd>
            </div>
            {data.meta.ecliptic_model && (
              <div>
                <dt className="font-medium text-muted">Ecliptic Model:</dt>
                <dd className="text-fg">{data.meta.ecliptic_model}</dd>
              </div>
            )}
            <div>
              <dt className="font-medium text-muted">SPICE Version:</dt>
              <dd className="text-fg font-mono">{data.meta.spice_version}</dd>
            </div>
            <div>
              <dt className="font-medium text-muted">Service Version:</dt>
              <dd className="text-fg">{data.meta.service_version}</dd>
            </div>
            <div>
              <dt className="font-medium text-muted">Kernel Set:</dt>
              <dd className="text-fg">{data.meta.kernel_set_tag}</dd>
            </div>
            <div>
              <dt className="font-medium text-muted">Request ID:</dt>
              <dd className="text-fg font-mono text-xs">{data.meta.request_id}</dd>
            </div>
          </dl>
          <div className="mt-3 text-xs text-muted">
            <p className="mb-1"><strong>Coordinate System:</strong> Topocentric, Ecliptic-of-Date (IAU-1980 mean), Light-Time + Stellar Aberration (LT+S)</p>
            <p><strong>Coverage:</strong> DE440 ephemeris (1550–2650 CE)</p>
          </div>
        </div>
      )}

      {/* Ephemeris Table */}
      <div className="overflow-x-auto rounded-lg border border-muted bg-card">
        <table className="min-w-full text-sm">
          <thead className="border-b border-muted bg-muted bg-opacity-20">
            <tr>
              <th
                scope="col"
                className="px-4 py-3 text-left font-semibold text-fg"
              >
                Body
              </th>
              {columnVisibility.longitude && (
                <th
                  scope="col"
                  className="px-4 py-3 text-right font-semibold text-fg"
                  title="Ecliptic longitude (0-360°)"
                >
                  Longitude
                </th>
              )}
              {columnVisibility.latitude && (
                <th
                  scope="col"
                  className="px-4 py-3 text-right font-semibold text-fg"
                  title="Ecliptic latitude (-90 to +90°)"
                >
                  Latitude
                </th>
              )}
              {columnVisibility.distance && (
                <th
                  scope="col"
                  className="px-4 py-3 text-right font-semibold text-fg"
                  title="Distance from observer in Astronomical Units"
                >
                  Distance (AU)
                </th>
              )}
              {columnVisibility.sign && (
                <th
                  scope="col"
                  className="px-4 py-3 text-left font-semibold text-fg"
                  title="Zodiac sign and degree within sign"
                >
                  Sign Position
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {bodies.map((body, idx) => {
              const pos = data.data[body];
              const { sign, deg } = getSignAndDegree(pos.longitude);

              return (
                <tr
                  key={body}
                  className={`border-b border-muted last:border-0 hover:bg-muted hover:bg-opacity-10 transition-colors ${
                    idx % 2 === 0 ? 'bg-opacity-5' : ''
                  }`}
                >
                  <td className="px-4 py-3 font-medium text-fg">
                    {body}
                  </td>
                  {columnVisibility.longitude && (
                    <td className="px-4 py-3 text-right font-mono text-fg">
                      {formatAngle(pos.longitude, angleFormat, precision)}
                    </td>
                  )}
                  {columnVisibility.latitude && (
                    <td className="px-4 py-3 text-right font-mono text-fg">
                      {formatLatitude(pos.latitude, angleFormat, precision)}
                    </td>
                  )}
                  {columnVisibility.distance && (
                    <td className="px-4 py-3 text-right font-mono text-fg">
                      {pos.distance.toFixed(precision)}
                    </td>
                  )}
                  {columnVisibility.sign && (
                    <td className="px-4 py-3 text-fg">
                      {sign} {deg.toFixed(2)}°
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Column visibility controls */}
      <details className="rounded-lg border border-muted bg-card p-4">
        <summary className="cursor-pointer text-sm font-medium text-fg hover:text-accent">
          Column Visibility
        </summary>
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {Object.entries(columnVisibility).map(([key, value]) => (
            <label key={key} className="flex items-center gap-2 text-sm text-fg">
              <input
                type="checkbox"
                checked={value}
                onChange={(e) => setColumnVisibility({
                  ...columnVisibility,
                  [key]: e.target.checked
                })}
                className="rounded border-muted text-accent focus:ring-accent"
              />
              <span className="capitalize">{key}</span>
            </label>
          ))}
        </div>
      </details>
    </div>
  );
}

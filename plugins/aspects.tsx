'use client';
import type { Plugin } from '@/lib/plugins';
import type { CalculateResponse } from '@/lib/astroTypes';

function angleDiff(a: number, b: number): number {
  let d = Math.abs(a - b) % 360;
  return d > 180 ? 360 - d : d;
}

function Panel({ data }: { data: CalculateResponse }) {
  const names = Object.keys(data.data) as (keyof typeof data.data)[];
  const rows: Array<{ a: string; b: string; sep: number; kind: string; orb: number }> = [];

  const aspects = [
    { angle: 0, name: 'Conjunction', symbol: '☌', orb: 8 },
    { angle: 60, name: 'Sextile', symbol: '⚹', orb: 6 },
    { angle: 90, name: 'Square', symbol: '□', orb: 8 },
    { angle: 120, name: 'Trine', symbol: '△', orb: 8 },
    { angle: 180, name: 'Opposition', symbol: '☍', orb: 8 },
  ];

  for (let i = 0; i < names.length; i++) {
    for (let j = i + 1; j < names.length; j++) {
      const A = names[i];
      const B = names[j];
      const sep = angleDiff(data.data[A].longitude, data.data[B].longitude);

      for (const aspect of aspects) {
        const orb = Math.abs(sep - aspect.angle);
        if (orb <= aspect.orb) {
          rows.push({
            a: String(A),
            b: String(B),
            sep,
            kind: `${aspect.symbol} ${aspect.name}`,
            orb
          });
          break; // Only match the first valid aspect
        }
      }
    }
  }

  // Sort by orb (tighter aspects first)
  rows.sort((a, b) => a.orb - b.orb);

  return (
    <div className="rounded-2xl border border-muted bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-fg">Major Aspects</h3>
        <span className="text-xs text-muted">{rows.length} found</span>
      </div>

      {rows.length === 0 ? (
        <div className="text-sm text-muted">No major aspects within orb</div>
      ) : (
        <div className="grid gap-2">
          {rows.map((row, i) => (
            <div key={i} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <span className="font-medium text-fg">
                  {row.a} – {row.b}
                </span>
                <span className="text-muted">
                  {row.kind}
                </span>
              </div>
              <div className="text-right">
                <div className="font-mono text-fg">
                  {row.sep.toFixed(2)}°
                </div>
                <div className="text-xs text-muted">
                  ±{row.orb.toFixed(1)}°
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export const AspectsPlugin: Plugin = {
  id: 'aspects',
  label: 'Aspects',
  Panel: Panel
};
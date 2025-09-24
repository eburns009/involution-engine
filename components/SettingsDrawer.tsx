'use client';
import { useEffect, useState } from 'react';
import { loadSettings, saveSettings, type Settings, type ColumnKey } from '@/lib/settings';
import { useTheme } from './ThemeProvider';

export default function SettingsDrawer() {
  const { theme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const [s, setS] = useState<Settings | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setS(loadSettings());
  }, []);

  useEffect(() => {
    if (s && mounted) {
      saveSettings(s);
      if (s.theme !== theme) {
        setTheme(s.theme);
      }
    }
  }, [s, theme, setTheme, mounted]);

  if (!s || !mounted) return null;

  const toggleCol = (c: ColumnKey) => {
    setS({
      ...s,
      columns: s.columns.includes(c)
        ? s.columns.filter(x => x !== c)
        : [...s.columns, c]
    });
  };

  return (
    <>
      <button
        onClick={() => setOpen(!open)}
        className="fixed bottom-5 right-5 rounded-xl bg-accent px-4 py-2 text-white shadow-lg hover:opacity-90 transition-opacity z-50"
      >
        ⚙️ Settings
      </button>

      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black bg-opacity-50 z-40"
            onClick={() => setOpen(false)}
          />

          {/* Settings Panel */}
          <div className="fixed bottom-16 right-5 w-96 rounded-2xl border bg-card p-5 shadow-2xl z-50">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-fg">Display Settings</h3>
              <button
                onClick={() => setOpen(false)}
                className="text-sm text-muted hover:text-fg transition-colors"
              >
                ✕
              </button>
            </div>

            <div className="mt-4 grid gap-4">
              {/* Theme Selection */}
              <div>
                <div className="text-xs text-muted mb-2 font-medium">Theme</div>
                <div className="flex gap-2">
                  {(['light', 'dark', 'astro'] as const).map(t => (
                    <button
                      key={t}
                      onClick={() => setS({ ...s, theme: t })}
                      className={`rounded-lg border px-3 py-1.5 text-sm capitalize transition-colors ${
                        s.theme === t
                          ? 'bg-accent text-white border-accent'
                          : 'bg-bg text-fg border-muted hover:border-accent'
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              {/* Column Visibility */}
              <div>
                <div className="text-xs text-muted mb-2 font-medium">Visible Columns</div>
                <div className="grid gap-2">
                  {(['longitude', 'latitude', 'distance'] as const).map(c => (
                    <label key={c} className="inline-flex items-center gap-2 text-sm cursor-pointer">
                      <input
                        type="checkbox"
                        checked={s.columns.includes(c)}
                        onChange={() => toggleCol(c)}
                        className="rounded border-muted text-accent focus:ring-accent focus:ring-opacity-50"
                      />
                      <span className="capitalize text-fg">{c}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Precision Controls */}
              <div>
                <div className="text-xs text-muted mb-2 font-medium">Decimal Precision</div>
                <div className="grid grid-cols-3 gap-2">
                  <NumberInput
                    label="Longitude"
                    value={s.precision.lon}
                    onChange={(v) => setS({ ...s, precision: { ...s.precision, lon: v } })}
                  />
                  <NumberInput
                    label="Latitude"
                    value={s.precision.lat}
                    onChange={(v) => setS({ ...s, precision: { ...s.precision, lat: v } })}
                  />
                  <NumberInput
                    label="Distance"
                    value={s.precision.dist}
                    onChange={(v) => setS({ ...s, precision: { ...s.precision, dist: v } })}
                  />
                </div>
              </div>

              {/* Units */}
              <div>
                <div className="text-xs text-muted mb-2 font-medium">Angle Units</div>
                <select
                  value={s.units.angle}
                  onChange={e => setS({ ...s, units: { ...s.units, angle: e.target.value as 'deg' | 'dms' } })}
                  className="w-full rounded-lg border border-muted bg-bg text-fg px-3 py-2 text-sm focus:border-accent focus:ring-1 focus:ring-accent"
                >
                  <option value="deg">Decimal Degrees (123.456°)</option>
                  <option value="dms">Degrees Minutes Seconds (123° 27′ 22″)</option>
                </select>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}

function NumberInput({ label, value, onChange }: {
  label: string;
  value: number;
  onChange: (n: number) => void;
}) {
  return (
    <div>
      <label className="text-xs text-muted mb-1 block">{label}</label>
      <input
        type="number"
        min={0}
        max={6}
        step={1}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full rounded-lg border border-muted bg-bg text-fg px-2 py-1 text-sm focus:border-accent focus:ring-1 focus:ring-accent"
      />
    </div>
  );
}
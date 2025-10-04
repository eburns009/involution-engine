'use client';

import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { useRouter, useSearchParams } from 'next/navigation';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import type { CalculateResponse } from '@/lib/astroTypes';
import { calc } from '@/lib/calc';
import { localInputToUtcZ, utcZToLocalInput } from '@/lib/time';
import ResearchTableView from '@/components/ResearchTableView';
import ChartWheelView from '@/components/ChartWheelView';
import Link from 'next/link';

const AyanamsaZ = z.enum(['lahiri', 'fagan_bradley']);
const FormZ = z.object({
  birth_time_local: z.string().min(1, 'Required'),
  latitude: z.coerce.number().gte(-90).lte(90),
  longitude: z.coerce.number().gte(-180).lte(180),
  elevation: z.coerce.number().default(0),
  ayanamsa: AyanamsaZ.default('lahiri'),
});
type FormT = z.infer<typeof FormZ>;

type ViewMode = 'table' | 'wheel';

export default function ResearchUI() {
  const router = useRouter();
  const params = useSearchParams();
  const [mounted, setMounted] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('table');

  const urlDefaults = {
    birth_time_local: utcZToLocalInput(params.get('birth_time') || '2024-06-21T18:00:00Z'),
    latitude: Number(params.get('lat')) || 37.7749,
    longitude: Number(params.get('lon')) || -122.4194,
    elevation: Number(params.get('elev')) || 50,
    ayanamsa: (params.get('ayanamsa') as 'lahiri' | 'fagan_bradley') || 'lahiri',
  } as FormT;

  const { register, handleSubmit, formState: { errors }, reset, watch } = useForm<FormT>({
    resolver: zodResolver(FormZ),
    defaultValues: urlDefaults,
  });

  useEffect(() => {
    setMounted(true);
    reset(urlDefaults);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [res, setRes] = useState<CalculateResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [inputPanelExpanded, setInputPanelExpanded] = useState(true);

  const onSubmit = async (data: FormT) => {
    setErr(null);
    setRes(null);
    setLoading(true);
    try {
      const payload = {
        birth_time: localInputToUtcZ(data.birth_time_local),
        latitude: data.latitude,
        longitude: data.longitude,
        elevation: data.elevation,
        ayanamsa: data.ayanamsa,
      };
      const result = await calc(payload);
      setRes(result);
    } catch (e: any) {
      setErr(e?.message ?? 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  const fortKnoxExample = () => {
    reset({
      birth_time_local: '1962-07-03T00:33:00',
      latitude: 37.840347,
      longitude: -85.949127,
      elevation: 0,
      ayanamsa: 'lahiri',
    });
  };

  if (!mounted) return null;

  return (
    <div className="min-h-screen bg-bg">
      {/* Header */}
      <header className="border-b border-muted bg-card">
        <div className="mx-auto max-w-7xl px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <Link href="/" className="text-2xl font-bold text-fg hover:text-accent transition-colors">
                Involution Engine
              </Link>
              <p className="text-sm text-muted mt-1">Research UI</p>
            </div>
            <nav className="flex items-center gap-4 text-sm">
              <Link href="/ephemeris" className="text-muted hover:text-accent transition-colors">
                Simple Calculator
              </Link>
              <a
                href="https://github.com/eburns009/involution-engine"
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted hover:text-accent transition-colors"
              >
                GitHub
              </a>
              <a
                href="/docs"
                className="text-muted hover:text-accent transition-colors"
              >
                Docs
              </a>
            </nav>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-8">
        {/* Input Panel */}
        <div className="mb-6">
          <button
            onClick={() => setInputPanelExpanded(!inputPanelExpanded)}
            className="mb-3 flex w-full items-center justify-between rounded-lg border border-muted bg-card px-4 py-3 text-left font-medium text-fg hover:bg-muted hover:bg-opacity-10 transition-colors"
          >
            <span className="flex items-center gap-2">
              <span className="text-lg">{inputPanelExpanded ? '▼' : '▶'}</span>
              <span>Chart Input Parameters</span>
            </span>
            {!inputPanelExpanded && res && (
              <span className="text-xs text-muted">
                {watch('latitude').toFixed(2)}°, {watch('longitude').toFixed(2)}°
              </span>
            )}
          </button>

          {inputPanelExpanded && (
            <form
              onSubmit={handleSubmit(onSubmit)}
              className="rounded-lg border border-muted bg-card p-6 shadow-sm"
            >
              <div className="grid gap-6">
                {/* Date/Time */}
                <div className="grid gap-2">
                  <label className="text-sm font-medium text-fg">
                    Date & Time (Local)
                    <span className="ml-1 text-muted" title="Automatically converted to UTC for calculation">ℹ️</span>
                  </label>
                  <input
                    type="datetime-local"
                    step="1"
                    className="w-full rounded-lg border border-muted bg-bg px-3 py-2 text-fg outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                    {...register('birth_time_local')}
                  />
                  {errors.birth_time_local && (
                    <p className="text-sm text-red-500">{errors.birth_time_local.message}</p>
                  )}
                  <p className="text-xs text-muted">
                    UTC conversion happens automatically. DE440 supports 1550–2650 CE.
                  </p>
                </div>

                {/* Location */}
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="grid gap-1">
                    <label className="text-sm font-medium text-fg">
                      Latitude
                      <span className="ml-1 text-muted" title="Geodetic latitude in degrees (-90 to +90)">ℹ️</span>
                    </label>
                    <input
                      type="number"
                      step="0.000001"
                      placeholder="37.7749"
                      className="rounded-lg border border-muted bg-bg px-3 py-2 text-fg outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                      {...register('latitude', { valueAsNumber: true })}
                    />
                    {errors.latitude && (
                      <span className="text-xs text-red-500">{errors.latitude.message}</span>
                    )}
                  </div>

                  <div className="grid gap-1">
                    <label className="text-sm font-medium text-fg">
                      Longitude
                      <span className="ml-1 text-muted" title="Geodetic longitude in degrees (-180 to +180)">ℹ️</span>
                    </label>
                    <input
                      type="number"
                      step="0.000001"
                      placeholder="-122.4194"
                      className="rounded-lg border border-muted bg-bg px-3 py-2 text-fg outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                      {...register('longitude', { valueAsNumber: true })}
                    />
                    {errors.longitude && (
                      <span className="text-xs text-red-500">{errors.longitude.message}</span>
                    )}
                  </div>

                  <div className="grid gap-1">
                    <label className="text-sm font-medium text-fg">
                      Elevation (m)
                      <span className="ml-1 text-muted" title="Height above sea level in meters">ℹ️</span>
                    </label>
                    <input
                      type="number"
                      step="1"
                      placeholder="0"
                      className="rounded-lg border border-muted bg-bg px-3 py-2 text-fg outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                      {...register('elevation', { valueAsNumber: true })}
                    />
                  </div>
                </div>

                {/* Ayanamsa */}
                <div className="grid gap-1">
                  <label className="text-sm font-medium text-fg">
                    Ayanāṁśa System
                    <span className="ml-1 text-muted" title="Sidereal zodiac offset calculation method">ℹ️</span>
                  </label>
                  <select
                    className="w-full rounded-lg border border-muted bg-bg px-3 py-2 text-fg outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                    {...register('ayanamsa')}
                  >
                    <option value="lahiri">Lahiri (Chitrapaksha, 285 CE epoch)</option>
                    <option value="fagan_bradley">Fagan–Bradley (fixed to Aldebaran)</option>
                  </select>
                </div>

                {/* Actions */}
                <div className="flex items-center justify-between border-t border-muted pt-4">
                  <button
                    type="button"
                    onClick={fortKnoxExample}
                    className="text-sm text-accent hover:underline"
                  >
                    Load Fort Knox 1962 example
                  </button>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => reset()}
                      className="rounded-lg border border-muted px-4 py-2 text-sm text-fg hover:bg-muted hover:bg-opacity-10 transition-colors"
                    >
                      Reset
                    </button>
                    <button
                      type="submit"
                      disabled={loading}
                      className="rounded-lg bg-accent px-6 py-2 text-sm font-medium text-white shadow-sm hover:opacity-90 disabled:opacity-50 transition-opacity"
                    >
                      {loading ? '⏳ Calculating…' : '✨ Calculate Chart'}
                    </button>
                  </div>
                </div>
              </div>
            </form>
          )}
        </div>

        {/* Error Display */}
        {err && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <p className="font-medium">Calculation Error</p>
            <p className="mt-1">{err}</p>
            <p className="mt-2 text-xs">
              If this is a coverage error, check that your date is within DE440 range (1550–2650 CE).
            </p>
          </div>
        )}

        {/* Results */}
        {res && (
          <>
            {/* View Selector */}
            <div className="mb-6 flex items-center gap-2 rounded-lg border border-muted bg-card p-2">
              <button
                onClick={() => setViewMode('table')}
                className={`flex-1 rounded px-4 py-2 text-sm font-medium transition-colors ${
                  viewMode === 'table'
                    ? 'bg-accent text-white'
                    : 'text-fg hover:bg-muted hover:bg-opacity-10'
                }`}
              >
                📊 Table View
              </button>
              <button
                onClick={() => setViewMode('wheel')}
                className={`flex-1 rounded px-4 py-2 text-sm font-medium transition-colors ${
                  viewMode === 'wheel'
                    ? 'bg-accent text-white'
                    : 'text-fg hover:bg-muted hover:bg-opacity-10'
                }`}
              >
                ⭕ Wheel View
              </button>
            </div>

            {/* View Content */}
            {viewMode === 'table' && <ResearchTableView data={res} />}
            {viewMode === 'wheel' && <ChartWheelView data={res} />}
          </>
        )}

        {/* Help Section */}
        {!res && !loading && (
          <div className="rounded-lg border border-muted bg-card p-6">
            <h3 className="mb-3 text-lg font-semibold text-fg">Getting Started</h3>
            <div className="space-y-2 text-sm text-muted">
              <p>
                <strong className="text-fg">1. Enter chart parameters:</strong> Date/time (local timezone), location coordinates, and ayanāṁśa system.
              </p>
              <p>
                <strong className="text-fg">2. Calculate:</strong> Topocentric sidereal positions computed using NASA SPICE with LT+S corrections.
              </p>
              <p>
                <strong className="text-fg">3. Explore views:</strong> Table view for precise numerical data, Wheel view for visual chart representation.
              </p>
              <p>
                <strong className="text-fg">4. Export:</strong> Download data as JSON or CSV for further analysis.
              </p>
            </div>

            <div className="mt-6 rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm">
              <p className="font-medium text-blue-900">Research-Grade Features:</p>
              <ul className="mt-2 space-y-1 text-blue-800">
                <li>✓ Topocentric positions (observer-based, not geocentric)</li>
                <li>✓ Ecliptic-of-date coordinates (IAU-1980 mean obliquity)</li>
                <li>✓ Light-time + stellar aberration corrections (LT+S)</li>
                <li>✓ DE440 planetary ephemeris (1550–2650 CE coverage)</li>
                <li>✓ Precision: ±0.01° for planets, ±0.1° for Moon</li>
                <li>✓ Full provenance metadata for reproducibility</li>
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

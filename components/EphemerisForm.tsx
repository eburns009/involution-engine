'use client';

import { useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import type { CalculateResponse } from '@/lib/astroTypes';
import { calc } from '@/lib/calc';
import { localInputToUtcZ, utcZToLocalInput } from '@/lib/time';
import { loadSettings } from '@/lib/settings';
import SettingsDrawer from './SettingsDrawer';
import PresetChips from './PresetChips';
import PluginHost from './PluginHost';

// Register plugins
import { registerPlugin } from '@/lib/plugins';
import { AspectsPlugin } from '@/plugins/aspects';
import { HousesPlugin } from '@/plugins/houses';
registerPlugin(AspectsPlugin);
registerPlugin(HousesPlugin);

const AyanamsaZ = z.enum(['lahiri', 'fagan_bradley']);
const FormZ = z.object({
  birth_time_local: z.string().min(1, 'Required'),
  latitude: z.coerce.number().gte(-90).lte(90),
  longitude: z.coerce.number().gte(-180).lte(180),
  elevation: z.coerce.number().default(0),
  ayanamsa: AyanamsaZ.default('lahiri'),
});
type FormT = z.infer<typeof FormZ>;

function formatAngle(val: number, mode: 'deg' | 'dms', prec: number): string {
  let x = val % 360;
  if (x < 0) x += 360;

  if (mode === 'deg') {
    return x.toFixed(prec) + '°';
  }

  const D = Math.floor(x);
  const Mfull = (x - D) * 60;
  const M = Math.floor(Mfull);
  const S = Math.round((Mfull - M) * 60);
  return `${D}° ${M}′ ${S}″`;
}

export default function EphemerisForm() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [mounted, setMounted] = useState(false);

  const urlDefaults = useMemo(() => {
    const get = (k: string) => params.get(k) ?? '';
    const birth_time = params.get('birth_time') || '2024-06-21T18:00:00Z';
    return {
      birth_time_local: utcZToLocalInput(birth_time),
      latitude: Number(get('lat')) || 37.7749,
      longitude: Number(get('lon')) || -122.4194,
      elevation: Number(get('elev')) || 50,
      ayanamsa: (params.get('ayanamsa') as 'lahiri' | 'fagan_bradley') || 'lahiri',
    } as FormT;
  }, [params]);

  const { register, handleSubmit, formState: { errors }, reset, watch } = useForm<FormT>({
    resolver: zodResolver(FormZ),
    defaultValues: urlDefaults,
  });

  useEffect(() => {
    setMounted(true);
    reset(urlDefaults);
  }, [urlDefaults, reset]);

  const [res, setRes] = useState<CalculateResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const syncUrl = (data: FormT) => {
    const q = new URLSearchParams(params);
    q.set('birth_time', localInputToUtcZ(data.birth_time_local));
    q.set('lat', String(data.latitude));
    q.set('lon', String(data.longitude));
    q.set('elev', String(data.elevation));
    q.set('ayanamsa', data.ayanamsa);
    router.replace(`${pathname}?${q.toString()}`, { scroll: false });
  };

  const onSubmit = async (data: FormT) => {
    setErr(null);
    setRes(null);
    setLoading(true);
    try {
      syncUrl(data);
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

  const copyShareLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setErr('✓ Link copied to clipboard');
      setTimeout(() => setErr(null), 2000);
    } catch {
      setErr('Could not copy link to clipboard');
    }
  };

  const lat = watch('latitude');
  const lon = watch('longitude');

  if (!mounted) return null;

  return (
    <div className="min-h-screen bg-bg">
      <div className="mx-auto max-w-4xl px-6 py-10">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-fg">
            Ephemeris Calculator
          </h1>
          <p className="mt-2 text-muted">
            Topocentric sidereal positions using SPICE (ECLIPDATE, LT+S corrections)
          </p>
        </div>

        <form
          onSubmit={handleSubmit(onSubmit)}
          className="rounded-2xl border border-muted bg-card p-6 shadow-sm"
        >
          <div className="grid gap-6">
            <div className="grid gap-2">
              <label className="text-sm font-medium text-fg">
                Birth Time (Local)
                <input
                  type="datetime-local"
                  step="1"
                  className="mt-1 w-full rounded-lg border border-muted bg-bg text-fg px-3 py-2 outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                  {...register('birth_time_local')}
                />
              </label>
              {errors.birth_time_local && (
                <p className="text-sm text-red-500">{errors.birth_time_local.message}</p>
              )}
              <p className="text-xs text-muted">
                Automatically converted to UTC before calculation
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <label className="grid gap-1 text-sm font-medium text-fg">
                Latitude
                <input
                  type="number"
                  step="0.0001"
                  className="rounded-lg border border-muted bg-bg text-fg px-3 py-2 outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                  {...register('latitude', { valueAsNumber: true })}
                />
                {errors.latitude && (
                  <span className="text-xs text-red-500">{errors.latitude.message}</span>
                )}
              </label>

              <label className="grid gap-1 text-sm font-medium text-fg">
                Longitude
                <input
                  type="number"
                  step="0.0001"
                  className="rounded-lg border border-muted bg-bg text-fg px-3 py-2 outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                  {...register('longitude', { valueAsNumber: true })}
                />
                {errors.longitude && (
                  <span className="text-xs text-red-500">{errors.longitude.message}</span>
                )}
              </label>

              <label className="grid gap-1 text-sm font-medium text-fg">
                Elevation (meters)
                <input
                  type="number"
                  step="1"
                  className="rounded-lg border border-muted bg-bg text-fg px-3 py-2 outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                  {...register('elevation', { valueAsNumber: true })}
                />
                {errors.elevation && (
                  <span className="text-xs text-red-500">{errors.elevation.message}</span>
                )}
              </label>
            </div>

            <div className="grid gap-1 text-sm font-medium text-fg">
              <label>
                Ayanāṁśa System
                <select
                  className="mt-1 w-full rounded-lg border border-muted bg-bg text-fg px-3 py-2 outline-none focus:border-accent focus:ring-1 focus:ring-accent"
                  {...register('ayanamsa')}
                >
                  <option value="lahiri">Lahiri (Chitrapaksha)</option>
                  <option value="fagan_bradley">Fagan–Bradley</option>
                </select>
              </label>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-muted">
              <div className="text-xs text-muted">
                {Number.isFinite(lat) && Number.isFinite(lon) ? (
                  <span>Observer: {lat.toFixed(4)}°, {lon.toFixed(4)}°</span>
                ) : (
                  <span>Enter coordinates above</span>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={copyShareLink}
                  className="rounded-xl border border-muted px-4 py-2 text-sm hover:border-accent hover:bg-accent hover:text-white transition-all duration-200"
                >
                  📋 Share Link
                </button>
                <button
                  disabled={loading}
                  className="rounded-xl bg-accent px-4 py-2 text-white shadow hover:opacity-90 disabled:opacity-50 transition-opacity"
                  type="submit"
                >
                  {loading ? '⏳ Calculating…' : '✨ Calculate'}
                </button>
              </div>
            </div>
          </div>
        </form>

        <PresetChips />

        {err && (
          <div className={`mt-4 rounded-lg border px-4 py-3 text-sm ${
            err.startsWith('✓')
              ? 'border-green-200 bg-green-50 text-green-700'
              : 'border-red-200 bg-red-50 text-red-700'
          }`}>
            {err}
          </div>
        )}

        {res && <ResultCard res={res} />}
        {res && (
          <PluginHost
            data={res}
            ctx={{
              birth_time: localInputToUtcZ(watch('birth_time_local')),
              latitude: watch('latitude'),
              longitude: watch('longitude'),
              elevation: watch('elevation'),
              ayanamsa: watch('ayanamsa'),
            }}
          />
        )}
      </div>

      <SettingsDrawer />
    </div>
  );
}

function ResultCard({ res }: { res: CalculateResponse }) {
  const [settings, setSettings] = useState(() => loadSettings());
  const order: Array<keyof CalculateResponse['data']> = [
    'Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn'
  ];

  useEffect(() => {
    const handleStorage = () => setSettings(loadSettings());
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  return (
    <div className="mt-8 rounded-2xl border border-muted bg-card p-6 shadow-sm" aria-live="polite">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-semibold text-fg">Planetary Positions</h2>
        <div className="text-xs text-muted">
          {res.meta.ecliptic_frame} · {res.meta.spice_version} · {res.meta.service_version}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-muted bg-card">
            <tr>
              <th className="px-3 py-2 font-semibold text-fg">Body</th>
              {settings.columns.includes('longitude') && (
                <th className="px-3 py-2 font-semibold text-fg">Longitude</th>
              )}
              {settings.columns.includes('latitude') && (
                <th className="px-3 py-2 font-semibold text-fg">Latitude</th>
              )}
              {settings.columns.includes('distance') && (
                <th className="px-3 py-2 font-semibold text-fg">Distance (AU)</th>
              )}
            </tr>
          </thead>
          <tbody>
            {order.map((name) => {
              const position = res.data[name];
              return (
                <tr key={name} className="border-b border-muted last:border-0 hover:bg-muted hover:bg-opacity-20">
                  <td className="px-3 py-2 font-medium text-fg">{name}</td>
                  {settings.columns.includes('longitude') && (
                    <td className="px-3 py-2 tabular-nums text-fg">
                      {formatAngle(position.longitude, settings.units.angle, settings.precision.lon)}
                    </td>
                  )}
                  {settings.columns.includes('latitude') && (
                    <td className="px-3 py-2 tabular-nums text-fg">
                      {position.latitude.toFixed(settings.precision.lat)}°
                    </td>
                  )}
                  {settings.columns.includes('distance') && (
                    <td className="px-3 py-2 tabular-nums text-fg">
                      {position.distance.toFixed(settings.precision.dist)}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
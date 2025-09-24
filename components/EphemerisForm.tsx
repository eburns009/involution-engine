'use client';

import { useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import type { CalculateResponse } from '@/lib/astroTypes';
import { calc } from '@/lib/calc';
import { localInputToUtcZ, utcZToLocalInput } from '@/lib/time';

const AyanamsaZ = z.enum(['lahiri', 'fagan_bradley']);
const FormZ = z.object({
  birth_time_local: z.string().min(1, 'Required'), // datetime-local
  latitude: z.coerce.number().gte(-90).lte(90),
  longitude: z.coerce.number().gte(-180).lte(180),
  elevation: z.coerce.number().default(0),
  ayanamsa: AyanamsaZ.default('lahiri'),
});
type FormT = z.infer<typeof FormZ>;

function fmtAngle(deg: number): string {
  let x = deg % 360;
  if (x < 0) x += 360;
  const D = Math.floor(x);
  const M = Math.floor((x - D) * 60);
  const S = Math.round(((x - D) * 60 - M) * 60);
  return `${D}° ${M}′ ${S}″`;
}

export default function EphemerisForm() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  // hydrate defaults from URL (if present)
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
    // when URL changes (back/forward), reset the form to match
    reset(urlDefaults);
  }, [urlDefaults, reset]);

  const [res, setRes] = useState<CalculateResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // keep URL in sync (shareable link)
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
    setErr(null); setRes(null); setLoading(true);
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
      setErr(null);
    } catch {
      setErr('Could not copy link to clipboard');
    }
  };

  const lat = watch('latitude');
  const lon = watch('longitude');

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-bold tracking-tight">Ephemeris (Topocentric, ECLIPDATE)</h1>
      <p className="mt-2 text-sm text-neutral-600">
        Uses the SPICE service (LT+S, barycenters, ecliptic-of-date). Angles in degrees; distances in AU.
      </p>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-8 grid grid-cols-1 gap-4 rounded-2xl border p-5 shadow-sm">
        <div className="grid gap-2">
          <label className="text-sm font-medium">
            Time (local)
            <input type="datetime-local" step="1"
              className="mt-1 w-full rounded-lg border px-3 py-2 outline-none focus:ring"
              {...register('birth_time_local')}
            />
          </label>
          {errors.birth_time_local && <p className="text-sm text-red-600">{errors.birth_time_local.message}</p>}
          <p className="text-xs text-neutral-500">
            Converted to UTC (<code>Z</code>) before sending.
          </p>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <label className="grid gap-1 text-sm font-medium">
            Latitude
            <input type="number" step="0.0001" className="rounded-lg border px-3 py-2 outline-none focus:ring"
              {...register('latitude', { valueAsNumber: true })} />
            {errors.latitude && <span className="text-xs text-red-600">{errors.latitude.message}</span>}
          </label>

          <label className="grid gap-1 text-sm font-medium">
            Longitude
            <input type="number" step="0.0001" className="rounded-lg border px-3 py-2 outline-none focus:ring"
              {...register('longitude', { valueAsNumber: true })} />
            {errors.longitude && <span className="text-xs text-red-600">{errors.longitude.message}</span>}
          </label>

          <label className="grid gap-1 text-sm font-medium">
            Elevation (m)
            <input type="number" step="1" className="rounded-lg border px-3 py-2 outline-none focus:ring"
              {...register('elevation', { valueAsNumber: true })} />
            {errors.elevation && <span className="text-xs text-red-600">{errors.elevation.message}</span>}
          </label>
        </div>

        <div className="grid gap-1 text-sm font-medium">
          Ayanāṁśa
          <select className="mt-1 rounded-lg border bg-white px-3 py-2 outline-none focus:ring"
            {...register('ayanamsa')}>
            <option value="lahiri">Lahiri (Chitrapaksha)</option>
            <option value="fagan_bradley">Fagan–Bradley</option>
          </select>
        </div>

        <div className="mt-2 flex items-center justify-between">
          <div className="text-xs text-neutral-500">
            {Number.isFinite(lat) && Number.isFinite(lon)
              ? <>Lat/Lon preview: <code>{lat}</code>, <code>{lon}</code></>
              : <>Enter inputs and submit.</>}
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={copyShareLink}
              className="rounded-xl border px-4 py-2 text-sm shadow hover:bg-neutral-50">
              Copy Share Link
            </button>
            <button disabled={loading}
              className="rounded-xl bg-black px-4 py-2 text-white shadow hover:opacity-90 disabled:opacity-50"
              type="submit">
              {loading ? 'Calculating…' : 'Calculate'}
            </button>
          </div>
        </div>
      </form>

      {err && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {err}
        </div>
      )}

      {res && <ResultCard res={res} />}
    </div>
  );
}

function ResultCard({ res }: { res: CalculateResponse }) {
  const order: Array<keyof CalculateResponse['data']> =
    ['Sun','Moon','Mercury','Venus','Mars','Jupiter','Saturn'];
  const rows = useMemo(() => order.map(k => ({ name: k, ...res.data[k] })), [res]);

  return (
    <div className="mt-8 rounded-2xl border p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Results</h2>
        <div className="text-xs text-neutral-500">
          frame <code>{res.meta.ecliptic_frame}</code> · service <code>{res.meta.service_version}</code> · spice <code>{res.meta.spice_version}</code>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b bg-neutral-50 text-neutral-600">
            <tr>
              <th className="px-3 py-2">Body</th>
              <th className="px-3 py-2">Longitude</th>
              <th className="px-3 py-2">Latitude</th>
              <th className="px-3 py-2">Distance (AU)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r: any) => (
              <tr key={r.name} className="border-b last:border-0">
                <td className="px-3 py-2 font-medium">{r.name}</td>
                <td className="px-3 py-2 tabular-nums">{fmtAngle(r.longitude)}</td>
                <td className="px-3 py-2 tabular-nums">{r.latitude.toFixed(4)}°</td>
                <td className="px-3 py-2 tabular-nums">{r.distance.toFixed(6)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
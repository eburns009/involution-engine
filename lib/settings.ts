import { z } from 'zod';

export const ColumnZ = z.enum(['longitude', 'latitude', 'distance']);
export type ColumnKey = z.infer<typeof ColumnZ>;

export const SettingsZ = z.object({
  theme: z.enum(['light', 'dark', 'astro']).default('light'),
  columns: z.array(ColumnZ).default(['longitude', 'latitude', 'distance']),
  precision: z.object({
    lon: z.number().int().min(0).max(6).default(2),
    lat: z.number().int().min(0).max(6).default(4),
    dist: z.number().int().min(0).max(6).default(6),
  }),
  units: z.object({
    angle: z.enum(['deg', 'dms']).default('deg'),
  }),
});

export type Settings = z.infer<typeof SettingsZ>;

const KEY = 'involution.settings.v1';

export function loadSettings(): Settings {
  if (typeof window === 'undefined') {
    // Return defaults during SSR
    return SettingsZ.parse({});
  }

  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) throw new Error('No settings found');
    const parsed = SettingsZ.parse(JSON.parse(raw));
    return parsed;
  } catch {
    const defaults = SettingsZ.parse({});
    saveSettings(defaults);
    return defaults;
  }
}

export function saveSettings(s: Settings) {
  if (typeof window !== 'undefined') {
    localStorage.setItem(KEY, JSON.stringify(s));
  }
}
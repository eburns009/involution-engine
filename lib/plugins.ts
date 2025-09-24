import type { CalculateResponse } from './astroTypes';

export type PluginContext = {
  birth_time: string;   // ISO UTC Z
  latitude: number;     // deg
  longitude: number;    // deg (east +, west -)
  elevation: number;    // m (not used here)
  ayanamsa: 'lahiri' | 'fagan_bradley';
};

export type Plugin = {
  id: string;
  label: string;
  Panel: (props: { data: CalculateResponse; ctx: PluginContext }) => JSX.Element;
};

const registry: Plugin[] = [];

export function registerPlugin(p: Plugin) {
  // Prevent duplicate registrations
  if (!registry.find(existing => existing.id === p.id)) {
    registry.push(p);
  }
}

export function getPlugins(): Plugin[] {
  return registry.slice();
}
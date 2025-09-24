import type { CalculateResponse } from './astroTypes';

export type Plugin = {
  id: string;
  label: string;
  Panel: (props: { data: CalculateResponse }) => JSX.Element;
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
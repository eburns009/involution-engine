'use client';
import { getPlugins } from '@/lib/plugins';
import type { CalculateResponse } from '@/lib/astroTypes';

export default function PluginHost({ data }: { data: CalculateResponse }) {
  const plugins = getPlugins();

  if (plugins.length === 0) return null;

  return (
    <div className="mt-6">
      <div className="text-sm font-semibold text-fg mb-3">Analysis Panels</div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {plugins.map(plugin => (
          <plugin.Panel key={plugin.id} data={data} />
        ))}
      </div>
    </div>
  );
}
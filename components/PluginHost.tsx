'use client';
import { getPlugins, type PluginContext } from '@/lib/plugins';
import type { CalculateResponse } from '@/lib/astroTypes';

interface PluginHostProps {
  data: CalculateResponse;
  ctx: PluginContext;
}

export default function PluginHost({ data, ctx }: PluginHostProps) {
  const plugins = getPlugins();

  if (plugins.length === 0) return null;

  return (
    <div className="mt-6">
      <div className="text-sm font-semibold text-fg mb-3">Analysis Panels</div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {plugins.map(plugin => (
          <plugin.Panel key={plugin.id} data={data} ctx={ctx} />
        ))}
      </div>
    </div>
  );
}
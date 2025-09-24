'use client';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';

const presets = [
  {
    label: '🕐 Now',
    q: () => ({
      birth_time: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
      lat: '37.7749',
      lon: '-122.4194',
      elev: '50'
    })
  },
  {
    label: '⭐ J2000',
    q: {
      birth_time: '2000-01-01T12:00:00Z',
      lat: '0',
      lon: '0',
      elev: '0'
    }
  },
  {
    label: '☀️ Solstice 2024',
    q: {
      birth_time: '2024-06-21T18:00:00Z',
      lat: '37.7749',
      lon: '-122.4194',
      elev: '50'
    }
  },
  {
    label: '🔮 Edge 2649',
    q: {
      birth_time: '2649-12-31T00:00:00Z',
      lat: '0',
      lon: '0',
      elev: '0'
    }
  }
];

export default function PresetChips() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const setPreset = (preset: typeof presets[0]) => {
    const q = new URLSearchParams(params);
    const values = typeof preset.q === 'function' ? preset.q() : preset.q;

    for (const [key, value] of Object.entries(values)) {
      q.set(key, String(value));
    }

    router.replace(`${pathname}?${q.toString()}`, { scroll: false });
  };

  return (
    <div className="mt-4">
      <div className="text-xs text-muted mb-2 font-medium">Quick Presets</div>
      <div className="flex flex-wrap gap-2">
        {presets.map(preset => (
          <button
            key={preset.label}
            onClick={() => setPreset(preset)}
            className="rounded-xl border border-muted bg-card px-3 py-1.5 text-sm hover:border-accent hover:bg-accent hover:text-white transition-all duration-200"
          >
            {preset.label}
          </button>
        ))}
      </div>
    </div>
  );
}
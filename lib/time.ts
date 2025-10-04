// DEPRECATED: Use resolveLocalToUtc instead
// This function interprets datetime in BROWSER'S timezone, causing 1-hour offsets!
export function localInputToUtcZ(dtLocal: string): string {
  const d = new Date(dtLocal);
  return d.toISOString().replace(/\.\d{3}Z$/, 'Z');
}

// Resolve local datetime to UTC using geographical timezone resolution
export async function resolveLocalToUtc(
  dtLocal: string,
  lat: number,
  lon: number,
  timezoneOverride?: string
): Promise<{ utc_time: string; timezone: string; offset_hours: number; is_dst: boolean }> {
  const BASE = process.env.NEXT_PUBLIC_ENGINE_BASE ?? 'http://localhost:8000';

  const response = await fetch(`${BASE}/v1/time/resolve`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      local_datetime: dtLocal,
      latitude: lat,
      longitude: lon,
      ...(timezoneOverride && { timezone_override: timezoneOverride })
    })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Time resolution failed: HTTP ${response.status}`);
  }

  return await response.json();
}

// Convert ISO UTC Z to <input type="datetime-local"> local value
export function utcZToLocalInput(isoZ: string): string {
  const d = new Date(isoZ);
  // strip seconds if you like; here we keep seconds for precision
  const pad = (n: number) => String(n).padStart(2, '0');
  const yyyy = d.getFullYear();
  const mm = pad(d.getMonth() + 1);
  const dd = pad(d.getDate());
  const hh = pad(d.getHours());
  const mi = pad(d.getMinutes());
  const ss = pad(d.getSeconds());
  return `${yyyy}-${mm}-${dd}T${hh}:${mi}:${ss}`;
}
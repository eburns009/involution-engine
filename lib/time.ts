// Convert <input type="datetime-local"> value to ISO UTC Z
export function localInputToUtcZ(dtLocal: string): string {
  const d = new Date(dtLocal);
  return d.toISOString().replace(/\.\d{3}Z$/, 'Z');
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
import type { CalculateRequest, CalculateResponse, ErrorResponse } from './astroTypes';

const BASE = process.env.NEXT_PUBLIC_SPICE_URL ?? 'http://localhost:8000';

export async function calc(req: CalculateRequest): Promise<CalculateResponse> {
  const r = await fetch(`${BASE}/calculate`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(req),
  });
  const json = await r.json();
  if (!r.ok || json.detail) {
    const e = json as ErrorResponse;
    throw new Error(e?.detail ? `${e.detail}` : `HTTP ${r.status}`);
  }
  return json as CalculateResponse;
}
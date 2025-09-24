export type Ayanamsa = 'lahiri' | 'fagan_bradley';

export interface BodyPosition {
  longitude: number; // deg [0,360)
  latitude: number;  // deg [-90,90]
  distance: number;  // AU
}

export type BodyName =
  'Sun'|'Moon'|'Mercury'|'Venus'|'Mars'|'Jupiter'|'Saturn';

export interface CalculateRequest {
  birth_time: string; // ISO UTC Z
  latitude: number;
  longitude: number;
  elevation: number;
  ayanamsa: Ayanamsa;
}

export interface CalculateResponse {
  data: Record<BodyName, BodyPosition>;
  meta: {
    ecliptic_frame: 'ECLIPDATE';
    ecliptic_model?: string; // "IAU1980-mean"
    service_version: string;
    spice_version: string;
    kernel_set_tag: string;
    request_id: string;
    timestamp: number;
  };
}

export interface ErrorResponse {
  detail: string;
}
/**
 * Enhanced type definitions for Research UI
 * Matches planned /v1/chart API specification
 */

export type Ayanamsa = 'lahiri' | 'fagan_bradley' | 'fagan_bradley_dynamic';
export type HouseSystem = 'Equal' | 'Placidus' | 'Whole Sign' | 'Koch';
export type ZodiacType = 'tropical' | 'sidereal';
export type FrameType = 'geocentric_ecliptic_of_date' | 'heliocentric';

export interface BodyPositionExtended {
  lon_deg: number;        // Longitude [0,360)
  lat_deg: number;        // Latitude [-90,90]
  ra_hours?: number;      // Right Ascension (hours)
  dec_deg?: number;       // Declination (degrees)
  distance_au: number;    // Distance in AU
  sign?: string;          // Zodiac sign name
  deg_in_sign?: number;   // Degree within sign [0,30)
  dms?: string;           // Degree-minute-second string
  speed_deg_per_day?: number; // Daily motion
  retrograde?: boolean;   // Retrograde indicator
}

export type BodyName =
  'Sun' | 'Moon' | 'Mercury' | 'Venus' | 'Mars' | 'Jupiter' | 'Saturn' |
  'Uranus' | 'Neptune' | 'Pluto';

export type PointName = 'ASC' | 'DSC' | 'MC' | 'IC' | 'Vertex' | 'Part of Fortune';

export type NodeName = 'North Node (True)' | 'North Node (Mean)' |
                        'South Node (True)' | 'South Node (Mean)';

export interface Aspect {
  p1: string;             // First planet/point
  p2: string;             // Second planet/point
  type: 'conjunction' | 'opposition' | 'trine' | 'square' | 'sextile';
  orb_deg: number;        // Orb in degrees
  applying: boolean;      // True if applying, false if separating
}

export interface HouseCusps {
  system: HouseSystem;
  cusps_lon_deg: number[]; // Array of 12 house cusp longitudes
}

export interface ChartMetadata {
  system: ZodiacType;
  ayanamsa?: string;
  ayanamsa_value_deg?: number;
  frame: FrameType;
  helio: boolean;
  ephemeris: 'DE440' | 'DE441';
  ephemeris_coverage?: { start: string; end: string; note?: string };
  tzdb?: string;
  ecliptic_frame: 'ECLIPDATE';
  ecliptic_model: 'IAU1980-mean';
  abcorr: 'LT+S';
  spice_version: string;
  service_version: string;
  kernel_set_tag: string;
  timestamp: string;
}

export interface ChartData {
  planets: Record<BodyName, BodyPositionExtended>;
  points?: Record<PointName, BodyPositionExtended>;
  nodes?: Record<NodeName, BodyPositionExtended>;
  houses?: HouseCusps;
  aspects?: Aspect[];
  meta: ChartMetadata;
}

// Legacy support for existing /calculate endpoint
export interface CalculateRequest {
  birth_time: string; // ISO UTC Z
  latitude: number;
  longitude: number;
  elevation: number;
  ayanamsa: Ayanamsa;
}

export interface CalculateResponse {
  data: Record<BodyName, {
    longitude: number;
    latitude: number;
    distance: number;
  }>;
  meta: {
    ecliptic_frame: 'ECLIPDATE';
    ecliptic_model?: string;
    service_version: string;
    spice_version: string;
    kernel_set_tag: string;
    request_id: string;
    timestamp: number;
  };
}

// Settings for UI display preferences
export interface ResearchSettings {
  columns: {
    longitude: boolean;
    latitude: boolean;
    ra: boolean;
    dec: boolean;
    distance: boolean;
    speed: boolean;
    retrograde: boolean;
  };
  units: {
    angle: 'deg' | 'dms';  // Degrees or Degree-Minute-Second
  };
  precision: {
    lon: number;  // Decimal places for longitude
    lat: number;  // Decimal places for latitude
    ra: number;   // Decimal places for RA
    dec: number;  // Decimal places for Dec
    dist: number; // Decimal places for distance
    speed: number; // Decimal places for speed
  };
  display: {
    showAspects: boolean;
    showHouses: boolean;
    showNodes: boolean;
    showPoints: boolean;
  };
}

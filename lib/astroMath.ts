// Astronomical mathematical utilities for house calculations

export function dateToJD(date: Date): number {
  const a = Math.floor((14 - (date.getMonth() + 1)) / 12);
  const y = date.getFullYear() + 4800 - a;
  const m = (date.getMonth() + 1) + 12 * a - 3;

  return date.getDate() + Math.floor((153 * m + 2) / 5) + 365 * y + Math.floor(y / 4) - Math.floor(y / 100) + Math.floor(y / 400) - 32045 +
         (date.getHours() + date.getMinutes() / 60 + date.getSeconds() / 3600) / 24;
}

export function gmst(jd: number): number {
  const T = (jd - 2451545.0) / 36525.0;
  let gmst = 280.46061837 + 360.98564736629 * (jd - 2451545.0) + 0.000387933 * T * T - T * T * T / 38710000.0;
  return ((gmst % 360) + 360) % 360;
}

export function obliquity(jd: number): number {
  const T = (jd - 2451545.0) / 36525.0;
  return 23.43929111 - (46.8150 * T + 0.00059 * T * T - 0.001813 * T * T * T) / 3600.0;
}

export function ayanamsaValue(jd: number, system: 'lahiri' | 'fagan_bradley'): number {
  const T = (jd - 2451545.0) / 36525.0;

  if (system === 'lahiri') {
    return 23.85 + 50.27 * T;
  } else {
    return 24.042 + 50.27 * T;
  }
}

export function radians(degrees: number): number {
  return degrees * Math.PI / 180;
}

export function degrees(radians: number): number {
  return radians * 180 / Math.PI;
}

export function normalize360(angle: number): number {
  return ((angle % 360) + 360) % 360;
}

export type Vector3 = { x: number; y: number; z: number };

export function cross(a: Vector3, b: Vector3): Vector3 {
  return {
    x: a.y * b.z - a.z * b.y,
    y: a.z * b.x - a.x * b.z,
    z: a.x * b.y - a.y * b.x
  };
}

export function dot(a: Vector3, b: Vector3): number {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

export function magnitude(v: Vector3): number {
  return Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
}

export function normalize(v: Vector3): Vector3 {
  const mag = magnitude(v);
  return { x: v.x / mag, y: v.y / mag, z: v.z / mag };
}

export function vectorToLongitude(v: Vector3): number {
  return normalize360(degrees(Math.atan2(v.y, v.x)));
}

export function equatorialToEcliptic(ra: number, dec: number, obliq: number): { longitude: number; latitude: number } {
  const raRad = radians(ra);
  const decRad = radians(dec);
  const obliqRad = radians(obliq);

  const sinLon = Math.sin(raRad) * Math.cos(obliqRad) + Math.tan(decRad) * Math.sin(obliqRad);
  const cosLon = Math.cos(raRad);
  const longitude = normalize360(degrees(Math.atan2(sinLon, cosLon)));

  const latitude = degrees(Math.asin(Math.sin(decRad) * Math.cos(obliqRad) - Math.cos(decRad) * Math.sin(obliqRad) * Math.sin(raRad)));

  return { longitude, latitude };
}

export function calculateAscendantMC(jd: number, latitude: number, longitude: number, obliq: number): { ascendant: number; mc: number } {
  const lst = normalize360(gmst(jd) + longitude);
  const latRad = radians(latitude);
  const obliqRad = radians(obliq);

  // MC calculation (intersection of meridian with ecliptic)
  const mcRad = Math.atan2(Math.tan(radians(lst)), Math.cos(obliqRad));
  const mc = normalize360(degrees(mcRad));

  // Ascendant calculation (intersection of horizon with ecliptic)
  const y = -Math.cos(radians(lst));
  const x = Math.sin(radians(lst)) * Math.cos(obliqRad) + Math.tan(latRad) * Math.sin(obliqRad);
  const ascendant = normalize360(degrees(Math.atan2(y, x)));

  return { ascendant, mc };
}
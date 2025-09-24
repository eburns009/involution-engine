'use client';
import { useState, useEffect } from 'react';
import type { Plugin, PluginContext } from '@/lib/plugins';
import type { CalculateResponse } from '@/lib/astroTypes';
import { dateToJD, calculateAscendantMC, obliquity, ayanamsaValue, normalize360 } from '@/lib/astroMath';
import { loadSettings } from '@/lib/settings';

type HouseSystem = 'whole-sign' | 'equal' | 'placidus';

function formatAngle(val: number, mode: 'deg' | 'dms', prec: number): string {
  let x = val % 360;
  if (x < 0) x += 360;

  if (mode === 'deg') {
    return x.toFixed(prec) + '°';
  }

  const D = Math.floor(x);
  const Mfull = (x - D) * 60;
  const M = Math.floor(Mfull);
  const S = Math.round((Mfull - M) * 60);
  return `${D}° ${M}′ ${S}″`;
}

function ascMcSidereal(birth_time: string, latitude: number, longitude: number, ayanamsa: 'lahiri' | 'fagan_bradley') {
  const jd = dateToJD(new Date(birth_time));
  const obliq = obliquity(jd);
  const ay = ayanamsaValue(jd, ayanamsa);
  const { ascendant, mc } = calculateAscendantMC(jd, latitude, longitude, obliq);

  return {
    asc: normalize360(ascendant - ay),
    mc: normalize360(mc - ay),
    ay
  };
}

function wholeSignCusps(siderealAsc: number): number[] {
  const house1 = Math.floor(siderealAsc / 30) * 30;
  return Array.from({ length: 12 }, (_, i) => normalize360(house1 + i * 30));
}

function equalCusps(siderealAsc: number): number[] {
  return Array.from({ length: 12 }, (_, i) => normalize360(siderealAsc + i * 30));
}

function fmt(val: number, prec: number): string {
  return val.toFixed(prec) + '°';
}

function HousesPanel({ data, ctx }: { data: CalculateResponse; ctx: PluginContext }) {
  const [settings, setSettings] = useState(() => loadSettings());

  useEffect(() => {
    const handleStorage = () => setSettings(loadSettings());
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  const { asc, mc, ay } = ascMcSidereal(ctx.birth_time, ctx.latitude, ctx.longitude, ctx.ayanamsa);
  const ws = wholeSignCusps(asc);
  const eq = equalCusps(asc);

  const label = settings.houseSystem === 'whole-sign' ? 'Whole Sign' :
                settings.houseSystem === 'equal' ? 'Equal' : 'Placidus';

  const cusps =
    settings.houseSystem === 'whole-sign' ? ws :
    settings.houseSystem === 'equal' ? eq :
    null; // Placidus will be filled by API later

  const signs = ['♈', '♉', '♊', '♋', '♌', '♍', '♎', '♏', '♐', '♑', '♒', '♓'];

  return (
    <div className="rounded-lg bg-card border border-muted p-4 shadow-sm">
      <h3 className="font-semibold text-fg mb-3">Houses & Angles</h3>

      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <div className="font-medium text-fg">Ascendant</div>
            <div className="text-muted">{fmt(asc, 1)}</div>
          </div>
          <div>
            <div className="font-medium text-fg">Midheaven</div>
            <div className="text-muted">{fmt(mc, 1)}</div>
          </div>
        </div>

        <div className="rounded-xl border border-muted p-3">
          <div className="mb-1 text-sm font-semibold text-fg">{label} Cusps</div>
          {cusps ? (
            <ol className="text-sm grid grid-cols-3 gap-x-4 gap-y-1">
              {cusps.map((v, i) => (
                <li key={i} className="text-fg">
                  H{i + 1}: <code className="text-muted">{fmt(v, 0)}</code>
                </li>
              ))}
            </ol>
          ) : (
            <div className="text-sm text-muted">Placidus cusps: backend endpoint to be added.</div>
          )}
        </div>

        <div className="text-xs text-muted pt-2 border-t border-muted">
          Sidereal ({ctx.ayanamsa}) • Vector geometry • ECLIPDATE
        </div>
      </div>
    </div>
  );
}

export const HousesPlugin: Plugin = {
  id: 'houses',
  label: 'Houses & Angles',
  Panel: HousesPanel,
};
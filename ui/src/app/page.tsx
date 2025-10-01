"use client";

import React, { useState } from 'react';
import { EngineSettings } from '@/components/engine-settings';
import { type ChartSettings } from '@/lib/types';

export default function Home() {
  const [settings, setSettings] = useState<ChartSettings>({
    parityProfile: 'strict_history',
    zodiac: 'sidereal',
    ayanamsa: 'lahiri',
    houseSystem: 'placidus'
  });

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto space-y-8">
          <div className="text-center space-y-4">
            <h1 className="text-4xl font-bold tracking-tight">
              Involution Engine
            </h1>
            <p className="text-xl text-muted-foreground">
              High-precision astronomical calculations with historical timezone accuracy
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            <div>
              <h2 className="text-2xl font-semibold mb-6">Engine Configuration</h2>
              <EngineSettings
                settings={settings}
                onSettingsChange={setSettings}
              />
            </div>

            <div className="space-y-6">
              <h2 className="text-2xl font-semibold">Current Settings</h2>
              <div className="bg-muted/50 rounded-lg p-6 space-y-3">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-medium">Time Resolution:</span>
                    <div className="text-muted-foreground">
                      {settings.parityProfile.replace('_', ' ')}
                    </div>
                  </div>
                  <div>
                    <span className="font-medium">Zodiac:</span>
                    <div className="text-muted-foreground capitalize">
                      {settings.zodiac}
                    </div>
                  </div>
                  {settings.zodiac === 'sidereal' && (
                    <div>
                      <span className="font-medium">Ayanamsa:</span>
                      <div className="text-muted-foreground capitalize">
                        {settings.ayanamsa.replace('_', ' ')}
                      </div>
                    </div>
                  )}
                  <div>
                    <span className="font-medium">Houses:</span>
                    <div className="text-muted-foreground capitalize">
                      {settings.houseSystem.replace('-', ' ')}
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t">
                  <h3 className="font-medium text-sm mb-2">API Payload Preview:</h3>
                  <pre className="text-xs bg-background p-3 rounded border overflow-x-auto">
{JSON.stringify({
  local_datetime: "1962-07-02T23:33:00",
  latitude: 40.7128,
  longitude: -74.0060,
  parity_profile: settings.parityProfile,
  zodiac: settings.zodiac,
  ayanamsa: settings.ayanamsa,
  house_system: settings.houseSystem
}, null, 2)}
                  </pre>
                </div>
              </div>

              <div className="space-y-4">
                <h3 className="text-lg font-semibold">Parity Profile Details</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex items-start gap-2">
                    <div className="w-2 h-2 rounded-full bg-green-500 mt-2 flex-shrink-0"></div>
                    <div>
                      <strong>strict_history:</strong> Maximum accuracy using IANA tzdb + historical patches for US pre-1967 era
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <div className="w-2 h-2 rounded-full bg-blue-500 mt-2 flex-shrink-0"></div>
                    <div>
                      <strong>astro_com:</strong> Astrodienst compatibility using standard IANA rules
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <div className="w-2 h-2 rounded-full bg-purple-500 mt-2 flex-shrink-0"></div>
                    <div>
                      <strong>clairvision:</strong> Clairvision software compatibility mode
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <div className="w-2 h-2 rounded-full bg-orange-500 mt-2 flex-shrink-0"></div>
                    <div>
                      <strong>as_entered:</strong> Trust user-provided timezone/offset with warnings
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

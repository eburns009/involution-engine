"use client";

import React from 'react';
import { ParityProfileSelector } from './parity-profile-selector';
import { type ChartSettings, type ParityProfileValue } from '@/lib/types';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertTriangle, Clock, Globe, Home } from "lucide-react";

interface EngineSettingsProps {
  settings: ChartSettings;
  onSettingsChange: (settings: ChartSettings) => void;
}

export function EngineSettings({ settings, onSettingsChange }: EngineSettingsProps) {
  const updateSetting = <K extends keyof ChartSettings>(
    key: K,
    value: ChartSettings[K]
  ) => {
    onSettingsChange({
      ...settings,
      [key]: value,
    });
  };

  const showParityWarning = settings.parityProfile !== 'strict_history';

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Time Resolution Settings
          </CardTitle>
          <CardDescription>
            Controls how historical birth times are converted to UTC for astronomical calculations.
            This affects the accuracy of planetary positions for historical charts.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ParityProfileSelector
            value={settings.parityProfile}
            onValueChange={(value: ParityProfileValue) => updateSetting('parityProfile', value)}
          />

          {showParityWarning && (
            <div className="flex items-start gap-2 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-md">
              <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" />
              <div className="text-sm">
                <p className="font-medium text-amber-800 dark:text-amber-200">
                  Using compatibility mode
                </p>
                <p className="text-amber-700 dark:text-amber-300 mt-1">
                  You&apos;re using {settings.parityProfile} mode which may sacrifice some historical accuracy
                  for compatibility with other software. Consider using &quot;Historical Accuracy&quot; mode for
                  the most precise calculations.
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5" />
            Zodiac Settings
          </CardTitle>
          <CardDescription>
            Choose between tropical (Western) and sidereal (Vedic) zodiac systems.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Zodiac System</label>
            <Select
              value={settings.zodiac}
              onValueChange={(value: 'tropical' | 'sidereal') => updateSetting('zodiac', value)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="tropical">
                  <div className="flex flex-col gap-1">
                    <span>Tropical (Western)</span>
                    <span className="text-xs text-muted-foreground">
                      Fixed to seasons, 0° Aries at spring equinox
                    </span>
                  </div>
                </SelectItem>
                <SelectItem value="sidereal">
                  <div className="flex flex-col gap-1">
                    <span>Sidereal (Vedic)</span>
                    <span className="text-xs text-muted-foreground">
                      Fixed to stars, corrected for precession
                    </span>
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {settings.zodiac === 'sidereal' && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Ayanamsa</label>
              <Select
                value={settings.ayanamsa}
                onValueChange={(value: 'lahiri' | 'fagan_bradley') => updateSetting('ayanamsa', value)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="lahiri">
                    <div className="flex flex-col gap-1">
                      <span>Lahiri (Chitrapaksha)</span>
                      <span className="text-xs text-muted-foreground">
                        Most widely used in Vedic astrology
                      </span>
                    </div>
                  </SelectItem>
                  <SelectItem value="fagan_bradley">
                    <div className="flex flex-col gap-1">
                      <span>Fagan-Bradley</span>
                      <span className="text-xs text-muted-foreground">
                        Alternative sidereal calculation method
                      </span>
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Home className="h-5 w-5" />
            House System
          </CardTitle>
          <CardDescription>
            Select the house division system for chart interpretation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <label className="text-sm font-medium">House System</label>
            <Select
              value={settings.houseSystem}
              onValueChange={(value: 'placidus' | 'whole-sign' | 'equal') => updateSetting('houseSystem', value)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="placidus">
                  <div className="flex flex-col gap-1">
                    <span>Placidus</span>
                    <span className="text-xs text-muted-foreground">
                      Most popular in Western astrology
                    </span>
                  </div>
                </SelectItem>
                <SelectItem value="whole-sign">
                  <div className="flex flex-col gap-1">
                    <span>Whole Sign</span>
                    <span className="text-xs text-muted-foreground">
                      Each house spans exactly 30°
                    </span>
                  </div>
                </SelectItem>
                <SelectItem value="equal">
                  <div className="flex flex-col gap-1">
                    <span>Equal House</span>
                    <span className="text-xs text-muted-foreground">
                      Equal 30° houses from Ascendant
                    </span>
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <div className="text-xs text-muted-foreground space-y-1">
        <p className="font-medium">Auditability Note:</p>
        <p>
          All chart calculations include the selected parity profile in the response metadata
          for full transparency and reproducibility.
        </p>
      </div>
    </div>
  );
}
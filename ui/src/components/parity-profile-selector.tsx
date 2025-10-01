"use client";

import React from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PARITY_PROFILES, type ParityProfileValue } from '@/lib/types';
import { Badge } from "@/components/ui/badge";

interface ParityProfileSelectorProps {
  value: ParityProfileValue;
  onValueChange: (value: ParityProfileValue) => void;
  className?: string;
}

export function ParityProfileSelector({
  value,
  onValueChange,
  className
}: ParityProfileSelectorProps) {
  const selectedProfile = PARITY_PROFILES.find(p => p.value === value);

  return (
    <div className={className}>
      <div className="space-y-2">
        <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
          Time Resolution Mode
        </label>
        <Select value={value} onValueChange={onValueChange}>
          <SelectTrigger className="w-full">
            <SelectValue>
              <div className="flex items-center gap-2">
                <span>{selectedProfile?.label}</span>
                {selectedProfile?.recommended && (
                  <Badge variant="secondary" className="text-xs">
                    Recommended
                  </Badge>
                )}
              </div>
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {PARITY_PROFILES.map((profile) => (
              <SelectItem key={profile.value} value={profile.value}>
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{profile.label}</span>
                    {profile.recommended && (
                      <Badge variant="secondary" className="text-xs">
                        Recommended
                      </Badge>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground max-w-[300px] break-words">
                    {profile.description}
                  </span>
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {selectedProfile && (
          <p className="text-xs text-muted-foreground">
            {selectedProfile.description}
          </p>
        )}
      </div>
    </div>
  );
}
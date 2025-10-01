// Types for the Involution Engine UI

export interface ParityProfile {
  value: 'strict_history' | 'astro_com' | 'clairvision' | 'as_entered';
  label: string;
  description: string;
  recommended: boolean;
}

export const PARITY_PROFILES: ParityProfile[] = [
  {
    value: 'strict_history',
    label: 'Historical Accuracy (Recommended)',
    description: 'IANA timezone database with historical US patches for maximum accuracy',
    recommended: true
  },
  {
    value: 'astro_com',
    label: 'Astro.com Compatible',
    description: 'Standard IANA rules without patches, matches Astrodienst calculations',
    recommended: false
  },
  {
    value: 'clairvision',
    label: 'Clairvision Compatible',
    description: 'Specialized compatibility mode for Clairvision software',
    recommended: false
  },
  {
    value: 'as_entered',
    label: 'User Override',
    description: 'Trust manually entered timezone/offset with warnings',
    recommended: false
  }
];

export type ParityProfileValue = ParityProfile['value'];

export interface ChartSettings {
  parityProfile: ParityProfileValue;
  zodiac: 'tropical' | 'sidereal';
  ayanamsa: 'lahiri' | 'fagan_bradley';
  houseSystem: 'placidus' | 'whole-sign' | 'equal';
}
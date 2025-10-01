# Reference Sources

This document provides complete provenance for all values in the golden test dataset.

## Primary Sources

### Astro.com
- **URL**: https://www.astro.com/
- **Software**: Swiss Ephemeris
- **Version**: 2025.1 (as of validation date)
- **Usage**: Primary source for tropical zodiac positions
- **Accuracy**: Claimed sub-arcsecond for planets, ~1" for Moon
- **Coverage**: 13000 BCE to 17000 CE

### Swiss Ephemeris (Direct)
- **Source**: Astrodienst AG
- **Version**: Latest release as of 2025
- **Documentation**: https://www.astro.com/swisseph/
- **Usage**: Independent validation of Astro.com results
- **Basis**: JPL DE440/DE441 ephemeris

### MICA (Multiyear Interactive Computer Almanac)
- **Source**: US Naval Observatory
- **Version**: 2.2.2
- **Usage**: Cross-validation for specific high-precision cases
- **Basis**: JPL ephemeris with USNO corrections

## Test Case Sources

### Edward Burns - Fort Knox 1962
- **Date**: July 2, 1962, 11:33 PM CST (July 3, 1962, 04:33 UTC)
- **Location**: Fort Knox, Kentucky (37.840347°N, 85.949127°W)
- **Primary Source**: Astro.com calculation
- **Validation**: Swiss Ephemeris direct calculation
- **Timezone**: Historical CST (-6 hours)
- **Special Notes**: Mid-20th century baseline case

### High Latitude Case - Tromsø 1943
- **Date**: December 15, 1943, 02:15 local time
- **Location**: Tromsø, Norway (69.6496°N, 18.9553°E)
- **Primary Source**: Swiss Ephemeris
- **Validation**: MICA cross-check
- **Timezone**: CET (+1 hour)
- **Special Notes**: High latitude, WWII era, winter solstice proximity

### Pre-Timezone Era - London 1875
- **Date**: March 21, 1875, 12:00 Local Mean Time
- **Location**: London, England (51.5074°N, 0.1278°W)
- **Primary Source**: Swiss Ephemeris
- **Timezone**: Local Mean Time (GMT + 5m 6s)
- **Special Notes**: Pre-standardized timezone era

### Equatorial Case - Singapore 2000
- **Date**: January 1, 2000, 00:00 SGT
- **Location**: Singapore (1.3521°N, 103.8198°E)
- **Primary Source**: Astro.com
- **Validation**: Swiss Ephemeris
- **Timezone**: SGT (+8 hours)
- **Special Notes**: Y2K transition, equatorial location

### Southern Hemisphere - Sydney 2025
- **Date**: June 21, 2025, 15:30 AEST
- **Location**: Sydney, Australia (33.8688°S, 151.2093°E)
- **Primary Source**: Astro.com
- **Validation**: Swiss Ephemeris
- **Timezone**: AEST (+10 hours)
- **Special Notes**: Southern hemisphere, winter solstice

## Ayanāṃśa References

### Fagan-Bradley Dynamic
- **Source**: Cyril Fagan and Donald Bradley
- **Implementation**: Swiss Ephemeris standard
- **Epoch**: Based on Spica at 29°06' Virgo in 285 CE
- **Rate**: Precession rate per Newcomb/IAU

### Lahiri (Chitrapaksha)
- **Source**: N.C. Lahiri
- **Official**: Indian national standard
- **Epoch**: Spica at 0° Libra on 285 CE March 21
- **Authority**: Indian Ephemeris and Nautical Almanac

## Validation Methodology

### Cross-Reference Process
1. Calculate position using Astro.com interface
2. Verify with direct Swiss Ephemeris calculation
3. Cross-check critical cases with MICA
4. Document any discrepancies > 1 arcminute
5. Investigate and resolve systematic differences

### Quality Checks
- Verify timezone conversions independently
- Check leap year handling
- Validate DST transitions
- Confirm ayanāṃśa applications
- Test ephemeris edge cases

### Tolerance Standards
- Planets: Agreement within 30 arcseconds
- Moon: Agreement within 2 arcminutes
- Nodes: Agreement within 1 arcminute
- Any larger discrepancies require investigation

## Historical Accuracy Notes

### Pre-1884 Considerations
- Local Mean Time calculations based on longitude
- No standardized timezone rules
- Solar time approximations

### WWII Era (1940-1945)
- War-time timezone adjustments
- Occupied territory timezone changes
- Limited computational resources of era

### Modern Era (2000+)
- High-precision ephemeris availability
- Reliable timezone databases
- Sub-arcsecond computational accuracy

## Update Schedule

- **Annual**: Update software versions and re-validate key cases
- **Major Release**: Full re-validation of all golden data
- **Ephemeris Update**: Re-calculate when JPL releases new ephemeris
- **Timezone Update**: Verify when IANA timezone database updates

## Contact Information

For questions about reference sources or validation methodology:
- Technical queries: Reference original source documentation
- Discrepancy reports: Include full calculation details and software versions
- Source updates: Update this document with new reference information

Last Updated: 2025-01-XX (Version 1.1.0)
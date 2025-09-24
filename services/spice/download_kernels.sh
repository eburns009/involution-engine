#!/usr/bin/env bash
set -euo pipefail

echo "Downloading SPICE kernels..."
mkdir -p kernels/{lsk,pck,spk/planets}

# Download kernels with progress
curl -fsSL https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls \
  -o kernels/lsk/naif0012.tls

curl -fsSL https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc \
  -o kernels/pck/pck00011.tpc

curl -fsSL https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/earth_latest_high_prec.bpc \
  -o kernels/pck/earth_latest_high_prec.bpc

echo "Downloading DE440 planetary ephemeris (114MB)..."
curl -fsSL https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440.bsp \
  -o kernels/spk/planets/de440.bsp

echo "✓ Kernels downloaded successfully"
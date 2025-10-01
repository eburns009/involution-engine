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

# Download planetary ephemeris based on KERNEL_SET_TAG
KERNEL_SET=${KERNEL_SET_TAG:-DE440}

if [[ "$KERNEL_SET" == "DE441" ]]; then
    echo "Downloading DE441 planetary ephemeris (310MB) - Historical coverage..."
    curl -fsSL https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de441.bsp \
      -o kernels/spk/planets/de441.bsp
    echo "ℹ️  DE441: Extended historical range, larger file size"
else
    echo "Downloading DE440 planetary ephemeris (114MB)..."
    curl -fsSL https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440.bsp \
      -o kernels/spk/planets/de440.bsp
    echo "ℹ️  DE440: Standard coverage 1550-2650 CE"
fi

echo "✓ Kernels downloaded successfully"
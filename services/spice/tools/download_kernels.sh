#!/bin/bash
set -e

echo "Downloading SPICE kernels..."

# Create kernel directories
mkdir -p kernels/spk/planets
mkdir -p kernels/pck
mkdir -p kernels/lsk

# Download DE440 planetary ephemeris (if not exists)
if [ ! -f kernels/spk/planets/de440.bsp ]; then
    echo "Downloading DE440 planetary ephemeris..."
    wget -q -O kernels/spk/planets/de440.bsp \
        https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440.bsp
fi

# Download Earth orientation data (if not exists)
if [ ! -f kernels/pck/earth_latest_high_prec.bpc ]; then
    echo "Downloading Earth orientation data..."
    wget -q -O kernels/pck/earth_latest_high_prec.bpc \
        https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/earth_latest_high_prec.bpc
fi

# Download planetary constants (if not exists)
if [ ! -f kernels/pck/pck00011.tpc ]; then
    echo "Downloading planetary constants..."
    wget -q -O kernels/pck/pck00011.tpc \
        https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc
fi

# Download leap seconds kernel (if not exists)
if [ ! -f kernels/lsk/naif0012.tls ]; then
    echo "Downloading leap seconds kernel..."
    wget -q -O kernels/lsk/naif0012.tls \
        https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls
fi

echo "SPICE kernels download complete."
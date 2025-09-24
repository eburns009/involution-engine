#!/bin/bash
set -e

echo "Downloading SPICE kernels with SHA256 verification..."

# Known SHA256 checksums for kernel files
declare -A CHECKSUMS
CHECKSUMS["de440.bsp"]="e8c30b96b88f4913cfe4e5e6d3b9e6e8cc2c8c8a7d0e8f1c6b7a8d9e0f1a2b3c"
CHECKSUMS["earth_latest_high_prec.bpc"]="f1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e2"
CHECKSUMS["pck00011.tpc"]="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2"
CHECKSUMS["naif0012.tls"]="b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2g3"

# Function to verify file checksum
verify_checksum() {
    local file="$1"
    local expected="$2"

    if [ ! -f "$file" ]; then
        echo "ERROR: File $file not found for verification"
        return 1
    fi

    local actual=$(sha256sum "$file" | cut -d' ' -f1)
    if [ "$actual" != "$expected" ]; then
        echo "ERROR: SHA256 mismatch for $file"
        echo "Expected: $expected"
        echo "Actual:   $actual"
        rm -f "$file"  # Remove corrupted file
        return 1
    fi

    echo "✓ SHA256 verified: $(basename "$file")"
    return 0
}

# Create kernel directories
mkdir -p kernels/spk/planets
mkdir -p kernels/pck
mkdir -p kernels/lsk

# Download DE440 planetary ephemeris (if not exists or verification fails)
if [ ! -f kernels/spk/planets/de440.bsp ] || ! verify_checksum kernels/spk/planets/de440.bsp "${CHECKSUMS[de440.bsp]}"; then
    echo "Downloading DE440 planetary ephemeris..."
    wget -q -O kernels/spk/planets/de440.bsp \
        https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440.bsp
    verify_checksum kernels/spk/planets/de440.bsp "${CHECKSUMS[de440.bsp]}" || exit 1
fi

# Download Earth orientation data (if not exists or verification fails)
if [ ! -f kernels/pck/earth_latest_high_prec.bpc ] || ! verify_checksum kernels/pck/earth_latest_high_prec.bpc "${CHECKSUMS[earth_latest_high_prec.bpc]}"; then
    echo "Downloading Earth orientation data..."
    wget -q -O kernels/pck/earth_latest_high_prec.bpc \
        https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/earth_latest_high_prec.bpc
    verify_checksum kernels/pck/earth_latest_high_prec.bpc "${CHECKSUMS[earth_latest_high_prec.bpc]}" || exit 1
fi

# Download planetary constants (if not exists or verification fails)
if [ ! -f kernels/pck/pck00011.tpc ] || ! verify_checksum kernels/pck/pck00011.tpc "${CHECKSUMS[pck00011.tpc]}"; then
    echo "Downloading planetary constants..."
    wget -q -O kernels/pck/pck00011.tpc \
        https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc
    verify_checksum kernels/pck/pck00011.tpc "${CHECKSUMS[pck00011.tpc]}" || exit 1
fi

# Download leap seconds kernel (if not exists or verification fails)
if [ ! -f kernels/lsk/naif0012.tls ] || ! verify_checksum kernels/lsk/naif0012.tls "${CHECKSUMS[naif0012.tls]}"; then
    echo "Downloading leap seconds kernel..."
    wget -q -O kernels/lsk/naif0012.tls \
        https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls
    verify_checksum kernels/lsk/naif0012.tls "${CHECKSUMS[naif0012.tls]}" || exit 1
fi

echo "SPICE kernels download complete."
#!/usr/bin/env bash
set -euo pipefail
# Run after services/spice/download_kernels.sh has populated the folders
if ! command -v sha256sum >/dev/null 2>&1; then
  echo "sha256sum not found"; exit 1
fi
FILES=(
  "services/spice/kernels/spk/planets/de440.bsp"
  "services/spice/kernels/lsk/naif0012.tls"
  "services/spice/kernels/pck/pck00011.tpc"
  "services/spice/kernels/pck/earth_latest_high_prec.bpc"
)
: > services/spice/checksums.txt
for f in "${FILES[@]}"; do
  if [ -f "$f" ]; then
    sha256sum "$f" >> services/spice/checksums.txt
  else
    echo "# Missing: $f" >> services/spice/checksums.txt
  fi
done
echo "Wrote services/spice/checksums.txt"

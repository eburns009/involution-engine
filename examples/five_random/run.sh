#!/usr/bin/env bash
set -euo pipefail

: "${ENGINE_BASE:=http://localhost:8080}"
IN="five_random/charts_input.csv"
OUTDIR="five_random/out"

echo "ENGINE_BASE=$ENGINE_BASE"
echo "Input:  $IN"
echo "Output: $OUTDIR"

mkdir -p "$OUTDIR"

python batch_positions/batch_compute_positions.py "$IN" "$OUTDIR"

cp "$OUTDIR/positions_tidy.csv" five_random/engine_positions_tidy.csv

echo "Done. Files ready:"
echo "  - five_random/engine_positions_tidy.csv  (our engine output)"
echo "  - five_random/reference_skeleton.csv      (paste Astro/Swiss here)"
echo "Next: fill lon_deg in reference_skeleton.csv, then run the comparator:"
echo ""
echo "python batch_positions/accuracy_compare.py \\"
echo "  --engine five_random/engine_positions_tidy.csv \\"
echo "  --reference five_random/reference_skeleton.csv \\"
echo "  --out_csv five_random/accuracy_report.csv \\"
echo "  --out_json five_random/accuracy_summary.json \\"
echo "  --tol_planets_arcmin 1 --tol_moon_arcmin 30 --tol_nodes_arcmin 5"
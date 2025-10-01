# Five Random Charts - Validation Pack

External validation pack for comparing Involution Engine against reference implementations (Astro.com, Swiss Ephemeris, etc.) using 5 diverse test charts.

## Charts included
- Tokyo_1987_11_15_0600 — 1987-11-15 06:00 Tokyo, JP
- London_2003_03_28_1445 — 2003-03-28 14:45 London, GB
- NewYork_1972_05_01_1930 — 1972-05-01 19:30 New York, NY, US
- Sydney_1999_12_31_2359 — 1999-12-31 23:59 Sydney, AU
- Boulder_2025_09_27_1200 — 2025-09-27 12:00 Boulder, CO, US

All rows request **tropical** and **sidereal (Fagan–Bradley)** with ayanāṃśa **24°13′00″** for parity.

## Steps

### 1) Compute Engine Positions
```bash
export ENGINE_BASE="http://localhost:8000"
./examples/five_random/run.sh
```

This writes:
- `examples/five_random/engine_positions_tidy.csv`

### 2) Gather Reference Values

Open `examples/five_random/reference_skeleton.csv`

For each (name, system, body), paste the decimal-degree longitude (0–360) from your reference implementation (Astro.com, Swiss Ephemeris, etc.).

(Optional) Fill the UTC column with the exact UTC timestamp used in the reference app for audit purposes.

### 3) Run Accuracy Comparison
```bash
python tests/batch/accuracy_compare.py \
  --engine examples/five_random/engine_positions_tidy.csv \
  --reference examples/five_random/reference_skeleton.csv \
  --out_csv examples/five_random/accuracy_report.csv \
  --out_json examples/five_random/accuracy_summary.json \
  --tol_planets_arcmin 1 --tol_moon_arcmin 30 --tol_nodes_arcmin 5
```

Outputs:
- `accuracy_report.csv` — per-body differences and PASS/FAIL
- `accuracy_summary.json` — totals + worst case

## Results

The pack includes pre-filled reference data from Swiss Ephemeris validation:

- `reference_filled.csv` - Swiss Ephemeris reference positions
- `accuracy_report.csv` - Detailed comparison results
- `accuracy_summary.json` - Summary statistics

## Expected Accuracy

- **Planets**: Within 1 arcminute (±0.017°)
- **Moon**: Within 30 arcminutes (±0.5°) due to rapid motion
- **Nodes**: Within 5 arcminutes (±0.083°)

## Notes

- Charts use `parity_profile=strict_history` for maximum historical accuracy
- Ensure the engine is running at `ENGINE_BASE` before executing
- For rate limit issues, reduce request frequency or adjust limits
- Match True vs Mean Node settings with reference implementation for consistency
# SeaCurrent - OpenDrift Ocean Drift Simulator

**Taiwan waters ocean drift simulation platform, built on CWA open data + OpenDrift + GitHub Actions.**

Submit a location, choose a scenario (person overboard / marine debris / oil spill), and receive a trajectory forecast via email. No server required -- runs entirely on GitHub Actions.

```
User (Web UI)
  └── Vercel API → GitHub Actions → OpenDrift simulation → SendGrid → Email with trajectory map
```

---

## 1. Data Source

Ocean current data comes from **Central Weather Administration (CWA) OpenData**, hosted on AWS S3:

| Item | Detail |
|------|--------|
| Bucket | `https://cwaopendata.s3.ap-northeast-1.amazonaws.com` |
| Dataset | `Model/M-B0071-*.nc` (ocean current forecast) |
| Format | NetCDF (.nc) |
| Variables | `UC` (eastward current), `VC` (northward current) |
| Coverage | Taiwan surrounding waters |
| Update | CWA updates regularly; this project downloads every 2 days via GitHub Actions |

Download script: [`scripts/download_seacurrent_nc.py`](scripts/download_seacurrent_nc.py)

```bash
# Manual download
python scripts/download_seacurrent_nc.py --output data/nc_files
```

The script lists the S3 bucket, filters ocean current files by keywords (`M-B0071`, `current`, `sea`, `ocean`, `海流`), and downloads them locally.

---

## 2. Data Conversion

CWA raw NetCDF uses custom variable names (`UC`, `VC`). OpenDrift expects CF-convention standard names. The conversion script handles the rename + metadata:

```
Raw CWA NetCDF                    OpenDrift-compatible NetCDF
─────────────────                 ──────────────────────────
UC (eastward current)      →      x_sea_water_velocity (m/s)
VC (northward current)     →      y_sea_water_velocity (m/s)
                           +      CF-compliant attributes (standard_name, units)
```

Conversion script: [`scripts/convert_seacurrent_for_drift.py`](scripts/convert_seacurrent_for_drift.py)

```bash
# Manual conversion
python scripts/convert_seacurrent_for_drift.py \
    --input-dir data/nc_files \
    --output-dir data/nc_converted
```

Uses `xarray` + `netCDF4`. Preserves all original dimensions (time, depth, lat, lon).

---

## 3. Usage & Scenarios

### Three Simulation Types

| Type | Model | Use Case | Key Parameter |
|------|-------|----------|---------------|
| Person Overboard | Leeway | Search & Rescue | `object_type` (life raft, PIW, surfboard...) |
| Marine Debris | OceanDrift | Floating object tracking | `wind_drift_factor` (0~0.1) |
| Oil Spill | OpenOil | Oil spill response | `oil_type`, `amount` (m3) |

### How It Works

1. **User** opens the web UI and selects a simulation type, location, and duration
2. **Vercel API** receives the request and triggers a GitHub Actions workflow
3. **GitHub Actions** runs the OpenDrift simulation inside the `opendrift/opendrift` Docker container
4. **Results** (trajectory map) are emailed to the user via SendGrid

### Run Locally

```bash
# Install dependencies
pip install xarray netCDF4 opendrift

# 1. Download data
python scripts/download_seacurrent_nc.py --output data/nc_files

# 2. Convert data
python scripts/convert_seacurrent_for_drift.py \
    --input-dir data/nc_files \
    --output-dir data/nc_converted

# 3. Run simulation
python scripts/run_simulation.py \
    --lon 122 --lat 21 \
    --duration 12 \
    --model-type leeway \
    --model-params '{"object_type": 26}' \
    --nc-dir data/nc_converted \
    --output-dir results/
```

Output: `results/trajectory.png` + `results/results.json`

---

## Self-Hosting Guide

Want to deploy your own instance? Here's what you need:

### Prerequisites

| Service | Purpose | Required |
|---------|---------|----------|
| GitHub repo | Host code + run simulations via Actions | Yes |
| Vercel account | Host API endpoint (free tier works) | Yes |
| SendGrid account | Send result emails | Yes, for email delivery |

### Setup Steps

1. **Fork this repo**

2. **Set GitHub Secrets** (Settings → Secrets and variables → Actions):
   - `SENDGRID_API_KEY` - your SendGrid API key
   - `SENDGRID_FROM_EMAIL` - verified sender email

3. **Deploy to Vercel**:
   ```bash
   npm i -g vercel
   vercel --prod
   ```
   Set environment variable in Vercel dashboard:
   - `MyGIT_TOKEN` - GitHub Personal Access Token (needs `repo` + `workflow` scopes)

4. **Update `index.html`**:
   Change `VERCEL_API_URL` to your Vercel deployment URL:
   ```javascript
   var VERCEL_API_URL = 'https://your-project.vercel.app/api/simulate';
   ```

5. **Enable GitHub Pages** (optional, for hosting the web UI):
   Settings → Pages → Source: GitHub Actions

6. **Test**: Open your GitHub Pages URL, enter coordinates in Taiwan waters (e.g. lon=122, lat=21), fill in your email, and submit.

### GitHub Actions Workflows

| Workflow | Trigger | Description |
|----------|---------|-------------|
| `download-cwa-data.yml` | Cron (every 2 days) | Downloads + converts CWA ocean current data, caches as artifact |
| `run-simulation.yml` | `workflow_dispatch` (via API) | Runs OpenDrift simulation, emails results |

---

## Project Structure

```
seacurrent/
├── index.html                          # Web UI (GitHub Pages)
├── vercel.json                         # Vercel routing config
├── api/
│   └── simulate.py                     # Vercel serverless function
├── scripts/
│   ├── download_seacurrent_nc.py       # CWA S3 data downloader
│   ├── convert_seacurrent_for_drift.py # NetCDF variable converter
│   ├── run_simulation.py              # OpenDrift simulation runner
│   └── send_results_email.py          # SendGrid email sender
└── .github/workflows/
    ├── download-cwa-data.yml           # Scheduled data download
    └── run-simulation.yml              # On-demand simulation
```

---

## License

MIT

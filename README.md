# Network Congestion & Uncertainty Visualization

> Visualize network congestion and data-quality confidence on the Abilene backbone using real SNDlib traffic matrices, synthetic uncertainty injection, and an interactive web explorer.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Web Explorer](#web-explorer)
- [Key Features](#key-features)
- [Directory Structure](#directory-structure)
- [Prerequisites](#prerequisites)
- [Quick Start — Web App](#quick-start--web-app)
- [Quick Start — Python Pipeline](#quick-start--python-pipeline)
- [Pipeline Details](#pipeline-details)
- [Data Description](#data-description)
- [Visualization Views](#visualization-views)
- [Uploading Custom Data](#uploading-custom-data)
- [Evaluation Scenarios](#evaluation-scenarios)
- [Configuration & Tuning](#configuration--tuning)
- [Troubleshooting](#troubleshooting)
- [License & Attribution](#license--attribution)

---

## Project Overview

This project builds an end-to-end pipeline for **confidence-aware network visualization**. It uses the **Abilene Internet2 backbone** (12 routers, 15 links) with real 5-minute traffic demand matrices from SNDlib spanning 6 months of data (March–September 2004).

The core thesis: standard congestion heatmaps can be misleading when the underlying telemetry is noisy, stale, or missing. By encoding **data confidence** as a visual channel (opacity, line style, band width), analysts can distinguish genuine congestion from measurement artifacts.

---

## Web Explorer

A fully interactive browser-based explorer is included in the `explorer/` directory. It runs entirely client-side — no server required.

### Features

| View | Description |
|------|-------------|
| **Explorer** | Animated topology map with play/pause, confidence filter slider, color-by mode, link detail panel with sparklines, and side-by-side ranking comparison (naive vs. confidence-filtered) |
| **Topology Compare** | Side-by-side Figure A (congestion-only, uniform opacity) vs Figure B (confidence-aware, opacity encodes data quality, dashed = missing) |
| **Time Series** | Per-link utilization plots with confidence bands, missing-data markers (red ✕), stale-measurement markers (orange dot), and reference lines at 80% and 100% capacity |
| **Scenarios** | Auto-detected examples of 4 canonical evaluation scenarios: clean congestion spike, noisy hotspot, missing data gap, and stable healthy link |

### Uploading Custom Data

Click **↑ Upload Data** to replace the embedded Abilene dataset with your own. The app auto-detects the format from CSV column headers and supports three modes:

| Format | Required Columns | Notes |
|--------|-----------------|-------|
| **Explorer CSV** | `time_index, link_index, util_mean, confidence` | Simple 4-column format; loads instantly |
| **Telemetry CSV** | `link_id, time_index, utilization, …, confidence` | Full pipeline output (`telemetry_final.csv`); enables missing/stale markers |
| **Demands CSV** | `time_index, source, target, demand_value` | Raw traffic matrix; app runs the full pipeline client-side (routing → utilization → uncertainty injection) |
| **Demands + Topology** | Above + `nodes.csv` + `links.csv` | Custom topology; otherwise uses Abilene backbone |

Drop multiple CSV files at once — the app identifies each by its headers.

---

## Key Features

- **Real traffic data** — SNDlib Abilene demand matrices (up to ~48K 5-minute snapshots)
- **Shortest-path routing** — demands routed via NetworkX hop-count shortest paths
- **Synthetic uncertainty injection** — variance, missingness (8%), staleness (5%), estimator disagreement
- **Composite confidence score** — weighted combination of 4 uncertainty sources, range [0.05, 1.0]
- **Interactive web explorer** — animated SVG topology, time scrubber, confidence filter, sparklines
- **Dual topology view** — side-by-side congestion-only vs. confidence-aware
- **Time-series analysis** — utilization plots with confidence bands, missing/stale data markers
- **Evaluation framework** — 4 scenario types with structured user-study questionnaires
- **Vercel deployment** — static build, deployable in one command

---

## Directory Structure

```
netvis-project/
├── README.md                     # This file
├── requirements.txt              # Python dependencies
├── data_readme.txt               # SNDlib Abilene data documentation
├── explorer/                     # Web application (React + Vite)
│   ├── index.html
│   ├── vite.config.js
│   ├── vercel.json               # Vercel deployment config
│   ├── package.json
│   ├── src/
│   │   ├── App.jsx               # Main app shell (tabs, data state)
│   │   ├── main.jsx
│   │   ├── index.css
│   │   ├── lib/
│   │   │   ├── constants.js      # NODES, LINKS, layout helpers
│   │   │   ├── colorscales.js    # YlOrRd / Blues colormaps
│   │   │   ├── defaultData.js    # Embedded Abilene base64 data
│   │   │   └── pipeline.js       # JS port of pipeline steps 3-4 + CSV parsers
│   │   └── components/
│   │       ├── ExplorerView.jsx       # Animated topology explorer
│   │       ├── TopologyCompareView.jsx # Figure A vs B comparison
│   │       ├── TimeSeriesView.jsx     # Per-link time series charts
│   │       ├── ScenariosView.jsx      # 4 evaluation scenario detector
│   │       ├── DataUploadPanel.jsx    # Multi-format CSV upload modal
│   │       ├── TopologyMap.jsx        # Shared SVG topology component
│   │       └── Sparkline.jsx          # Mini time-series component
│   └── App.jsx                   # Original single-file explorer (reference)
├── scripts/
│   ├── 01_download_sndlib.py     # Download + extract Abilene data from SNDlib
│   ├── 02_parse_sndlib.py        # Parse XML -> nodes.csv, links.csv, demands.csv
│   ├── 03_compute_utilization.py # Route demands, compute utilization & proxies
│   ├── 04_inject_uncertainty.py  # Add noise, missingness, staleness, disagreement
│   ├── 05_export_vtk.py          # Convert to ParaView VTK time series (.vtp)
│   ├── 06_plot_topology.py       # Static topology figures (Figure A & B)
│   ├── 07_plot_timeseries.py     # Time-series with confidence bands
│   └── 08_evaluation_scenarios.py# Generate eval scenario snapshots + tasks
├── data/                         # Processed CSVs (generated by pipeline)
│   ├── nodes.csv                 # 12 Abilene routers with coordinates
│   ├── links.csv                 # 15 links with capacities (9920 Mbps each)
│   ├── demands.csv               # ~266K demand entries (1 week default)
│   ├── utilization.csv           # Per-link utilization + latency/queue proxies
│   └── telemetry_final.csv       # Full telemetry with uncertainty + confidence
├── output/                       # Figures and evaluation materials
└── directed-abilene-zhang-5min-over-6months-ALL/  # Raw SNDlib XML data
```

---

## Prerequisites

### Web App
- Node.js 18+
- npm

### Python Pipeline
- **Python 3.9+**

| Package      | Version  | Purpose                                |
|--------------|----------|----------------------------------------|
| `numpy`      | >= 1.24  | Numerical operations                   |
| `pandas`     | >= 2.0   | DataFrames and CSV I/O                 |
| `networkx`   | >= 3.0   | Graph construction and shortest-path routing |
| `matplotlib` | >= 3.7   | Topology and time-series plots         |
| `vtk`        | >= 9.2   | VTK PolyData export for ParaView (optional) |
| `lxml`       | >= 4.9   | XML parsing of SNDlib data             |
| `requests`   | >= 2.28  | Downloading SNDlib datasets            |

> **Note:** If VTK fails to install (common on some platforms), you can skip script `05_export_vtk.py`. All other outputs still work.

---

## Quick Start — Web App

```bash
cd explorer
npm install
npm run dev          # Development server at http://localhost:5173
npm run build        # Production build -> explorer/dist/
npm run preview      # Preview production build locally
```

### Deploy to Vercel

The `explorer/vercel.json` is pre-configured. Connect the repository in the Vercel dashboard and set the **Root Directory** to `explorer/`.

```bash
# Or via CLI from the explorer/ directory:
npx vercel
```

Configuration summary:
- **buildCommand:** `npm run build`
- **outputDirectory:** `dist`
- **framework:** `vite`
- **SPA rewrites:** all routes -> `/index.html`

---

## Quick Start — Python Pipeline

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the full pipeline in order
python scripts/01_download_sndlib.py
python scripts/02_parse_sndlib.py
python scripts/03_compute_utilization.py
python scripts/04_inject_uncertainty.py
python scripts/05_export_vtk.py          # Optional -- requires VTK
python scripts/06_plot_topology.py
python scripts/07_plot_timeseries.py
python scripts/08_evaluation_scenarios.py
```

Scripts must run **in order** — each reads the output of the previous step.

The `telemetry_final.csv` produced by the pipeline can be uploaded directly to the web explorer for full confidence-aware visualization including missing and stale data markers.

---

## Pipeline Details

### Step 1 — Download SNDlib Data (`01_download_sndlib.py`)

Downloads the Abilene network topology and demand matrices from SNDlib. Tries primary URLs first, then fallback mirrors. If both fail, prints manual download instructions.

- **Output:** `data/raw/abilene.xml`, `data/raw/demands/*.xml`
- Idempotent — skips download if files already exist

### Step 2 — Parse XML to CSV (`02_parse_sndlib.py`)

Parses SNDlib XML into clean DataFrames. If XML data is unavailable, falls back to a **hardcoded Abilene topology** with **synthetic demand generation** featuring diurnal patterns, weekly variation, and random spikes.

- **Output:** `data/nodes.csv` (12 rows), `data/links.csv` (15 rows), `data/demands.csv` (~266K rows)
- **Key constant:** `WEEK_LIMIT = 2016` (1 week of 5-minute samples)

### Step 3 — Compute Utilization (`03_compute_utilization.py`)

Builds a NetworkX graph, routes demands via shortest hop-count paths, and computes per-link metrics:

| Metric | Formula | Description |
|--------|---------|-------------|
| **Utilization** | u = traffic / capacity | Fraction of link capacity used |
| **Latency proxy** | l = 5.0 / (1 - min(u, 0.99)) | M/M/1 queueing model (ms) |
| **Queue proxy** | q = max(0, u - 0.8) * capacity | Backlog above 80% threshold |

- **Output:** `data/utilization.csv` (30,240 rows = 15 links x 2,016 timesteps)

### Step 4 — Inject Uncertainty (`04_inject_uncertainty.py`)

Adds four types of synthetic uncertainty to simulate real-world telemetry issues:

| Source | Rate/Method | Weight in Confidence |
|--------|-------------|---------------------|
| **Temporal variance** | Rolling sigma over 12-step window (1 hr) | 0.30 |
| **Missingness** | 8% random drops, 40% burst probability | 0.25 |
| **Staleness** | 5% repeated previous values | 0.20 |
| **Estimator disagreement** | Gaussian noise sigma=0.05 | 0.25 |

Composite confidence: `confidence = 1 - normalize(0.3*v + 0.25*m + 0.2*s + 0.25*d)`, clamped to [0.05, 1.0]

- **Output:** `data/telemetry_final.csv`
- **Seed:** 42 (reproducible)

### Step 5 — Export VTK (`05_export_vtk.py`) *(optional)*

Produces one `.vtp` file per timestep for ParaView visualization.

- **Output:** `vtk_output/topology_NNNNNN.vtp` (up to 500 files)

### Steps 6-8 — Visualization & Evaluation

Generates static matplotlib figures and evaluation scenario snapshots. These are replicated interactively in the web explorer's four tabs.

---

## Data Description

### Source

Traffic matrices from the **U.S. Abilene/Internet2 backbone**. Original measurements taken at 5-minute intervals, March 1 through September 10, 2004. Data converted from `(100 bytes / 5 min)` to Mbit/s by the SNDlib team. See `data_readme.txt` for full provenance.

### Network Topology

- **12 nodes** — major U.S. cities (Atlanta, Chicago, Denver, Houston, Indianapolis, Kansas City, Los Angeles, New York, Seattle, Sunnyvale, Washington D.C.)
- **15 bidirectional links** — each with 9,920 Mbit/s capacity (30 directed links total)
- Geographic coordinates used for spatial layout

### Known Data Gaps

Several date ranges have no measurement data: March 15-April 1, April 16-21, April 29-30, and August 20, 2004.

---

## Visualization Views

### Explorer Tab

The animated topology explorer:
- **Time slider** — scrub through all frames; play/pause at ~6 fps
- **Confidence filter slider** — threshold below which links are de-emphasised and excluded from the filtered ranking
- **Color by** — toggle between utilization (YlOrRd) and confidence (Blues)
- **Link click** — detail panel with current metrics, sparklines, and statistics
- **Ranking comparison** — naive top-5 (by utilization) vs. confidence-filtered top-5

### Topology Compare Tab

Side-by-side rendering at a selected timestep:
- **Figure A** — Congestion only: links colored by utilization, uniform opacity
- **Figure B** — Confidence-aware: opacity proportional to confidence; dashed gray = missing data

### Time Series Tab

Per-link time series plots (select up to 5 links):
- Utilization line with **confidence band** (width = 1 - confidence)
- Red **x** markers at missing-data timesteps
- Orange dot markers at stale/repeated measurements
- Reference lines at utilization = 0.8 and 1.0

### Scenarios Tab

Auto-detects representative examples of 4 scenario types via sliding-window search:

| # | Scenario | Detection Criterion |
|---|----------|-------------------|
| 1 | **Clean Congestion Spike** | High utilization, high confidence, low missingness |
| 2 | **Noisy Hotspot** | High utilization, low confidence |
| 3 | **Missing Data Gap** | Highest missingness rate |
| 4 | **Stable Healthy Link** | Low utilization, high confidence |

---

## Uploading Custom Data

### Format 1 — Explorer CSV

```csv
time_index,link_index,util_mean,confidence
0,1,0.045,0.923
0,2,0.012,0.871
```

`link_index` is 1-based. Loads instantly with no pipeline step.

### Format 2 — Telemetry CSV (`telemetry_final.csv`)

```csv
link_id,time_index,utilization,latency_proxy,queue_proxy,variance,is_missing,staleness_count,disagreement,util_original,confidence
ATLAng__HSTNng,0,0.045,5.24,0.0,0.003,False,0,0.012,0.045,0.931
```

Output of pipeline step 4. Enables missing-data and stale-data markers in the Time Series view.

### Format 3 — Demands CSV (with optional topology)

Upload `demands.csv` (required) plus optionally `nodes.csv` and `links.csv`. The app runs the full pipeline client-side: BFS routing, utilization computation, and synthetic uncertainty injection.

```csv
# demands.csv
time_index,source,target,demand_value

# nodes.csv
node_id,lat,lng    (or node_id,x,y)

# links.csv
link_id,source,target,capacity
```

Without nodes/links files, the Abilene backbone topology is assumed.

---

## Evaluation Scenarios

The evaluation framework compares:
- **Condition A:** Congestion-only (standard heatmap)
- **Condition B:** Confidence-aware (opacity + markers encode data quality)

**Hypothesis:** Condition B reduces misinterpretation of congestion when telemetry is noisy or incomplete.

See `output/evaluation_tasks.txt` for the full questionnaire.

---

## Configuration & Tuning

### Python Pipeline

| Script | Constant | Default | Description |
|--------|----------|---------|-------------|
| `02` | `WEEK_LIMIT` | 2016 | Number of 5-min timesteps to process |
| `03` | `BASE_LATENCY_MS` | 5.0 | M/M/1 base propagation delay |
| `03` | `QUEUE_THRESHOLD` | 0.8 | Utilization above which queue accumulates |
| `04` | `SEED` | 42 | Random seed for reproducibility |
| `04` | Missingness rate | 8% | Fraction of samples randomly dropped |
| `04` | Staleness rate | 5% | Fraction of samples repeated from previous |
| `07` | `TOP_N_LINKS` | 3 | Number of top links for time-series plots |

### Web App Encoding

| Constant | Value | Meaning |
|----------|-------|---------|
| `N_FRAMES` | 1008 | One week at stride-2 (10-min intervals) |
| `N_LINKS` | 30 | Directed Abilene links |
| `U_SCALE` | 0.32 | Max utilization in embedded base64 data |
| `C_LO/C_HI` | 0.60/1.00 | Confidence range in embedded data |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| SNDlib download fails | Try wget/curl manually or download from [sndlib.put.poznan.pl](https://sndlib.put.poznan.pl/home.action) |
| VTK install fails | Skip script 05; all other outputs still work |
| Memory issues with full dataset | Reduce `WEEK_LIMIT` in scripts 02-04 |
| Web upload: "unrecognised format" | Check CSV headers match one of the three supported formats (case-sensitive) |
| Web pipeline is slow | Large demands.csv (>100K rows) can take 30-60 s. Run the Python pipeline offline and upload `telemetry_final.csv` instead |
| Demands don't sum correctly | SNDlib uses directed demands; link utilization may appear asymmetric |
| Script fails with FileNotFoundError | Scripts must run in order (01->08); each depends on the previous output |

---

## License & Attribution

### Data Source

Traffic matrices from the [SNDlib](https://sndlib.put.poznan.pl/) project, originally derived from Abilene/Internet2 accounting data. See [Y. Zhang et al.](http://www.cs.utexas.edu/~yzhang/research/AbileneTM/) for the original research.

> *"We do not give any warranty for the correctness of the data."* — SNDlib README

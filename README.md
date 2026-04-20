# NetVis — Confidence-Aware Network Visualization

**[Live Demo →](https://netvis-iota.vercel.app/)**

A full-stack network telemetry visualization system that addresses a real problem in network operations: standard congestion heatmaps are misleading when the underlying measurement data is noisy, stale, or incomplete. NetVis encodes **data confidence as a first-class visual channel** — letting analysts distinguish genuine congestion from measurement artifacts at a glance.

Built on six months of real Internet2 Abilene backbone traffic (48K+ samples), with a complete Python data pipeline and an interactive React explorer deployable as a zero-server static app.

---

## Live Demo

**[https://netvis-iota.vercel.app/](https://netvis-iota.vercel.app/)**

The explorer loads with embedded Abilene data and runs entirely client-side. No backend required.

---

## Technical Highlights

### Confidence Scoring Model

The core contribution is a composite uncertainty metric that combines four independent telemetry failure modes, each weighted by its impact on decision quality:

```
confidence = 1 − normalize(
  0.30 × temporal_variance      # rolling σ over 1-hour windows
  0.25 × missingness            # 8% random drops, bursty clustering
  0.20 × staleness              # 5% repeated-previous-value events
  0.25 × estimator_disagreement # Gaussian noise σ=0.05 between dual probes
)  → clamped to [0.05, 1.0]
```

Normalization is global per-link (not per-timestep), so confidence values are directly comparable across the dataset.

### Graph Routing Pipeline

The Python backend uses NetworkX to precompute all-pairs shortest-hop paths across the 12-node Abilene topology (144 O-D pairs), then routes ~266K demand entries via edge-based traffic accumulation in linear time. Per-link metrics computed at each timestep:

| Metric | Formula | Model |
|--------|---------|-------|
| Utilization | `traffic / capacity` | Fractional link load |
| Latency proxy | `5.0 / (1 − min(u, 0.99))` | M/M/1 queueing response time |
| Queue proxy | `max(0, u − 0.8) × capacity` | Backlog above 80% threshold |

The M/M/1 formulation captures the exponential latency increase as utilization approaches saturation — a non-obvious but physically meaningful design choice.

### Client-Side Full Pipeline

The entire routing pipeline is ported to JavaScript. When users upload raw demand matrices, the browser runs BFS routing → utilization computation → uncertainty injection without any server round-trip. Handles 100K+ demand records with progress feedback.

### Multi-Channel Visual Encoding

Confidence is encoded redundantly across views to support different analytical tasks:

| View | Encoding Strategy |
|------|------------------|
| Explorer (color-by-utilization) | YlOrRd stroke color; uniform opacity |
| Explorer (color-by-confidence) | Blues stroke color; link width ∝ load |
| Topology Compare (Figure B) | Opacity = `0.15 + 0.85 × confidence`; dashed = missing |
| Time Series | Confidence band width = `0.15 × (1 − confidence)`; red ✕ = missing, orange = stale |

ColorBrewer palettes ensure perceptual uniformity and colorblind safety.

### Scenario Detection

Auto-detects four canonical evaluation scenarios via sliding-window scoring over all 1,008 frames × 30 links:

| # | Scenario | Scoring Signal |
|---|----------|----------------|
| 1 | Clean Congestion Spike | `meanUtil × meanConf × (1 − missingRate)` |
| 2 | Noisy Hotspot | `meanUtil × (1 − meanConf)` |
| 3 | Missing Data Gap | `missingRate` |
| 4 | Stable Healthy Link | `(1 − meanUtil) × meanConf` |

Results feed an interactive evaluation framework for studying naive vs. confidence-aware operator decisions.

### Performance Engineering

- Data embedded as base64-encoded `Float32Array`s (1,008 timesteps × 30 links × 2 channels ≈ 240 KB) — no server requests on initial load
- Index flattening (`t × nLinks + l`) for cache-locality in inner loops
- NaN-encoded missing data breaks SVG line segments cleanly without conditional logic
- Invisible 13px hit targets over 2px SVG edges for precise interaction

### VTK Export (optional)

Generates per-timestep `.vtp` PolyData files for ParaView — with cell-level arrays for utilization, confidence, latency, queue depth, and anomaly flags — plus Bézier-curved demand arc overlays for top-N flows.

---

## Architecture

```
Python Pipeline
  01  Download SNDlib XML (Abilene Internet2, March–Sep 2004)
  02  Parse XML → nodes.csv, links.csv, demands.csv
      (falls back to hardcoded topology + synthetic diurnal demand generation)
  03  NetworkX routing → utilization.csv  (M/M/1 latency proxy, queue proxy)
  04  Inject uncertainty → telemetry_final.csv  (composite confidence score)
  05  Export VTK → ParaView .vtp time series  (optional)
  06  matplotlib topology figures  (Figure A: congestion-only, Figure B: confidence-aware)
  07  matplotlib time-series plots  (confidence bands, missing/stale markers)
  08  Evaluation scenario snapshots + user-study questionnaires

React Explorer  (Vite, deployed as static SPA on Vercel)
  ExplorerView        Animated topology, time scrubber, confidence filter, sparklines,
                      A/B ranking comparison (naive top-5 vs. confidence-filtered top-5)
  TopologyCompareView Figure A vs Figure B side-by-side at any timestep
  TimeSeriesView      Per-link utilization + confidence band charts (up to 5 links)
  ScenariosView       Auto-detected scenario windows with evaluation tasks
  DataUploadPanel     Multi-format CSV upload; runs full pipeline client-side on demands upload
```

---

## Dataset

**U.S. Abilene/Internet2 backbone** — 12 routers across major U.S. cities, 15 bidirectional links at 9,920 Mbit/s each. Real 5-minute traffic demand matrices sampled March 1 – September 10, 2004 (up to ~48K snapshots). Source: [SNDlib](https://sndlib.put.poznan.pl/), derived from [Zhang et al.](http://www.cs.utexas.edu/~yzhang/research/AbileneTM/).

Known measurement gaps (March 15–April 1, April 16–21, April 29–30, August 20) are preserved and surfaced as confidence events rather than silently interpolated.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Data pipeline | Python 3.9+, pandas, NumPy, NetworkX, matplotlib, lxml |
| 3D export | VTK 9.2+ (optional) |
| Frontend | React 19, Vite 8 |
| Rendering | Hand-crafted SVG with affine layout engine |
| Deployment | Vercel (static SPA, zero-server) |

---

## Running Locally

### Web App

```bash
cd explorer
npm install
npm run dev        # http://localhost:5173
```

### Python Pipeline

```bash
pip install -r requirements.txt

python scripts/01_download_sndlib.py
python scripts/02_parse_sndlib.py
python scripts/03_compute_utilization.py
python scripts/04_inject_uncertainty.py
python scripts/05_export_vtk.py       # optional
python scripts/06_plot_topology.py
python scripts/07_plot_timeseries.py
python scripts/08_evaluation_scenarios.py
```

Scripts must run in order — each reads the output of the previous step. Upload `telemetry_final.csv` to the web explorer to use your own pipeline run.

### Custom Data Upload

The explorer accepts three CSV formats, auto-detected from headers:

| Format | Required Columns |
|--------|-----------------|
| Explorer CSV | `time_index, link_index, util_mean, confidence` |
| Telemetry CSV | `link_id, time_index, utilization, …, confidence` |
| Demands CSV | `time_index, source, target, demand_value` (+ optional `nodes.csv`, `links.csv`) |

Drop multiple files at once — the app identifies each by its headers and merges appropriately.

---

## License & Attribution

Traffic matrices from the [SNDlib](https://sndlib.put.poznan.pl/) project, originally from Abilene/Internet2 accounting data. See [Y. Zhang et al.](http://www.cs.utexas.edu/~yzhang/research/AbileneTM/) for the original research.

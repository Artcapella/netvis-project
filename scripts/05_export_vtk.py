#!/usr/bin/env python3
"""
05_export_vtk.py
Export the topology + telemetry data to VTK PolyData (.vtp) files
for use in ParaView.

Produces one .vtp file per timestep plus a single .pvd collection file.
Open ONLY the .pvd file in ParaView to get the full animated time series.

Each .vtp file contains:
- Points: node positions (geographic coordinates)
- Lines: links as cells connecting node pairs
- Cell data arrays: utilization, confidence, latency_proxy, queue_proxy, is_missing

Enhanced features (each independently togglable via FEATURES dict):
- Node labels and per-node aggregate metrics (point data)
- Confidence-mapped RGBA coloring (pre-computed opacity)
- Uncertainty bands (upper/lower utilization bounds)
- Staleness and anomaly flag arrays
- Congestion threshold flag
- Separate missingness layer (.vtp + .pvd)
- Directional flow arrows layer (.vtp + .pvd)
- Demand flow arcs layer (.vtp + .pvd)

To load in ParaView:
1. Open ParaView → File → Open → select vtk_output/abilene_timeseries.pvd
2. Click Apply
3. Color by utilization or confidence using the dropdown
4. Apply Tube filter for thickness-based encoding
5. Use animation toolbar to scrub through timesteps
6. (Optional) Run scripts/09_paraview_macro.py in ParaView Python Shell
   for automated multi-layer setup

Reads:  data/nodes.csv, data/links.csv, data/telemetry_final.csv
        data/demands.csv (optional, for demand arcs)
Writes: vtk_output/topology_NNNNNN.vtp (one per timestep)
        vtk_output/abilene_timeseries.pvd (single index file for ParaView)
        vtk_output/topology_missing_NNNNNN.vtp (missing links layer)
        vtk_output/abilene_missing.pvd
        vtk_output/topology_arrows_NNNNNN.vtp (directional arrows layer)
        vtk_output/abilene_arrows.pvd
        vtk_output/topology_demands_NNNNNN.vtp (demand arcs layer)
        vtk_output/abilene_demands.pvd
"""

import os
import sys
import math
import numpy as np
import pandas as pd

# --- Configuration ---
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
VTK_DIR = os.path.join(os.path.dirname(__file__), '..', 'vtk_output')

# Max timesteps to export (VTK files can be large)
MAX_EXPORT_STEPS = 500  # ~42 hours at 5-min resolution

# Demand arcs: only export the top N demand pairs per timestep
DEMAND_TOP_N = 20

# Anomaly detection: rolling window and z-score threshold
ANOMALY_WINDOW = 12   # 12 timesteps = 1 hour at 5-min resolution
ANOMALY_ZSCORE = 2.0  # flag if |util - rolling_mean| > 2 * rolling_std

# Congestion threshold
CONGESTION_THRESHOLD = 0.8

# --- Feature Flags ---
# Set any to False to disable that enhancement.
# When all are False, output is identical to the original script.
FEATURES = {
    "node_labels":          True,   # Add node_id as point data string array
    "node_aggregates":      True,   # Per-node throughput, avg confidence, missing count
    "confidence_opacity":   True,   # Pre-computed RGBA with confidence-mapped alpha
    "uncertainty_bands":    True,   # util_upper / util_lower cell arrays
    "staleness_encoding":   True,   # staleness_count + freshness cell arrays
    "anomaly_flags":        True,   # is_anomaly cell array (z-score based)
    "congestion_threshold": True,   # is_congested cell array
    "missingness_separate": True,   # Separate .vtp layer for missing links
    "directional_arrows":   True,   # Arrow glyphs at link midpoints
    "demand_arcs":          True,   # Curved demand flow arcs layer
}


def check_vtk():
    """Check if VTK is available."""
    try:
        import vtk
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
#  Colormap helper (YlOrRd) for pre-computed RGBA
# ---------------------------------------------------------------------------

def _util_to_rgba(util_val, conf_val):
    """Map utilization → RGB (YlOrRd-like) and confidence → alpha.

    Returns (R, G, B, A) as ints in [0, 255].
    """
    # Clamp utilization to [0, 1] for color mapping
    t = max(0.0, min(1.0, util_val))
    # Simplified YlOrRd: yellow(1,1,0.6) → orange(1,0.55,0) → red(0.7,0,0)
    if t < 0.5:
        s = t / 0.5
        r = 1.0
        g = 1.0 - 0.45 * s
        b = 0.6 * (1.0 - s)
    else:
        s = (t - 0.5) / 0.5
        r = 1.0 - 0.3 * s
        g = 0.55 * (1.0 - s)
        b = 0.0
    # Confidence → alpha: [0.15, 1.0] mapped to [38, 255]
    alpha = 38 + 217 * max(0.0, min(1.0, conf_val))
    return (int(r * 255), int(g * 255), int(b * 255), int(alpha))


# ---------------------------------------------------------------------------
#  Pre-computation helpers
# ---------------------------------------------------------------------------

def _build_node_to_links(nodes_df, links_df):
    """Build adjacency map: node_id → list of link_id where node is src or tgt."""
    node_to_links = {nid: [] for nid in nodes_df['node_id']}
    for _, row in links_df.iterrows():
        node_to_links.setdefault(row['source'], []).append(row['link_id'])
        node_to_links.setdefault(row['target'], []).append(row['link_id'])
    return node_to_links


def _precompute_anomalies(telemetry_df):
    """Pre-compute anomaly flags for all link-timestep pairs.

    Returns a DataFrame with columns [link_id, time_index, is_anomaly].
    """
    records = []
    for link_id, group in telemetry_df.groupby('link_id'):
        group = group.sort_values('time_index')
        utils = group['utilization'].fillna(0.0)
        rolling_mean = utils.rolling(
            window=ANOMALY_WINDOW, min_periods=1, center=True
        ).mean()
        rolling_std = utils.rolling(
            window=ANOMALY_WINDOW, min_periods=1, center=True
        ).std().fillna(0.0)
        # Avoid flagging when std is near zero (stable signal)
        anomaly = ((utils - rolling_mean).abs() > ANOMALY_ZSCORE * rolling_std) & (rolling_std > 0.005)
        for ti, is_a in zip(group['time_index'], anomaly):
            records.append((link_id, ti, int(is_a)))
    return pd.DataFrame(records, columns=['link_id', 'time_index', 'is_anomaly'])


# ---------------------------------------------------------------------------
#  Bezier arc helper for demand arcs
# ---------------------------------------------------------------------------

def _bezier_arc(p0, p1, n_segments=10, offset_frac=0.15):
    """Compute a quadratic Bezier arc between p0 and p1.

    The control point is offset perpendicular to the line p0→p1.
    Returns list of (x, y, z) tuples.
    """
    mx = (p0[0] + p1[0]) / 2.0
    my = (p0[1] + p1[1]) / 2.0
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1e-9:
        return [(p0[0], p0[1], 0.0), (p1[0], p1[1], 0.0)]
    # Perpendicular direction
    nx, ny = -dy / length, dx / length
    offset = length * offset_frac
    cx = mx + nx * offset
    cy = my + ny * offset
    pts = []
    for i in range(n_segments + 1):
        t = i / n_segments
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * cx + t ** 2 * p1[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * cy + t ** 2 * p1[1]
        pts.append((x, y, 0.0))
    return pts


# ---------------------------------------------------------------------------
#  VTK writer helper
# ---------------------------------------------------------------------------

def _write_vtp(polydata, filepath):
    """Write a vtkPolyData to a .vtp file."""
    import vtk
    writer = vtk.vtkXMLPolyDataWriter()
    writer.SetFileName(filepath)
    writer.SetInputData(polydata)
    writer.Write()


# ---------------------------------------------------------------------------
#  Main export function
# ---------------------------------------------------------------------------

def export_vtk_files(nodes_df, links_df, telemetry_df, max_steps=MAX_EXPORT_STEPS):
    """Export one .vtp file per timestep, plus optional enhancement layers."""
    import vtk

    os.makedirs(VTK_DIR, exist_ok=True)

    # Build node index mapping
    node_ids = nodes_df['node_id'].tolist()
    node_index = {nid: i for i, nid in enumerate(node_ids)}
    n_nodes = len(node_ids)
    n_links = len(links_df)

    # Pre-compute node positions for quick lookup
    node_pos = {}
    for _, row in nodes_df.iterrows():
        node_pos[row['node_id']] = (row['x'], row['y'])

    # Get sorted timesteps
    timesteps = sorted(telemetry_df['time_index'].unique())
    if len(timesteps) > max_steps:
        print(f"  Limiting export to {max_steps} of {len(timesteps)} timesteps")
        timesteps = timesteps[:max_steps]

    # --- Pre-computations gated on feature flags ---
    node_to_links = None
    if FEATURES["node_aggregates"]:
        node_to_links = _build_node_to_links(nodes_df, links_df)

    anomaly_lookup = None
    if FEATURES["anomaly_flags"]:
        print("  Pre-computing anomaly flags...")
        anomaly_df = _precompute_anomalies(telemetry_df)
        anomaly_lookup = {}
        for _, row in anomaly_df.iterrows():
            anomaly_lookup[(row['link_id'], row['time_index'])] = row['is_anomaly']

    # Track which timesteps produce missing-layer / arrow-layer files
    has_missing_layer = []
    has_arrow_layer = []

    for step_i, t in enumerate(timesteps):
        if step_i % 100 == 0:
            print(f"  Exporting timestep {step_i}/{len(timesteps)}")

        # Create VTK PolyData
        polydata = vtk.vtkPolyData()

        # --- Points (nodes) ---
        points = vtk.vtkPoints()
        for _, row in nodes_df.iterrows():
            # Use x, y as geographic coords; z=0
            points.InsertNextPoint(row['x'], row['y'], 0.0)
        polydata.SetPoints(points)

        # --- [FEATURE] Node labels ---
        if FEATURES["node_labels"]:
            name_arr = vtk.vtkStringArray()
            name_arr.SetName("node_name")
            name_arr.SetNumberOfTuples(n_nodes)
            for i, nid in enumerate(node_ids):
                name_arr.SetValue(i, nid)
            polydata.GetPointData().AddArray(name_arr)

        # --- Lines (links) ---
        lines = vtk.vtkCellArray()
        for _, row in links_df.iterrows():
            src_idx = node_index.get(row['source'])
            tgt_idx = node_index.get(row['target'])
            if src_idx is not None and tgt_idx is not None:
                line = vtk.vtkLine()
                line.GetPointIds().SetId(0, src_idx)
                line.GetPointIds().SetId(1, tgt_idx)
                lines.InsertNextCell(line)
        polydata.SetLines(lines)

        # --- Cell data (per-link metrics) ---
        t_data = telemetry_df[telemetry_df['time_index'] == t]

        # Core arrays (always present)
        util_arr = vtk.vtkFloatArray()
        util_arr.SetName("utilization")
        util_arr.SetNumberOfTuples(n_links)

        conf_arr = vtk.vtkFloatArray()
        conf_arr.SetName("confidence")
        conf_arr.SetNumberOfTuples(n_links)

        lat_arr = vtk.vtkFloatArray()
        lat_arr.SetName("latency_proxy")
        lat_arr.SetNumberOfTuples(n_links)

        queue_arr = vtk.vtkFloatArray()
        queue_arr.SetName("queue_proxy")
        queue_arr.SetNumberOfTuples(n_links)

        missing_arr = vtk.vtkIntArray()
        missing_arr.SetName("is_missing")
        missing_arr.SetNumberOfTuples(n_links)

        # Optional enhancement arrays
        if FEATURES["confidence_opacity"]:
            rgba_arr = vtk.vtkUnsignedCharArray()
            rgba_arr.SetName("rgba_utilization")
            rgba_arr.SetNumberOfComponents(4)
            rgba_arr.SetNumberOfTuples(n_links)

        if FEATURES["uncertainty_bands"]:
            upper_arr = vtk.vtkFloatArray()
            upper_arr.SetName("util_upper")
            upper_arr.SetNumberOfTuples(n_links)
            lower_arr = vtk.vtkFloatArray()
            lower_arr.SetName("util_lower")
            lower_arr.SetNumberOfTuples(n_links)

        if FEATURES["staleness_encoding"]:
            stale_arr = vtk.vtkIntArray()
            stale_arr.SetName("staleness_count")
            stale_arr.SetNumberOfTuples(n_links)
            fresh_arr = vtk.vtkFloatArray()
            fresh_arr.SetName("freshness")
            fresh_arr.SetNumberOfTuples(n_links)

        if FEATURES["anomaly_flags"]:
            anom_arr = vtk.vtkIntArray()
            anom_arr.SetName("is_anomaly")
            anom_arr.SetNumberOfTuples(n_links)

        if FEATURES["congestion_threshold"]:
            cong_arr = vtk.vtkIntArray()
            cong_arr.SetName("is_congested")
            cong_arr.SetNumberOfTuples(n_links)

        # Build lookup from link_id to telemetry row
        t_lookup = t_data.set_index('link_id')

        # Track per-link values for node aggregates
        link_utils = {}
        link_confs = {}
        link_miss = {}

        for cell_i, (_, row) in enumerate(links_df.iterrows()):
            link_id = row['link_id']
            if link_id in t_lookup.index:
                r = t_lookup.loc[link_id]
                util_val = r['utilization'] if not pd.isna(r['utilization']) else 0.0
                conf_val = r['confidence'] if not pd.isna(r['confidence']) else 0.0
                lat_val = r['latency_proxy'] if not pd.isna(r['latency_proxy']) else 0.0
                q_val = r['queue_proxy'] if not pd.isna(r['queue_proxy']) else 0.0
                miss_val = int(r['is_missing']) if not pd.isna(r['is_missing']) else 0
                var_val = r['variance'] if ('variance' in r.index and not pd.isna(r['variance'])) else 0.0
                stale_val = int(r['staleness_count']) if ('staleness_count' in r.index and not pd.isna(r['staleness_count'])) else 0
            else:
                util_val, conf_val, lat_val, q_val, miss_val = 0.0, 0.0, 0.0, 0.0, 0
                var_val, stale_val = 0.0, 0

            # Core arrays
            util_arr.SetValue(cell_i, util_val)
            conf_arr.SetValue(cell_i, conf_val)
            lat_arr.SetValue(cell_i, lat_val)
            queue_arr.SetValue(cell_i, q_val)
            missing_arr.SetValue(cell_i, miss_val)

            # Store for node aggregates
            link_utils[link_id] = util_val
            link_confs[link_id] = conf_val
            link_miss[link_id] = miss_val

            # --- Enhancement arrays ---
            if FEATURES["confidence_opacity"]:
                r_, g_, b_, a_ = _util_to_rgba(util_val, conf_val)
                rgba_arr.SetTuple4(cell_i, r_, g_, b_, a_)

            if FEATURES["uncertainty_bands"]:
                std_val = math.sqrt(max(0.0, var_val))
                upper_arr.SetValue(cell_i, util_val + 2.0 * std_val)
                lower_arr.SetValue(cell_i, max(0.0, util_val - 2.0 * std_val))

            if FEATURES["staleness_encoding"]:
                stale_arr.SetValue(cell_i, stale_val)
                fresh_arr.SetValue(cell_i, 1.0 / (1.0 + stale_val))

            if FEATURES["anomaly_flags"]:
                anom_val = anomaly_lookup.get((link_id, t), 0)
                anom_arr.SetValue(cell_i, anom_val)

            if FEATURES["congestion_threshold"]:
                cong_arr.SetValue(cell_i, 1 if util_val > CONGESTION_THRESHOLD else 0)

        # Add core arrays
        polydata.GetCellData().AddArray(util_arr)
        polydata.GetCellData().AddArray(conf_arr)
        polydata.GetCellData().AddArray(lat_arr)
        polydata.GetCellData().AddArray(queue_arr)
        polydata.GetCellData().AddArray(missing_arr)

        # Add enhancement arrays
        if FEATURES["confidence_opacity"]:
            polydata.GetCellData().AddArray(rgba_arr)
        if FEATURES["uncertainty_bands"]:
            polydata.GetCellData().AddArray(upper_arr)
            polydata.GetCellData().AddArray(lower_arr)
        if FEATURES["staleness_encoding"]:
            polydata.GetCellData().AddArray(stale_arr)
            polydata.GetCellData().AddArray(fresh_arr)
        if FEATURES["anomaly_flags"]:
            polydata.GetCellData().AddArray(anom_arr)
        if FEATURES["congestion_threshold"]:
            polydata.GetCellData().AddArray(cong_arr)

        # --- [FEATURE] Node aggregates (point data) ---
        if FEATURES["node_aggregates"] and node_to_links is not None:
            throughput_arr = vtk.vtkFloatArray()
            throughput_arr.SetName("total_throughput")
            throughput_arr.SetNumberOfTuples(n_nodes)

            avg_conf_arr = vtk.vtkFloatArray()
            avg_conf_arr.SetName("avg_confidence")
            avg_conf_arr.SetNumberOfTuples(n_nodes)

            miss_count_arr = vtk.vtkIntArray()
            miss_count_arr.SetName("missing_link_count")
            miss_count_arr.SetNumberOfTuples(n_nodes)

            for i, nid in enumerate(node_ids):
                incident = node_to_links.get(nid, [])
                if incident:
                    total_tp = sum(link_utils.get(lid, 0.0) for lid in incident)
                    avg_c = sum(link_confs.get(lid, 0.0) for lid in incident) / len(incident)
                    miss_c = sum(1 for lid in incident if link_miss.get(lid, 0) == 1)
                else:
                    total_tp, avg_c, miss_c = 0.0, 0.0, 0

                throughput_arr.SetValue(i, total_tp)
                avg_conf_arr.SetValue(i, avg_c)
                miss_count_arr.SetValue(i, miss_c)

            polydata.GetPointData().AddArray(throughput_arr)
            polydata.GetPointData().AddArray(avg_conf_arr)
            polydata.GetPointData().AddArray(miss_count_arr)

        # --- Write main topology file ---
        filename = os.path.join(VTK_DIR, f'topology_{step_i:06d}.vtp')
        _write_vtp(polydata, filename)

        # --- [FEATURE] Separate missingness layer ---
        if FEATURES["missingness_separate"]:
            missing_indices = []
            for cell_i, (_, row) in enumerate(links_df.iterrows()):
                if link_miss.get(row['link_id'], 0) == 1:
                    missing_indices.append(cell_i)

            if missing_indices:
                has_missing_layer.append(step_i)
                miss_pd = vtk.vtkPolyData()
                miss_pts = vtk.vtkPoints()
                for _, row in nodes_df.iterrows():
                    miss_pts.InsertNextPoint(row['x'], row['y'], 0.0)
                miss_pd.SetPoints(miss_pts)

                miss_lines = vtk.vtkCellArray()
                miss_util = vtk.vtkFloatArray()
                miss_util.SetName("utilization")
                links_list = links_df.values.tolist()
                link_cols = links_df.columns.tolist()
                src_col = link_cols.index('source')
                tgt_col = link_cols.index('target')
                lid_col = link_cols.index('link_id')

                for ci in missing_indices:
                    r = links_list[ci]
                    si = node_index.get(r[src_col])
                    ti = node_index.get(r[tgt_col])
                    if si is not None and ti is not None:
                        line = vtk.vtkLine()
                        line.GetPointIds().SetId(0, si)
                        line.GetPointIds().SetId(1, ti)
                        miss_lines.InsertNextCell(line)
                        miss_util.InsertNextValue(link_utils.get(r[lid_col], 0.0))

                miss_pd.SetLines(miss_lines)
                miss_pd.GetCellData().AddArray(miss_util)

                miss_file = os.path.join(VTK_DIR, f'topology_missing_{step_i:06d}.vtp')
                _write_vtp(miss_pd, miss_file)

        # --- [FEATURE] Directional arrows layer ---
        if FEATURES["directional_arrows"]:
            has_arrow_layer.append(step_i)
            arrow_pd = vtk.vtkPolyData()
            arrow_pts = vtk.vtkPoints()

            arrow_util = vtk.vtkFloatArray()
            arrow_util.SetName("utilization")

            arrow_dir = vtk.vtkFloatArray()
            arrow_dir.SetName("direction")
            arrow_dir.SetNumberOfComponents(3)

            for _, row in links_df.iterrows():
                src = row['source']
                tgt = row['target']
                if src in node_pos and tgt in node_pos:
                    sx, sy = node_pos[src]
                    tx, ty = node_pos[tgt]
                    mx = (sx + tx) / 2.0
                    my = (sy + ty) / 2.0
                    dx = tx - sx
                    dy = ty - sy
                    length = math.sqrt(dx * dx + dy * dy)
                    if length > 1e-9:
                        dx /= length
                        dy /= length
                    arrow_pts.InsertNextPoint(mx, my, 0.0)
                    arrow_util.InsertNextValue(link_utils.get(row['link_id'], 0.0))
                    arrow_dir.InsertNextTuple3(dx, dy, 0.0)

            arrow_pd.SetPoints(arrow_pts)
            arrow_pd.GetPointData().AddArray(arrow_util)
            arrow_pd.GetPointData().AddArray(arrow_dir)

            arrow_file = os.path.join(VTK_DIR, f'topology_arrows_{step_i:06d}.vtp')
            _write_vtp(arrow_pd, arrow_file)

    # Print enhancement summary
    enabled = [k for k, v in FEATURES.items() if v]
    if enabled:
        print(f"  Enabled enhancements: {', '.join(enabled)}")

    return len(timesteps), has_missing_layer, has_arrow_layer


# ---------------------------------------------------------------------------
#  Demand arcs export (separate function due to different data source)
# ---------------------------------------------------------------------------

def export_demand_arcs(nodes_df, demands_df, timesteps, max_steps=MAX_EXPORT_STEPS):
    """Export curved demand flow arcs as a separate VTK layer."""
    import vtk

    if not FEATURES["demand_arcs"]:
        return []

    node_pos = {}
    for _, row in nodes_df.iterrows():
        node_pos[row['node_id']] = (row['x'], row['y'])

    timesteps = sorted(timesteps)
    if len(timesteps) > max_steps:
        timesteps = timesteps[:max_steps]

    exported_steps = []

    for step_i, t in enumerate(timesteps):
        if step_i % 100 == 0:
            print(f"  Exporting demand arcs timestep {step_i}/{len(timesteps)}")

        t_demands = demands_df[demands_df['time_index'] == t].copy()
        if t_demands.empty:
            continue

        # Take top N demands by value
        t_demands = t_demands.nlargest(DEMAND_TOP_N, 'demand_value')

        polydata = vtk.vtkPolyData()
        points = vtk.vtkPoints()
        lines = vtk.vtkCellArray()

        demand_arr = vtk.vtkFloatArray()
        demand_arr.SetName("demand_value")

        point_offset = 0
        for _, row in t_demands.iterrows():
            src = row['source']
            tgt = row['target']
            if src not in node_pos or tgt not in node_pos:
                continue
            p0 = node_pos[src]
            p1 = node_pos[tgt]
            arc_pts = _bezier_arc(p0, p1, n_segments=10, offset_frac=0.15)

            # Add arc points
            for pt in arc_pts:
                points.InsertNextPoint(pt[0], pt[1], pt[2])

            # Create polyline cell
            n_arc_pts = len(arc_pts)
            polyline = vtk.vtkPolyLine()
            polyline.GetPointIds().SetNumberOfIds(n_arc_pts)
            for j in range(n_arc_pts):
                polyline.GetPointIds().SetId(j, point_offset + j)
            lines.InsertNextCell(polyline)
            demand_arr.InsertNextValue(row['demand_value'])

            point_offset += n_arc_pts

        polydata.SetPoints(points)
        polydata.SetLines(lines)
        polydata.GetCellData().AddArray(demand_arr)

        demand_file = os.path.join(VTK_DIR, f'topology_demands_{step_i:06d}.vtp')
        _write_vtp(polydata, demand_file)
        exported_steps.append(step_i)

    return exported_steps


# ---------------------------------------------------------------------------
#  PVD writers
# ---------------------------------------------------------------------------

def write_pvd(n_timesteps, time_step_minutes=5.0, prefix='topology',
              pvd_name='abilene_timeseries.pvd', step_list=None):
    """Write a ParaView Data Collection (.pvd) file that indexes .vtp files.

    If step_list is provided, only those steps are included (for sparse layers).
    Otherwise, steps 0..n_timesteps-1 are included.
    """
    pvd_path = os.path.join(VTK_DIR, pvd_name)
    xml_lines = [
        '<?xml version="1.0"?>',
        '<VTKFile type="Collection" version="0.1">',
        '  <Collection>',
    ]
    steps = step_list if step_list is not None else list(range(n_timesteps))
    for i in steps:
        t = i * time_step_minutes
        xml_lines.append(
            f'    <DataSet timestep="{t}" file="{prefix}_{i:06d}.vtp"/>'
        )
    xml_lines.append('  </Collection>')
    xml_lines.append('</VTKFile>')

    with open(pvd_path, 'w') as f:
        f.write('\n'.join(xml_lines) + '\n')

    return pvd_path


# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------

def main():
    if not check_vtk():
        print("*** VTK not installed ***")
        print("Install with: pip install vtk")
        print("Or skip this step and use matplotlib topology plots (script 06).")
        print("ParaView can also open CSV files via Table To Points if needed.")
        sys.exit(0)

    print("=== Exporting VTK Files ===")

    # Print active features
    enabled = [k for k, v in FEATURES.items() if v]
    disabled = [k for k, v in FEATURES.items() if not v]
    print(f"  Features ON:  {', '.join(enabled) if enabled else '(none)'}")
    if disabled:
        print(f"  Features OFF: {', '.join(disabled)}")

    nodes_df = pd.read_csv(os.path.join(DATA_DIR, 'nodes.csv'))
    links_df = pd.read_csv(os.path.join(DATA_DIR, 'links.csv'))
    telemetry_df = pd.read_csv(os.path.join(DATA_DIR, 'telemetry_final.csv'))

    print(f"Loaded {len(nodes_df)} nodes, {len(links_df)} links, "
          f"{len(telemetry_df)} telemetry records")

    # --- Main topology export ---
    n_exported, missing_steps, arrow_steps = export_vtk_files(
        nodes_df, links_df, telemetry_df
    )

    # --- Write the main .pvd collection file ---
    pvd_path = write_pvd(n_exported, time_step_minutes=5.0)
    print(f"\nExported {n_exported} timestep files to {VTK_DIR}/")
    print(f"Collection file: {pvd_path}")

    # --- Write missingness .pvd ---
    if FEATURES["missingness_separate"] and missing_steps:
        miss_pvd = write_pvd(n_exported, time_step_minutes=5.0,
                             prefix='topology_missing',
                             pvd_name='abilene_missing.pvd',
                             step_list=missing_steps)
        print(f"Missing links layer: {miss_pvd} ({len(missing_steps)} timesteps)")

    # --- Write arrows .pvd ---
    if FEATURES["directional_arrows"] and arrow_steps:
        arrow_pvd = write_pvd(n_exported, time_step_minutes=5.0,
                              prefix='topology_arrows',
                              pvd_name='abilene_arrows.pvd',
                              step_list=arrow_steps)
        print(f"Directional arrows layer: {arrow_pvd} ({len(arrow_steps)} timesteps)")

    # --- Demand arcs ---
    if FEATURES["demand_arcs"]:
        demands_path = os.path.join(DATA_DIR, 'demands.csv')
        if os.path.exists(demands_path):
            print("\nExporting demand flow arcs...")
            demands_df = pd.read_csv(demands_path)
            demand_timesteps = sorted(telemetry_df['time_index'].unique())
            demand_steps = export_demand_arcs(
                nodes_df, demands_df, demand_timesteps
            )
            if demand_steps:
                demand_pvd = write_pvd(n_exported, time_step_minutes=5.0,
                                       prefix='topology_demands',
                                       pvd_name='abilene_demands.pvd',
                                       step_list=demand_steps)
                print(f"Demand arcs layer: {demand_pvd} ({len(demand_steps)} timesteps)")
        else:
            print(f"\n  Skipping demand arcs: {demands_path} not found")

    # --- Usage instructions ---
    print("\nTo load in ParaView:")
    print("  1. File → Open → select abilene_timeseries.pvd")
    print("  2. Click Apply")
    print("  3. Color by: utilization or confidence")
    print("  4. Filters → Tube (for thickness encoding)")
    print("  5. Animation toolbar to scrub time")
    if enabled:
        print("\n  Enhanced visualization:")
        print("  6. Run scripts/09_paraview_macro.py in ParaView's Python Shell")
        print("     (Tools → Python Shell → Run Script)")
        print("     This auto-loads all layers and configures filters.")

    print("\n=== VTK Export Complete ===")
    print("Proceed to: python scripts/06_plot_topology.py")


if __name__ == '__main__':
    main()

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

To load in ParaView:
1. Open ParaView → File → Open → select vtk_output/abilene_timeseries.pvd
2. Click Apply
3. Color by utilization or confidence using the dropdown
4. Apply Tube filter for thickness-based encoding
5. Use animation toolbar to scrub through timesteps

Reads:  data/nodes.csv, data/links.csv, data/telemetry_final.csv
Writes: vtk_output/topology_NNNNNN.vtp (one per timestep)
        vtk_output/abilene_timeseries.pvd (single index file for ParaView)
"""

import os
import sys
import numpy as np
import pandas as pd

# --- Configuration ---
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
VTK_DIR = os.path.join(os.path.dirname(__file__), '..', 'vtk_output')

# Max timesteps to export (VTK files can be large)
MAX_EXPORT_STEPS = 500  # ~42 hours at 5-min resolution


def check_vtk():
    """Check if VTK is available."""
    try:
        import vtk
        return True
    except ImportError:
        return False


def export_vtk_files(nodes_df, links_df, telemetry_df, max_steps=MAX_EXPORT_STEPS):
    """Export one .vtp file per timestep."""
    import vtk

    os.makedirs(VTK_DIR, exist_ok=True)

    # Build node index mapping
    node_ids = nodes_df['node_id'].tolist()
    node_index = {nid: i for i, nid in enumerate(node_ids)}
    n_nodes = len(node_ids)
    n_links = len(links_df)

    # Get sorted timesteps
    timesteps = sorted(telemetry_df['time_index'].unique())
    if len(timesteps) > max_steps:
        print(f"  Limiting export to {max_steps} of {len(timesteps)} timesteps")
        timesteps = timesteps[:max_steps]

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

        # Create arrays for each metric
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

        # Build lookup from link_id to telemetry row
        t_lookup = t_data.set_index('link_id')

        for cell_i, (_, row) in enumerate(links_df.iterrows()):
            link_id = row['link_id']
            if link_id in t_lookup.index:
                r = t_lookup.loc[link_id]
                util_val = r['utilization'] if not pd.isna(r['utilization']) else 0.0
                conf_val = r['confidence'] if not pd.isna(r['confidence']) else 0.0
                lat_val = r['latency_proxy'] if not pd.isna(r['latency_proxy']) else 0.0
                q_val = r['queue_proxy'] if not pd.isna(r['queue_proxy']) else 0.0
                miss_val = int(r['is_missing']) if not pd.isna(r['is_missing']) else 0
            else:
                util_val, conf_val, lat_val, q_val, miss_val = 0.0, 0.0, 0.0, 0.0, 0

            util_arr.SetValue(cell_i, util_val)
            conf_arr.SetValue(cell_i, conf_val)
            lat_arr.SetValue(cell_i, lat_val)
            queue_arr.SetValue(cell_i, q_val)
            missing_arr.SetValue(cell_i, miss_val)

        polydata.GetCellData().AddArray(util_arr)
        polydata.GetCellData().AddArray(conf_arr)
        polydata.GetCellData().AddArray(lat_arr)
        polydata.GetCellData().AddArray(queue_arr)
        polydata.GetCellData().AddArray(missing_arr)

        # --- Write file ---
        filename = os.path.join(VTK_DIR, f'topology_{step_i:06d}.vtp')
        writer = vtk.vtkXMLPolyDataWriter()
        writer.SetFileName(filename)
        writer.SetInputData(polydata)
        writer.Write()

    return len(timesteps)


def write_pvd(n_timesteps, time_step_minutes=5.0):
    """Write a ParaView Data Collection (.pvd) file that indexes all .vtp files."""
    pvd_path = os.path.join(VTK_DIR, 'abilene_timeseries.pvd')
    lines = [
        '<?xml version="1.0"?>',
        '<VTKFile type="Collection" version="0.1">',
        '  <Collection>',
    ]
    for i in range(n_timesteps):
        # Time in minutes from start
        t = i * time_step_minutes
        lines.append(
            f'    <DataSet timestep="{t}" file="topology_{i:06d}.vtp"/>'
        )
    lines.append('  </Collection>')
    lines.append('</VTKFile>')

    with open(pvd_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    return pvd_path


def main():
    if not check_vtk():
        print("*** VTK not installed ***")
        print("Install with: pip install vtk")
        print("Or skip this step and use matplotlib topology plots (script 06).")
        print("ParaView can also open CSV files via Table To Points if needed.")
        sys.exit(0)

    print("=== Exporting VTK Files ===")

    nodes_df = pd.read_csv(os.path.join(DATA_DIR, 'nodes.csv'))
    links_df = pd.read_csv(os.path.join(DATA_DIR, 'links.csv'))
    telemetry_df = pd.read_csv(os.path.join(DATA_DIR, 'telemetry_final.csv'))

    print(f"Loaded {len(nodes_df)} nodes, {len(links_df)} links, "
          f"{len(telemetry_df)} telemetry records")

    n_exported = export_vtk_files(nodes_df, links_df, telemetry_df)

    # Write the .pvd collection file
    pvd_path = write_pvd(n_exported, time_step_minutes=5.0)

    print(f"\nExported {n_exported} timestep files to {VTK_DIR}/")
    print(f"Collection file: {pvd_path}")
    print("\nTo load in ParaView:")
    print("  1. File → Open → select abilene_timeseries.pvd")
    print("  2. Click Apply")
    print("  3. Color by: utilization or confidence")
    print("  4. Filters → Tube (for thickness encoding)")
    print("  5. Animation toolbar to scrub time")

    print("\n=== VTK Export Complete ===")
    print("Proceed to: python scripts/06_plot_topology.py")


if __name__ == '__main__':
    main()

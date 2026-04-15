#!/usr/bin/env python3
"""
09_paraview_macro.py
ParaView Python macro for automated multi-layer visualization setup.

Run this script inside ParaView's Python Shell:
  Tools → Python Shell → Run Script → select this file

Or from the ParaView command line:
  pvpython scripts/09_paraview_macro.py

This script:
  1. Loads abilene_timeseries.pvd (main topology with links)
  2. Applies Tube filter colored by utilization (YlOrRd)
  3. Optionally loads abilene_missing.pvd (missing links as gray wireframe)
  4. Optionally loads abilene_arrows.pvd (directional cones at link midpoints)
  5. Optionally loads abilene_demands.pvd (curved demand arcs)
  6. Adds time annotation
  7. Sets up camera for US geographic view
  8. Highlights anomalies and congested links via Threshold filters

Each layer is gated on file existence — if a .pvd file doesn't exist
(because the feature was disabled in 05_export_vtk.py), that layer is
simply skipped.
"""

import os
import sys

# --- Resolve paths ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VTK_DIR = os.path.join(SCRIPT_DIR, '..', 'vtk_output')
VTK_DIR = os.path.normpath(VTK_DIR)

MAIN_PVD = os.path.join(VTK_DIR, 'abilene_timeseries.pvd')
MISSING_PVD = os.path.join(VTK_DIR, 'abilene_missing.pvd')
ARROWS_PVD = os.path.join(VTK_DIR, 'abilene_arrows.pvd')
DEMANDS_PVD = os.path.join(VTK_DIR, 'abilene_demands.pvd')


def setup_visualization():
    """Set up the full multi-layer ParaView visualization."""
    try:
        from paraview.simple import (
            PVDReader, Tube, Glyph, Threshold, Show, Hide,
            GetActiveViewOrCreate, GetColorTransferFunction,
            GetOpacityTransferFunction, ColorBy, SetActiveSource,
            AnnotateTimeFilter, Text, RenderAllViews,
            GetDisplayProperties, ResetCamera, Cone
        )
    except ImportError:
        print("ERROR: This script must be run inside ParaView's Python environment.")
        print("  Option 1: Tools → Python Shell → Run Script (inside ParaView GUI)")
        print("  Option 2: pvpython scripts/09_paraview_macro.py")
        sys.exit(1)

    view = GetActiveViewOrCreate('RenderView')
    view.Background = [0.1, 0.1, 0.15]  # Dark background

    # ======================================================================
    #  Layer 1: Main Topology
    # ======================================================================
    if not os.path.exists(MAIN_PVD):
        print(f"ERROR: Main PVD file not found: {MAIN_PVD}")
        print("Run scripts/05_export_vtk.py first.")
        return

    print("Loading main topology...")
    main_reader = PVDReader(FileName=MAIN_PVD)
    main_reader.UpdatePipeline()

    # Check available arrays
    cell_arrays = main_reader.CellData.keys() if hasattr(main_reader, 'CellData') else []
    point_arrays = main_reader.PointData.keys() if hasattr(main_reader, 'PointData') else []
    print(f"  Cell arrays: {cell_arrays}")
    print(f"  Point arrays: {point_arrays}")

    # --- Tube filter for link thickness ---
    tube = Tube(Input=main_reader)
    tube.Scalars = ['CELLS', 'utilization']
    tube.Radius = 0.15
    tube.VaryRadius = 'By Scalar'
    tube.RadiusFactor = 8.0
    tube.NumberOfSides = 12
    tube.UpdatePipeline()

    tube_display = Show(tube, view)
    ColorBy(tube_display, ('CELLS', 'utilization'))
    tube_display.SetScalarBarVisibility(view, True)

    # Set up YlOrRd-like color transfer function
    util_lut = GetColorTransferFunction('utilization')
    util_lut.ApplyPreset('Yellow - Orange - Red', True)
    util_lut.RescaleTransferFunction(0.0, 1.0)

    # Hide the raw reader (show only the tube)
    Hide(main_reader, view)

    # ======================================================================
    #  Layer 1b: Anomaly highlight (Threshold on is_anomaly)
    # ======================================================================
    if 'is_anomaly' in cell_arrays:
        print("  Setting up anomaly highlights...")
        anom_thresh = Threshold(Input=main_reader)
        anom_thresh.Scalars = ['CELLS', 'is_anomaly']
        anom_thresh.LowerThreshold = 1
        anom_thresh.UpperThreshold = 1
        anom_thresh.UpdatePipeline()

        anom_tube = Tube(Input=anom_thresh)
        anom_tube.Radius = 0.25
        anom_tube.NumberOfSides = 12
        anom_tube.UpdatePipeline()

        anom_display = Show(anom_tube, view)
        anom_display.DiffuseColor = [1.0, 0.2, 0.2]  # Red glow
        anom_display.Opacity = 0.6
        ColorBy(anom_display, None)  # Solid color, no scalar mapping

    # ======================================================================
    #  Layer 1c: Congestion highlight (Threshold on is_congested)
    # ======================================================================
    if 'is_congested' in cell_arrays:
        print("  Setting up congestion highlights...")
        cong_thresh = Threshold(Input=main_reader)
        cong_thresh.Scalars = ['CELLS', 'is_congested']
        cong_thresh.LowerThreshold = 1
        cong_thresh.UpperThreshold = 1
        cong_thresh.UpdatePipeline()

        cong_tube = Tube(Input=cong_thresh)
        cong_tube.Radius = 0.2
        cong_tube.NumberOfSides = 12
        cong_tube.UpdatePipeline()

        cong_display = Show(cong_tube, view)
        cong_display.DiffuseColor = [1.0, 0.0, 0.0]  # Bright red
        cong_display.Opacity = 0.4
        ColorBy(cong_display, None)

    # ======================================================================
    #  Layer 1d: Node labels (if node_name point data exists)
    # ======================================================================
    # Note: ParaView can show point labels via display properties.
    # We show the main_reader with point labels but hide its surface.
    if 'node_name' in point_arrays:
        print("  Setting up node labels...")
        label_display = Show(main_reader, view)
        label_display.Opacity = 0.0  # Hide lines (shown via tube)
        label_display.PointSize = 8.0
        label_display.SelectionPointLabelVisibility = 0

        # Point Gaussian representation for showing nodes as dots
        try:
            label_display.SetRepresentationType('Point Gaussian')
            label_display.GaussianRadius = 0.3
            label_display.Opacity = 1.0
            label_display.DiffuseColor = [0.9, 0.9, 0.9]
            ColorBy(label_display, None)
        except Exception:
            # Fallback: just show as points
            label_display.SetRepresentationType('Points')
            label_display.PointSize = 10
            label_display.DiffuseColor = [0.9, 0.9, 0.9]
            ColorBy(label_display, None)

    # ======================================================================
    #  Layer 2: Missing Links
    # ======================================================================
    if os.path.exists(MISSING_PVD):
        print("Loading missing links layer...")
        miss_reader = PVDReader(FileName=MISSING_PVD)
        miss_reader.UpdatePipeline()

        miss_display = Show(miss_reader, view)
        miss_display.SetRepresentationType('Wireframe')
        miss_display.LineWidth = 2.0
        miss_display.DiffuseColor = [0.5, 0.5, 0.5]  # Gray
        miss_display.Opacity = 0.5
        ColorBy(miss_display, None)
    else:
        print("  Skipping missing links layer (file not found)")

    # ======================================================================
    #  Layer 3: Directional Arrows
    # ======================================================================
    if os.path.exists(ARROWS_PVD):
        print("Loading directional arrows layer...")
        arrow_reader = PVDReader(FileName=ARROWS_PVD)
        arrow_reader.UpdatePipeline()

        # Glyph filter: cones oriented by 'direction', scaled by 'utilization'
        glyph = Glyph(Input=arrow_reader, GlyphType='Cone')
        glyph.OrientationArray = ['POINTS', 'direction']
        glyph.ScaleArray = ['POINTS', 'utilization']
        glyph.ScaleFactor = 1.5
        glyph.GlyphMode = 'All Points'
        glyph.GlyphType.Resolution = 12
        glyph.GlyphType.Height = 1.5
        glyph.GlyphType.Radius = 0.3
        glyph.UpdatePipeline()

        glyph_display = Show(glyph, view)
        ColorBy(glyph_display, ('POINTS', 'utilization'))
        glyph_display.SetScalarBarVisibility(view, False)

        # Reuse the YlOrRd colormap
        glyph_lut = GetColorTransferFunction('utilization')
    else:
        print("  Skipping directional arrows (file not found)")

    # ======================================================================
    #  Layer 4: Demand Flow Arcs
    # ======================================================================
    if os.path.exists(DEMANDS_PVD):
        print("Loading demand flow arcs layer...")
        demand_reader = PVDReader(FileName=DEMANDS_PVD)
        demand_reader.UpdatePipeline()

        demand_tube = Tube(Input=demand_reader)
        demand_tube.Scalars = ['CELLS', 'demand_value']
        demand_tube.Radius = 0.05
        demand_tube.VaryRadius = 'By Scalar'
        demand_tube.RadiusFactor = 5.0
        demand_tube.NumberOfSides = 8
        demand_tube.UpdatePipeline()

        demand_display = Show(demand_tube, view)
        ColorBy(demand_display, ('CELLS', 'demand_value'))
        demand_display.Opacity = 0.5
        demand_display.SetScalarBarVisibility(view, True)

        # Use a Blues colormap for demands
        demand_lut = GetColorTransferFunction('demand_value')
        try:
            demand_lut.ApplyPreset('Blue to Red Rainbow', True)
        except Exception:
            pass  # Use default if preset not available

        Hide(demand_reader, view)
    else:
        print("  Skipping demand flow arcs (file not found)")

    # ======================================================================
    #  Time Annotation
    # ======================================================================
    print("Adding time annotation...")
    try:
        time_ann = AnnotateTimeFilter(Input=main_reader)
        time_ann.Format = 'Time: {time:.0f} min'
        time_ann.UpdatePipeline()

        time_display = Show(time_ann, view)
        time_display.FontSize = 14
        time_display.Color = [1.0, 1.0, 1.0]
        time_display.WindowLocation = 'Upper Right Corner'
    except Exception as e:
        print(f"  Warning: Could not add time annotation: {e}")

    # ======================================================================
    #  Camera Setup (US geographic extent)
    # ======================================================================
    print("Setting camera...")
    # Abilene network spans roughly:
    #   longitude: -122 (Seattle) to -74 (NYC)
    #   latitude:   29 (Houston) to  47 (Seattle)
    view.CameraPosition = [-98.0, 38.0, 80.0]   # Center of US, elevated
    view.CameraFocalPoint = [-98.0, 38.0, 0.0]   # Looking straight down
    view.CameraViewUp = [0.0, 1.0, 0.0]
    view.CameraParallelScale = 25.0
    view.CameraParallelProjection = 1  # Orthographic for map-like view

    # ======================================================================
    #  Final render
    # ======================================================================
    RenderAllViews()
    print("\nVisualization setup complete!")
    print("Use the animation toolbar to scrub through timesteps.")
    print("\nLayers loaded:")
    print("  - Main topology (tubes colored by utilization)")
    if 'is_anomaly' in cell_arrays:
        print("  - Anomaly highlights (red tubes)")
    if 'is_congested' in cell_arrays:
        print("  - Congestion highlights (red overlay)")
    if 'node_name' in point_arrays:
        print("  - Node labels / glyphs")
    if os.path.exists(MISSING_PVD):
        print("  - Missing links (gray wireframe)")
    if os.path.exists(ARROWS_PVD):
        print("  - Directional flow arrows (cones)")
    if os.path.exists(DEMANDS_PVD):
        print("  - Demand flow arcs (blue tubes)")
    print("\nTip: Toggle layer visibility in the Pipeline Browser.")
    print("Tip: Color the main tube by other arrays: confidence, freshness, etc.")


if __name__ == '__main__':
    setup_visualization()

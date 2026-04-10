#!/usr/bin/env python3
"""
06_plot_topology.py
Generate the two key proposal figures:
  Figure A: Congestion-only topology view (no confidence info)
  Figure B: Confidence-aware topology view (opacity encodes confidence)

Also generates a side-by-side comparison figure.

Uses matplotlib to draw the node-link graph with geographic coordinates.
Links are drawn with width proportional to utilization and color from a
sequential colormap.

Reads:  data/nodes.csv, data/links.csv, data/telemetry_final.csv
Writes: output/figure_a_congestion_only.png
        output/figure_b_confidence_aware.png
        output/figure_comparison.png
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.collections import LineCollection
import matplotlib.cm as cm

# --- Configuration ---
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'output')

# Pick a representative timestep — we'll find the one with highest max utilization
# to make the figure interesting
COLORMAP = 'YlOrRd'  # Sequential: yellow → orange → red
MIN_LINE_WIDTH = 1.0
MAX_LINE_WIDTH = 10.0
NODE_SIZE = 120
NODE_COLOR = '#2c3e50'
NODE_LABEL_SIZE = 7
BG_COLOR = '#fafafa'
MISSING_COLOR = '#888888'
MISSING_STYLE = '--'


def load_data():
    nodes_df = pd.read_csv(os.path.join(DATA_DIR, 'nodes.csv'))
    links_df = pd.read_csv(os.path.join(DATA_DIR, 'links.csv'))
    telem_df = pd.read_csv(os.path.join(DATA_DIR, 'telemetry_final.csv'))
    return nodes_df, links_df, telem_df


def find_interesting_timestep(telem_df):
    """Find the timestep with the highest peak utilization (most congested)."""
    # Group by timestep, find max utilization per timestep
    ts_max = telem_df.groupby('time_index')['utilization'].max()
    # Pick the timestep with highest max (ignoring NaN)
    best_t = ts_max.idxmax()
    print(f"  Selected timestep {best_t} (max utilization: {ts_max[best_t]:.3f})")
    return best_t


def get_timestep_data(telem_df, time_index):
    """Get telemetry for a specific timestep."""
    t_data = telem_df[telem_df['time_index'] == time_index].copy()
    # Fill NaN utilization with 0 for drawing purposes, but mark as missing
    t_data['util_draw'] = t_data['utilization'].fillna(0.0)
    t_data['conf_draw'] = t_data['confidence'].fillna(0.3)
    return t_data


def draw_topology(ax, nodes_df, links_df, t_data, show_confidence=False,
                  title="Network Congestion"):
    """
    Draw the network topology on the given axes.

    If show_confidence=True, link opacity encodes confidence and missing
    links are shown with dashed style.
    """
    ax.set_facecolor(BG_COLOR)
    ax.set_aspect('equal')

    # Node positions
    node_pos = {}
    for _, row in nodes_df.iterrows():
        node_pos[row['node_id']] = (row['x'], row['y'])

    # Build link data lookup
    link_data = t_data.set_index('link_id')

    # Colormap
    cmap = cm.get_cmap(COLORMAP)
    norm = mcolors.Normalize(vmin=0, vmax=1.0)

    # Draw links
    for _, link_row in links_df.iterrows():
        lid = link_row['link_id']
        src = link_row['source']
        tgt = link_row['target']

        if src not in node_pos or tgt not in node_pos:
            continue

        x0, y0 = node_pos[src]
        x1, y1 = node_pos[tgt]

        # Get metrics
        if lid in link_data.index:
            util = link_data.loc[lid, 'util_draw']
            conf = link_data.loc[lid, 'conf_draw']
            is_missing = bool(link_data.loc[lid, 'is_missing'])
        else:
            util = 0.0
            conf = 0.5
            is_missing = False

        # Width from utilization
        width = MIN_LINE_WIDTH + (MAX_LINE_WIDTH - MIN_LINE_WIDTH) * min(util, 1.5) / 1.5

        # Color from utilization
        color = cmap(norm(min(util, 1.0)))

        # Alpha
        if show_confidence:
            alpha = 0.15 + 0.85 * conf  # Range: 0.15 (low conf) to 1.0 (high conf)
        else:
            alpha = 0.9

        # Line style
        linestyle = MISSING_STYLE if (show_confidence and is_missing) else '-'

        # Draw link
        ax.plot([x0, x1], [y0, y1],
                color=color if not (show_confidence and is_missing) else MISSING_COLOR,
                linewidth=width,
                alpha=alpha,
                linestyle=linestyle,
                solid_capstyle='round',
                zorder=1)

    # Draw nodes
    for _, row in nodes_df.iterrows():
        x, y = row['x'], row['y']
        ax.scatter(x, y, s=NODE_SIZE, c=NODE_COLOR, zorder=3,
                   edgecolors='white', linewidths=1.5)
        ax.annotate(row['node_id'].replace('ng', ''),
                    (x, y), textcoords="offset points",
                    xytext=(0, 8), ha='center', fontsize=NODE_LABEL_SIZE,
                    fontweight='bold', color='#2c3e50', zorder=4)

    ax.set_title(title, fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')

    # Add colorbar
    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, shrink=0.7, pad=0.02)
    cbar.set_label('Link Utilization', fontsize=9)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=== Generating Topology Figures ===")

    nodes_df, links_df, telem_df = load_data()
    t = find_interesting_timestep(telem_df)
    t_data = get_timestep_data(telem_df, t)

    # --- Figure A: Congestion only ---
    print("Generating Figure A (congestion only)...")
    fig_a, ax_a = plt.subplots(1, 1, figsize=(12, 7))
    draw_topology(ax_a, nodes_df, links_df, t_data,
                  show_confidence=False,
                  title=f"Figure A: Congestion Only (t={t})")
    fig_a.tight_layout()
    path_a = os.path.join(OUTPUT_DIR, 'figure_a_congestion_only.png')
    fig_a.savefig(path_a, dpi=150, bbox_inches='tight')
    print(f"  Saved: {path_a}")
    plt.close(fig_a)

    # --- Figure B: Confidence-aware ---
    print("Generating Figure B (confidence-aware)...")
    fig_b, ax_b = plt.subplots(1, 1, figsize=(12, 7))
    draw_topology(ax_b, nodes_df, links_df, t_data,
                  show_confidence=True,
                  title=f"Figure B: Confidence-Aware (t={t})")

    # Add legend for confidence encoding
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color='#e74c3c', linewidth=3, alpha=1.0, label='High confidence'),
        Line2D([0], [0], color='#e74c3c', linewidth=3, alpha=0.3, label='Low confidence'),
        Line2D([0], [0], color=MISSING_COLOR, linewidth=2, linestyle='--',
               label='Missing data'),
    ]
    ax_b.legend(handles=legend_elements, loc='lower left', fontsize=8,
                framealpha=0.9)

    fig_b.tight_layout()
    path_b = os.path.join(OUTPUT_DIR, 'figure_b_confidence_aware.png')
    fig_b.savefig(path_b, dpi=150, bbox_inches='tight')
    print(f"  Saved: {path_b}")
    plt.close(fig_b)

    # --- Comparison figure ---
    print("Generating comparison figure...")
    fig_c, (ax_c1, ax_c2) = plt.subplots(1, 2, figsize=(22, 8))
    draw_topology(ax_c1, nodes_df, links_df, t_data,
                  show_confidence=False,
                  title="A: Congestion Only")
    draw_topology(ax_c2, nodes_df, links_df, t_data,
                  show_confidence=True,
                  title="B: Confidence-Aware")

    # Add legend to panel B
    legend_elements = [
        Line2D([0], [0], color='#e74c3c', linewidth=3, alpha=1.0, label='High confidence'),
        Line2D([0], [0], color='#e74c3c', linewidth=3, alpha=0.3, label='Low confidence'),
        Line2D([0], [0], color=MISSING_COLOR, linewidth=2, linestyle='--',
               label='Missing data'),
    ]
    ax_c2.legend(handles=legend_elements, loc='lower left', fontsize=8,
                 framealpha=0.9)

    fig_c.suptitle(f'Network Congestion Visualization Comparison (t={t})',
                   fontsize=15, fontweight='bold', y=1.01)
    fig_c.tight_layout()
    path_c = os.path.join(OUTPUT_DIR, 'figure_comparison.png')
    fig_c.savefig(path_c, dpi=150, bbox_inches='tight')
    print(f"  Saved: {path_c}")
    plt.close(fig_c)

    print("\n=== Topology Figures Complete ===")
    print("Proceed to: python scripts/07_plot_timeseries.py")


if __name__ == '__main__':
    main()

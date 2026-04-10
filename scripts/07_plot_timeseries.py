#!/usr/bin/env python3
"""
07_plot_timeseries.py
Generate time-series plots for the most congested links, showing:
- Utilization as a solid line
- Confidence band as a shaded region
- Missing data points as red markers
- Stale data points as orange markers

Reads:  data/telemetry_final.csv
Writes: output/timeseries_<link_id>.png (one per top link)
        output/timeseries_combined.png (all top links in one figure)
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# --- Configuration ---
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'output')

TOP_N_LINKS = 3           # How many links to plot
TIME_WINDOW = 500          # Timesteps to show (500 × 5min ≈ 42 hours)
BAND_SCALE = 0.15          # How wide the confidence band is relative to utilization


def load_data():
    df = pd.read_csv(os.path.join(DATA_DIR, 'telemetry_final.csv'))
    return df


def find_top_links(df, n=TOP_N_LINKS):
    """Find the N links with highest mean utilization (most congested)."""
    mean_util = df.groupby('link_id')['utilization'].mean().sort_values(ascending=False)
    top = mean_util.head(n).index.tolist()
    print(f"  Top {n} links by mean utilization:")
    for lid in top:
        print(f"    {lid}: mean util = {mean_util[lid]:.4f}")
    return top


def plot_link_timeseries(df, link_id, output_path, time_limit=TIME_WINDOW):
    """Generate a detailed time-series plot for one link."""
    link_data = df[df['link_id'] == link_id].sort_values('time_index').head(time_limit).copy()

    t = link_data['time_index'].values
    util = link_data['utilization'].values
    conf = link_data['confidence'].values
    is_missing = link_data['is_missing'].values.astype(bool)
    is_stale = (link_data['staleness_count'].values > 0)

    # For the confidence band, width is inversely proportional to confidence
    # High confidence → narrow band, low confidence → wide band
    band_width = BAND_SCALE * (1 - conf)
    upper = np.where(~np.isnan(util), util + band_width, np.nan)
    lower = np.where(~np.isnan(util), np.maximum(0, util - band_width), np.nan)

    # Create figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), height_ratios=[3, 1],
                                     sharex=True, gridspec_kw={'hspace': 0.08})

    # --- Top panel: Utilization + confidence band ---
    # Fill confidence band
    ax1.fill_between(t, lower, upper, alpha=0.25, color='#3498db',
                     label='Confidence band', linewidth=0)

    # Draw utilization line (NaN creates gaps for missing data)
    ax1.plot(t, util, color='#2c3e50', linewidth=1.2, label='Utilization', zorder=3)

    # Mark missing data
    missing_t = t[is_missing]
    if len(missing_t) > 0:
        ax1.scatter(missing_t, np.zeros(len(missing_t)), color='#e74c3c',
                    marker='x', s=20, zorder=4, label='Missing data', alpha=0.7)

    # Mark stale data
    stale_mask = is_stale & ~is_missing
    stale_t = t[stale_mask]
    stale_u = util[stale_mask]
    if len(stale_t) > 0:
        ax1.scatter(stale_t, stale_u, color='#e67e22', marker='.',
                    s=15, zorder=4, label='Stale data', alpha=0.6)

    # Overload threshold line
    ax1.axhline(y=1.0, color='#e74c3c', linestyle=':', linewidth=0.8,
                alpha=0.5, label='Capacity (util=1.0)')
    ax1.axhline(y=0.8, color='#f39c12', linestyle=':', linewidth=0.8,
                alpha=0.4, label='High util (0.8)')

    ax1.set_ylabel('Link Utilization', fontsize=10)
    ax1.set_title(f'Time Series: {link_id}', fontsize=12, fontweight='bold')
    ax1.legend(loc='upper right', fontsize=8, framealpha=0.9)
    ax1.set_ylim(bottom=-0.05)
    ax1.grid(True, alpha=0.2)

    # --- Bottom panel: Confidence score ---
    ax2.fill_between(t, 0, conf, alpha=0.4, color='#27ae60')
    ax2.plot(t, conf, color='#27ae60', linewidth=0.8)
    ax2.set_ylabel('Confidence', fontsize=10)
    ax2.set_xlabel('Timestep (5-min intervals)', fontsize=10)
    ax2.set_ylim(0, 1.05)
    ax2.grid(True, alpha=0.2)

    # Mark low-confidence regions
    low_conf_mask = conf < 0.5
    if low_conf_mask.any():
        low_t = t[low_conf_mask]
        low_c = conf[low_conf_mask]
        ax2.scatter(low_t, low_c, color='#e74c3c', s=8, zorder=3, alpha=0.5)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def plot_combined(df, link_ids, output_path, time_limit=TIME_WINDOW):
    """Plot all top links in a single combined figure."""
    n = len(link_ids)
    fig, axes = plt.subplots(n, 1, figsize=(14, 4 * n), sharex=True,
                             gridspec_kw={'hspace': 0.15})
    if n == 1:
        axes = [axes]

    for i, link_id in enumerate(link_ids):
        ax = axes[i]
        link_data = df[df['link_id'] == link_id].sort_values('time_index').head(time_limit)

        t = link_data['time_index'].values
        util = link_data['utilization'].values
        conf = link_data['confidence'].values

        band_width = BAND_SCALE * (1 - conf)
        upper = np.where(~np.isnan(util), util + band_width, np.nan)
        lower = np.where(~np.isnan(util), np.maximum(0, util - band_width), np.nan)

        ax.fill_between(t, lower, upper, alpha=0.25, color='#3498db', linewidth=0)
        ax.plot(t, util, color='#2c3e50', linewidth=1.0)
        ax.axhline(y=1.0, color='#e74c3c', linestyle=':', linewidth=0.7, alpha=0.4)

        ax.set_ylabel('Utilization', fontsize=9)
        ax.set_title(link_id, fontsize=10, fontweight='bold', loc='left')
        ax.grid(True, alpha=0.2)
        ax.set_ylim(bottom=-0.05)

    axes[-1].set_xlabel('Timestep (5-min intervals)', fontsize=10)
    fig.suptitle('Time Series with Confidence Bands — Top Congested Links',
                 fontsize=13, fontweight='bold', y=1.01)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=== Generating Time-Series Plots ===")

    df = load_data()
    top_links = find_top_links(df)

    # Individual plots
    for link_id in top_links:
        safe_name = link_id.replace('__', '_').replace('/', '_')
        out_path = os.path.join(OUTPUT_DIR, f'timeseries_{safe_name}.png')
        print(f"  Plotting {link_id}...")
        plot_link_timeseries(df, link_id, out_path)
        print(f"    Saved: {out_path}")

    # Combined plot
    combined_path = os.path.join(OUTPUT_DIR, 'timeseries_combined.png')
    print("  Generating combined plot...")
    plot_combined(df, top_links, combined_path)
    print(f"    Saved: {combined_path}")

    print("\n=== Time-Series Plots Complete ===")
    print("Proceed to: python scripts/08_evaluation_scenarios.py")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
08_evaluation_scenarios.py
Identify 4 evaluation scenarios from the processed data and generate
annotated snapshot figures plus a task-question file.

Scenarios:
  1. Clean congestion spike   — high util, high confidence
  2. Noisy hotspot            — high util, low confidence
  3. Missing data gap         — period with missing telemetry on a link
  4. Stable healthy link      — low util, high confidence

Reads:  data/nodes.csv, data/links.csv, data/telemetry_final.csv
Writes: output/scenario_1_clean_spike.png
        output/scenario_2_noisy_hotspot.png
        output/scenario_3_missing_gap.png
        output/scenario_4_stable_link.png
        output/evaluation_tasks.txt
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# --- Configuration ---
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'output')
WINDOW = 100  # Timesteps to show per scenario


def load_data():
    telem_df = pd.read_csv(os.path.join(DATA_DIR, 'telemetry_final.csv'))
    return telem_df


def find_scenarios(df):
    """
    Identify timestep windows matching each scenario type.
    Returns dict of scenario_name → (link_id, start_time, end_time)
    """
    scenarios = {}

    # For each link, compute summary stats over rolling windows
    link_ids = df['link_id'].unique()

    best_clean = {'score': -1}
    best_noisy = {'score': -1}
    best_missing = {'score': -1}
    best_stable = {'score': 1e9}

    for lid in link_ids:
        ld = df[df['link_id'] == lid].sort_values('time_index')
        n = len(ld)

        for start in range(0, n - WINDOW, WINDOW // 2):
            w = ld.iloc[start:start + WINDOW]
            t_start = w['time_index'].iloc[0]
            t_end = w['time_index'].iloc[-1]

            mean_util = w['utilization'].mean()
            mean_conf = w['confidence'].mean()
            miss_rate = w['is_missing'].mean()
            max_util = w['utilization'].max()

            # Scenario 1: Clean spike — high util, high confidence, low missingness
            score_clean = mean_util * mean_conf * (1 - miss_rate)
            if score_clean > best_clean['score'] and mean_util > 0.5 and mean_conf > 0.7:
                best_clean = {'score': score_clean, 'link_id': lid,
                              't_start': t_start, 't_end': t_end,
                              'mean_util': mean_util, 'mean_conf': mean_conf}

            # Scenario 2: Noisy hotspot — high util, low confidence
            score_noisy = mean_util * (1 - mean_conf)
            if score_noisy > best_noisy['score'] and mean_util > 0.3 and mean_conf < 0.6:
                best_noisy = {'score': score_noisy, 'link_id': lid,
                              't_start': t_start, 't_end': t_end,
                              'mean_util': mean_util, 'mean_conf': mean_conf}

            # Scenario 3: Missing data gap — high missingness rate
            if miss_rate > best_missing.get('miss_rate', 0):
                best_missing = {'score': miss_rate, 'link_id': lid,
                                't_start': t_start, 't_end': t_end,
                                'miss_rate': miss_rate, 'mean_util': mean_util}

            # Scenario 4: Stable healthy — low util, high confidence
            score_stable = mean_util + (1 - mean_conf)
            if score_stable < best_stable['score'] and mean_conf > 0.7:
                best_stable = {'score': score_stable, 'link_id': lid,
                               't_start': t_start, 't_end': t_end,
                               'mean_util': mean_util, 'mean_conf': mean_conf}

    scenarios['clean_spike'] = best_clean
    scenarios['noisy_hotspot'] = best_noisy
    scenarios['missing_gap'] = best_missing
    scenarios['stable_link'] = best_stable

    return scenarios


def plot_scenario(df, scenario, title, output_path):
    """Plot a single scenario window."""
    lid = scenario['link_id']
    t0 = scenario['t_start']
    t1 = scenario['t_end']

    w = df[(df['link_id'] == lid) &
           (df['time_index'] >= t0) &
           (df['time_index'] <= t1)].sort_values('time_index')

    t = w['time_index'].values
    util = w['utilization'].values
    conf = w['confidence'].values
    is_missing = w['is_missing'].values.astype(bool)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), height_ratios=[2, 1],
                                     sharex=True, gridspec_kw={'hspace': 0.08})

    # Utilization with confidence band
    band = 0.15 * (1 - conf)
    upper = np.where(~np.isnan(util), util + band, np.nan)
    lower = np.where(~np.isnan(util), np.maximum(0, util - band), np.nan)

    ax1.fill_between(t, lower, upper, alpha=0.3, color='#3498db', linewidth=0)
    ax1.plot(t, util, color='#2c3e50', linewidth=1.2)

    missing_t = t[is_missing]
    if len(missing_t) > 0:
        ax1.scatter(missing_t, np.zeros(len(missing_t)), color='#e74c3c',
                    marker='x', s=30, zorder=4, alpha=0.8)

    ax1.axhline(y=1.0, color='#e74c3c', linestyle=':', linewidth=0.8, alpha=0.4)
    ax1.set_ylabel('Utilization')
    ax1.set_title(f'{title}\nLink: {lid}', fontsize=11, fontweight='bold')
    ax1.grid(True, alpha=0.2)

    # Confidence
    ax2.fill_between(t, 0, conf, alpha=0.4, color='#27ae60')
    ax2.plot(t, conf, color='#27ae60', linewidth=0.8)
    ax2.set_ylabel('Confidence')
    ax2.set_xlabel('Timestep')
    ax2.set_ylim(0, 1.05)
    ax2.grid(True, alpha=0.2)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)


def write_evaluation_tasks(scenarios, output_path):
    """Write evaluation task questions to a text file."""
    with open(output_path, 'w') as f:
        f.write("=" * 70 + "\n")
        f.write("EVALUATION TASK QUESTIONS\n")
        f.write("Network Congestion & Uncertainty Visualization\n")
        f.write("=" * 70 + "\n\n")

        f.write("INSTRUCTIONS:\n")
        f.write("Each scenario shows a time window of network link telemetry.\n")
        f.write("Condition A: Congestion-only view (no confidence information)\n")
        f.write("Condition B: Confidence-aware view (with uncertainty encoding)\n")
        f.write("Answer each question for both conditions.\n\n")

        # Scenario 1
        s = scenarios['clean_spike']
        f.write("-" * 50 + "\n")
        f.write(f"SCENARIO 1: Clean Congestion Spike\n")
        f.write(f"Link: {s['link_id']}, Time window: {s['t_start']}-{s['t_end']}\n\n")
        f.write("Q1.1: Is this link congested during this time window? (Yes/No)\n")
        f.write("Q1.2: At what timestep does peak congestion occur?\n")
        f.write("Q1.3: How confident are you in your answer to Q1.1? (1-5 scale)\n")
        f.write("Q1.4: [Condition B only] Does the confidence information change\n")
        f.write("       your interpretation? (Yes/No, explain)\n\n")

        # Scenario 2
        s = scenarios['noisy_hotspot']
        f.write("-" * 50 + "\n")
        f.write(f"SCENARIO 2: Noisy Hotspot\n")
        f.write(f"Link: {s['link_id']}, Time window: {s['t_start']}-{s['t_end']}\n\n")
        f.write("Q2.1: Is this link congested during this time window? (Yes/No)\n")
        f.write("Q2.2: How reliable is the displayed congestion level?\n")
        f.write("       (Very reliable / Somewhat reliable / Unreliable)\n")
        f.write("Q2.3: Would you take action based on this data? (Yes/No)\n")
        f.write("Q2.4: [Condition B only] Does the low confidence change\n")
        f.write("       whether you would act? (Yes/No, explain)\n\n")

        # Scenario 3
        s = scenarios['missing_gap']
        f.write("-" * 50 + "\n")
        f.write(f"SCENARIO 3: Missing Data Gap\n")
        f.write(f"Link: {s['link_id']}, Time window: {s['t_start']}-{s['t_end']}\n\n")
        f.write("Q3.1: Are there periods where data appears to be missing? (Yes/No)\n")
        f.write("Q3.2: During the gap, is the link congested or healthy?\n")
        f.write("       (Congested / Healthy / Cannot determine)\n")
        f.write("Q3.3: [Condition B only] Does the visualization clearly\n")
        f.write("       indicate which measurements are missing? (Yes/No)\n\n")

        # Scenario 4
        s = scenarios['stable_link']
        f.write("-" * 50 + "\n")
        f.write(f"SCENARIO 4: Stable Healthy Link\n")
        f.write(f"Link: {s['link_id']}, Time window: {s['t_start']}-{s['t_end']}\n\n")
        f.write("Q4.1: Is this link congested? (Yes/No)\n")
        f.write("Q4.2: How confident are you that this link is healthy? (1-5)\n")
        f.write("Q4.3: [Condition B only] Does the confidence information\n")
        f.write("       increase your certainty? (Yes/No)\n\n")

        f.write("=" * 70 + "\n")
        f.write("SCORING:\n")
        f.write("- Correct identification: 1 point\n")
        f.write("- Incorrect identification: 0 points\n")
        f.write("- Compare total scores between Condition A and Condition B\n")
        f.write("- Hypothesis: Condition B should yield fewer incorrect\n")
        f.write("  interpretations, especially in Scenarios 2 and 3.\n")
        f.write("=" * 70 + "\n")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=== Generating Evaluation Scenarios ===")

    df = load_data()

    print("Finding scenario windows...")
    scenarios = find_scenarios(df)

    for name, s in scenarios.items():
        print(f"  {name}: link={s.get('link_id', '?')}, "
              f"t={s.get('t_start', '?')}-{s.get('t_end', '?')}, "
              f"score={s.get('score', 0):.4f}")

    # Plot each scenario
    scenario_configs = [
        ('clean_spike', 'Scenario 1: Clean Congestion Spike', 'scenario_1_clean_spike.png'),
        ('noisy_hotspot', 'Scenario 2: Noisy Hotspot', 'scenario_2_noisy_hotspot.png'),
        ('missing_gap', 'Scenario 3: Missing Data Gap', 'scenario_3_missing_gap.png'),
        ('stable_link', 'Scenario 4: Stable Healthy Link', 'scenario_4_stable_link.png'),
    ]

    for key, title, filename in scenario_configs:
        if 'link_id' in scenarios[key]:
            out_path = os.path.join(OUTPUT_DIR, filename)
            print(f"  Plotting {title}...")
            plot_scenario(df, scenarios[key], title, out_path)
            print(f"    Saved: {out_path}")
        else:
            print(f"  WARNING: No good window found for {key}")

    # Write evaluation tasks
    tasks_path = os.path.join(OUTPUT_DIR, 'evaluation_tasks.txt')
    write_evaluation_tasks(scenarios, tasks_path)
    print(f"\nSaved evaluation tasks to {tasks_path}")

    print("\n=== All Done! ===")
    print("\nDeliverables in output/:")
    print("  - figure_a_congestion_only.png    (from script 06)")
    print("  - figure_b_confidence_aware.png   (from script 06)")
    print("  - figure_comparison.png           (from script 06)")
    print("  - timeseries_*.png                (from script 07)")
    print("  - scenario_*.png                  (from script 08)")
    print("  - evaluation_tasks.txt            (from script 08)")
    print("\nOptional ParaView files in vtk_output/ (from script 05)")


if __name__ == '__main__':
    main()

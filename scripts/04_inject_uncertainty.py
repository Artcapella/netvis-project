#!/usr/bin/env python3
"""
04_inject_uncertainty.py
Inject synthetic uncertainty into the utilization data and compute a
composite confidence score per link per timestep.

Uncertainty sources:
  1. Temporal variance  — rolling std of utilization
  2. Missingness        — randomly drop ~8% of measurements
  3. Staleness          — ~5% of measurements are stale (repeated previous)
  4. Estimator disagreement — synthetic second estimator with added noise

Confidence = 1 - normalize(w1*variance + w2*missingness + w3*staleness + w4*disagreement)

Reads:  data/utilization.csv
Writes: data/telemetry_final.csv
"""

import os
import numpy as np
import pandas as pd

# --- Configuration ---
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

SEED = 42
MISSINGNESS_RATE = 0.08     # 8% of measurements will be missing
STALENESS_RATE = 0.05       # 5% of measurements will be stale
VARIANCE_WINDOW = 12        # Rolling window = 12 timesteps = 1 hour at 5-min res
NOISE_STD = 0.05            # Std dev of Gaussian noise for estimator disagreement

# Confidence weights
W_VARIANCE = 0.3
W_MISSING = 0.25
W_STALENESS = 0.2
W_DISAGREEMENT = 0.25


def inject_uncertainty(util_df, seed=SEED):
    """Add uncertainty columns to the utilization DataFrame."""
    rng = np.random.RandomState(seed)
    df = util_df.copy()
    link_ids = df['link_id'].unique()

    # Initialize new columns
    df['variance'] = 0.0
    df['is_missing'] = False
    df['staleness_count'] = 0
    df['disagreement'] = 0.0
    df['util_original'] = df['utilization'].copy()

    for link_id in link_ids:
        mask = df['link_id'] == link_id
        idx = df.index[mask]
        n = len(idx)

        # --- 1. Temporal variance (rolling std) ---
        utils = df.loc[idx, 'utilization'].values
        # Compute rolling std with a fixed window
        variance = pd.Series(utils).rolling(
            window=VARIANCE_WINDOW, min_periods=1, center=True
        ).std().fillna(0).values
        df.loc[idx, 'variance'] = variance

        # --- 2. Missingness ---
        missing_mask = rng.random(n) < MISSINGNESS_RATE
        # Cluster some missingness (bursty pattern is more realistic)
        for i in range(n):
            if missing_mask[i] and i + 1 < n and rng.random() < 0.4:
                missing_mask[i + 1] = True  # burst
        df.loc[idx, 'is_missing'] = missing_mask

        # --- 3. Staleness ---
        stale_mask = rng.random(n) < STALENESS_RATE
        stale_mask[0] = False  # can't be stale at t=0
        staleness_counts = np.zeros(n, dtype=int)
        for i in range(1, n):
            if stale_mask[i]:
                # Replace with previous value
                df.loc[idx[i], 'utilization'] = df.loc[idx[i - 1], 'utilization']
                df.loc[idx[i], 'latency_proxy'] = df.loc[idx[i - 1], 'latency_proxy']
                df.loc[idx[i], 'queue_proxy'] = df.loc[idx[i - 1], 'queue_proxy']
                staleness_counts[i] = staleness_counts[i - 1] + 1
            else:
                staleness_counts[i] = 0
        df.loc[idx, 'staleness_count'] = staleness_counts

        # --- 4. Estimator disagreement ---
        # Simulate a second estimator by adding noise to the utilization
        noise = rng.normal(0, NOISE_STD, n)
        util_est2 = utils + noise
        disagreement = np.abs(utils - util_est2)
        df.loc[idx, 'disagreement'] = disagreement

        # Set missing values to NaN
        missing_idx = idx[missing_mask]
        df.loc[missing_idx, 'utilization'] = np.nan
        df.loc[missing_idx, 'latency_proxy'] = np.nan
        df.loc[missing_idx, 'queue_proxy'] = np.nan

    return df


def compute_confidence(df):
    """
    Compute composite confidence score from uncertainty factors.
    confidence = 1 - normalize(weighted sum of factors)
    """
    # Normalize each factor to [0, 1] range globally
    def safe_normalize(series):
        s = series.fillna(series.max() if series.max() > 0 else 1.0)
        smin, smax = s.min(), s.max()
        if smax == smin:
            return pd.Series(0.0, index=series.index)
        return (s - smin) / (smax - smin)

    norm_var = safe_normalize(df['variance'])
    norm_miss = df['is_missing'].astype(float)  # already 0/1
    norm_stale = safe_normalize(df['staleness_count'].astype(float))
    norm_disagree = safe_normalize(df['disagreement'])

    weighted = (W_VARIANCE * norm_var +
                W_MISSING * norm_miss +
                W_STALENESS * norm_stale +
                W_DISAGREEMENT * norm_disagree)

    # Normalize the weighted sum to [0, 1]
    w_min, w_max = weighted.min(), weighted.max()
    if w_max > w_min:
        weighted_norm = (weighted - w_min) / (w_max - w_min)
    else:
        weighted_norm = pd.Series(0.0, index=df.index)

    confidence = 1.0 - weighted_norm
    # Clamp to [0.05, 1.0] — never fully zero confidence
    confidence = confidence.clip(0.05, 1.0)

    return confidence


def main():
    print("=== Injecting Uncertainty ===")

    # Load utilization data
    util_path = os.path.join(DATA_DIR, 'utilization.csv')
    df = pd.read_csv(util_path)
    print(f"Loaded {len(df)} utilization records")

    # Inject uncertainty
    print("Injecting noise, missingness, staleness, and estimator disagreement...")
    df = inject_uncertainty(df)

    # Compute confidence
    print("Computing confidence scores...")
    df['confidence'] = compute_confidence(df)

    # Round for cleanliness
    for col in ['variance', 'disagreement', 'confidence']:
        df[col] = df[col].round(6)

    # Save
    out_path = os.path.join(DATA_DIR, 'telemetry_final.csv')
    df.to_csv(out_path, index=False)

    # Summary
    print(f"\nSaved {len(df)} records to {out_path}")
    print(f"\nConfidence stats:")
    print(f"  Mean:   {df['confidence'].mean():.4f}")
    print(f"  Median: {df['confidence'].median():.4f}")
    print(f"  Min:    {df['confidence'].min():.4f}")
    print(f"  Max:    {df['confidence'].max():.4f}")
    print(f"\nMissingness: {df['is_missing'].mean()*100:.1f}% of records")
    print(f"Staleness > 0: {(df['staleness_count'] > 0).mean()*100:.1f}% of records")

    print("\n=== Uncertainty Injection Complete ===")
    print("Proceed to: python scripts/05_export_vtk.py")
    print("   or skip to: python scripts/06_plot_topology.py")


if __name__ == '__main__':
    main()

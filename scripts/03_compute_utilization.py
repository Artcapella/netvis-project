#!/usr/bin/env python3
"""
03_compute_utilization.py
Route demands over the network topology and compute per-link utilization
plus derived metrics (latency proxy, queue proxy).

Reads:  data/nodes.csv, data/links.csv, data/demands.csv
Writes: data/utilization.csv

Routing uses shortest hop-count path via NetworkX.
"""

import os
import numpy as np
import pandas as pd
import networkx as nx

# --- Configuration ---
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

# M/M/1 base latency in ms (propagation delay proxy)
BASE_LATENCY_MS = 5.0

# Queue proxy threshold — backlog accumulates above this utilization
QUEUE_THRESHOLD = 0.8


def build_graph(nodes_df, links_df):
    """Build an undirected NetworkX graph from node and link CSVs."""
    G = nx.Graph()
    for _, row in nodes_df.iterrows():
        G.add_node(row['node_id'], x=row['x'], y=row['y'])
    for _, row in links_df.iterrows():
        G.add_edge(row['source'], row['target'],
                    link_id=row['link_id'],
                    capacity=row['capacity'])
    return G


def precompute_routes(G, node_list):
    """
    Precompute shortest paths for all node pairs.
    Returns dict: (src, tgt) → list of edges as (u, v) tuples along the path.
    """
    routes = {}
    for src in node_list:
        for tgt in node_list:
            if src == tgt:
                continue
            try:
                path = nx.shortest_path(G, src, tgt)
                # Convert node path to edge list
                edges = []
                for i in range(len(path) - 1):
                    u, v = path[i], path[i + 1]
                    # Normalize edge key (undirected: always alphabetical order)
                    edge_key = tuple(sorted([u, v]))
                    edges.append(edge_key)
                routes[(src, tgt)] = edges
            except nx.NetworkXNoPath:
                routes[(src, tgt)] = []
    return routes


def compute_utilization(demands_df, links_df, routes, G):
    """
    For each timestep, route all demands and compute per-link utilization.
    Returns a DataFrame with columns: link_id, time_index, utilization,
    latency_proxy, queue_proxy.
    """
    # Build a mapping from edge tuple to link_id and capacity
    edge_to_link = {}
    edge_to_cap = {}
    for _, row in links_df.iterrows():
        key = tuple(sorted([row['source'], row['target']]))
        edge_to_link[key] = row['link_id']
        edge_to_cap[key] = row['capacity']

    all_link_ids = links_df['link_id'].tolist()
    time_indices = sorted(demands_df['time_index'].unique())

    results = []

    for i, t in enumerate(time_indices):
        if i % 200 == 0:
            print(f"  Processing timestep {i}/{len(time_indices)} (t={t})")

        # Get demands for this timestep
        t_demands = demands_df[demands_df['time_index'] == t]

        # Accumulate traffic per edge
        edge_traffic = {key: 0.0 for key in edge_to_link.keys()}

        for _, row in t_demands.iterrows():
            src, tgt = row['source'], row['target']
            demand = row['demand_value']
            route = routes.get((src, tgt), [])
            for edge_key in route:
                if edge_key in edge_traffic:
                    edge_traffic[edge_key] += demand

        # Compute metrics for each link
        for edge_key, traffic in edge_traffic.items():
            link_id = edge_to_link[edge_key]
            capacity = edge_to_cap[edge_key]

            util = traffic / capacity if capacity > 0 else 0.0

            # Latency proxy: M/M/1 model — latency rises sharply near util=1
            clamped_util = min(util, 0.99)
            latency = BASE_LATENCY_MS / (1.0 - clamped_util)

            # Queue proxy: estimated backlog when over threshold
            queue = max(0.0, util - QUEUE_THRESHOLD) * capacity

            results.append({
                'link_id': link_id,
                'time_index': t,
                'utilization': round(util, 6),
                'latency_proxy': round(latency, 3),
                'queue_proxy': round(queue, 3),
            })

    return pd.DataFrame(results)


def main():
    print("=== Computing Link Utilization ===")

    # Load data
    nodes_df = pd.read_csv(os.path.join(DATA_DIR, 'nodes.csv'))
    links_df = pd.read_csv(os.path.join(DATA_DIR, 'links.csv'))
    demands_df = pd.read_csv(os.path.join(DATA_DIR, 'demands.csv'))

    print(f"Loaded: {len(nodes_df)} nodes, {len(links_df)} links, "
          f"{len(demands_df)} demand records")

    # Build graph
    G = build_graph(nodes_df, links_df)
    node_list = nodes_df['node_id'].tolist()

    # Precompute routes
    print("Precomputing shortest-path routes...")
    routes = precompute_routes(G, node_list)
    print(f"  Computed routes for {len(routes)} node pairs")

    # Compute utilization
    print("Computing per-link utilization...")
    util_df = compute_utilization(demands_df, links_df, routes, G)

    # Save
    out_path = os.path.join(DATA_DIR, 'utilization.csv')
    util_df.to_csv(out_path, index=False)

    # Summary stats
    print(f"\nSaved {len(util_df)} records to {out_path}")
    print(f"\nUtilization stats:")
    print(f"  Mean:   {util_df['utilization'].mean():.4f}")
    print(f"  Median: {util_df['utilization'].median():.4f}")
    print(f"  Max:    {util_df['utilization'].max():.4f}")
    print(f"  >1.0 (overloaded): {(util_df['utilization'] > 1.0).sum()} records")

    print("\n=== Utilization Complete ===")
    print("Proceed to: python scripts/04_inject_uncertainty.py")


if __name__ == '__main__':
    main()

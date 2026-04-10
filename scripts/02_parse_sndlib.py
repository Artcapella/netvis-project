#!/usr/bin/env python3
"""
02_parse_sndlib.py
Parse SNDlib Abilene XML files into clean CSV tables.

Handles multiple possible XML structures from SNDlib (they vary between
download formats). Outputs:
  - data/nodes.csv   (node_id, x, y)
  - data/links.csv   (link_id, source, target, capacity)
  - data/demands.csv  (time_index, source, target, demand_value)

If the real SNDlib download failed, this script will generate synthetic
data that matches the Abilene topology structure so you can continue
building the visualization pipeline.
"""

import os
import sys
import glob
import numpy as np
import pandas as pd
from xml.etree import ElementTree as ET

# --- Configuration ---
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
RAW_DIR = os.path.join(DATA_DIR, 'raw')
DEMANDS_DIR = os.path.join(RAW_DIR, 'demands')

# Limit to 1 week of 5-min data = 2016 timesteps for MVP
WEEK_LIMIT = 2016


# =====================================================================
# ABILENE FALLBACK DATA
# If SNDlib download fails, we use this hardcoded Abilene topology.
# Coordinates are approximate geographic positions (longitude, latitude).
# Capacities are in Mbps (typical OC-48 = 2488 Mbps).
# =====================================================================

ABILENE_NODES = {
    'ATLAM5':    (-84.39,  33.75),
    'ATLAng':    (-84.38,  33.76),
    'CHINng':    (-87.63,  41.88),
    'DNVRng':    (-104.99, 39.74),
    'HSTNng':    (-95.37,  29.76),
    'IPLSng':    (-86.16,  39.77),
    'KSCYng':    (-94.58,  39.10),
    'LOSAng':    (-118.24, 34.05),
    'NYCMng':    (-74.01,  40.71),
    'SNVAng':    (-122.03, 37.37),
    'STTLng':    (-122.33, 47.61),
    'WASHng':    (-77.04,  38.91),
}

ABILENE_LINKS = [
    ('ATLAM5',  'ATLAng',  9920.0),
    ('ATLAng',  'CHINng',  9920.0),
    ('ATLAng',  'HSTNng',  9920.0),
    ('ATLAng',  'IPLSng',  9920.0),
    ('ATLAng',  'WASHng',  9920.0),
    ('CHINng',  'IPLSng',  9920.0),
    ('CHINng',  'NYCMng',  9920.0),
    ('DNVRng',  'KSCYng',  9920.0),
    ('DNVRng',  'SNVAng',  9920.0),
    ('HSTNng',  'KSCYng',  9920.0),
    ('IPLSng',  'KSCYng',  9920.0),
    ('KSCYng',  'SNVAng',  9920.0),
    ('LOSAng',  'SNVAng',  9920.0),
    ('NYCMng',  'WASHng',  9920.0),
    ('SNVAng',  'STTLng',  9920.0),
]


def parse_topology_xml(xml_path):
    """
    Parse an SNDlib native-format topology XML file.
    Returns (nodes_dict, links_list) or (None, None) on failure.

    SNDlib native format structure:
    <network>
      <networkStructure>
        <nodes>
          <node id="...">
            <coordinates><x>...</x><y>...</y></coordinates>
          </node>
        </nodes>
        <links>
          <link id="...">
            <source>...</source>
            <target>...</target>
            <additionalModules>
              <addModule>
                <capacity>...</capacity>
              </addModule>
            </additionalModules>
          </link>
        </links>
      </networkStructure>
    </network>
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as e:
        print(f"  XML parse error: {e}")
        return None, None

    # Handle namespace if present
    ns = ''
    if root.tag.startswith('{'):
        ns = root.tag.split('}')[0] + '}'

    # --- Parse nodes ---
    nodes = {}
    for node_elem in root.iter(f'{ns}node'):
        node_id = node_elem.get('id')
        if not node_id:
            continue
        x_elem = node_elem.find(f'.//{ns}x')
        y_elem = node_elem.find(f'.//{ns}y')
        if x_elem is not None and y_elem is not None:
            try:
                nodes[node_id] = (float(x_elem.text), float(y_elem.text))
            except (TypeError, ValueError):
                nodes[node_id] = (0.0, 0.0)
        else:
            nodes[node_id] = (0.0, 0.0)

    # --- Parse links ---
    links = []
    for link_elem in root.iter(f'{ns}link'):
        link_id = link_elem.get('id')
        src_elem = link_elem.find(f'{ns}source')
        tgt_elem = link_elem.find(f'{ns}target')
        if src_elem is None:
            src_elem = link_elem.find(f'.//{ns}source')
        if tgt_elem is None:
            tgt_elem = link_elem.find(f'.//{ns}target')

        if src_elem is None or tgt_elem is None:
            continue

        source = src_elem.text.strip()
        target = tgt_elem.text.strip()

        # Try to find capacity
        cap = 9920.0  # default OC-48 ×4
        cap_elem = link_elem.find(f'.//{ns}capacity')
        if cap_elem is not None and cap_elem.text:
            try:
                cap = float(cap_elem.text)
            except ValueError:
                pass

        links.append((source, target, cap))

    if len(nodes) > 0 and len(links) > 0:
        return nodes, links
    return None, None


def parse_demands_xml(xml_path, node_list, max_matrices=WEEK_LIMIT):
    """
    Parse SNDlib demand matrix XML.
    Returns list of (time_index, source, target, value) tuples.

    SNDlib demand matrix format:
    <demandMatrix>
      <demand id="...">
        <source>...</source>
        <target>...</target>
        <demandValue>...</demandValue>
      </demand>
    </demandMatrix>
    """
    records = []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as e:
        print(f"  Demand XML parse error: {e}")
        return records

    ns = ''
    if root.tag.startswith('{'):
        ns = root.tag.split('}')[0] + '}'

    time_idx = 0
    for dm_elem in root.iter(f'{ns}demandMatrix'):
        if time_idx >= max_matrices:
            break
        for d_elem in dm_elem.iter(f'{ns}demand'):
            src_elem = d_elem.find(f'{ns}source')
            tgt_elem = d_elem.find(f'{ns}target')
            val_elem = d_elem.find(f'{ns}demandValue')

            if src_elem is None or tgt_elem is None or val_elem is None:
                # Try alternative tag names
                src_elem = src_elem or d_elem.find(f'.//{ns}source')
                tgt_elem = tgt_elem or d_elem.find(f'.//{ns}target')
                val_elem = val_elem or d_elem.find(f'.//{ns}demandValue')

            if all(e is not None for e in [src_elem, tgt_elem, val_elem]):
                try:
                    records.append((
                        time_idx,
                        src_elem.text.strip(),
                        tgt_elem.text.strip(),
                        float(val_elem.text)
                    ))
                except (TypeError, ValueError):
                    pass
        time_idx += 1

    return records


def generate_synthetic_demands(node_list, n_timesteps=WEEK_LIMIT, seed=42):
    """
    Generate synthetic demand matrices that mimic real traffic patterns.
    Uses diurnal patterns + random variation.
    """
    rng = np.random.RandomState(seed)
    n_nodes = len(node_list)
    pairs = [(s, t) for s in node_list for t in node_list if s != t]

    records = []
    for t in range(n_timesteps):
        # Diurnal pattern: peak during "business hours" (timesteps mod 288 ≈ 1 day)
        hour_of_day = (t % 288) / 288.0 * 24.0
        diurnal = 0.5 + 0.5 * np.sin(2 * np.pi * (hour_of_day - 6) / 24.0)
        diurnal = max(0.1, diurnal)

        # Weekly pattern: lower on "weekends"
        day_of_week = (t // 288) % 7
        weekly = 0.6 if day_of_week >= 5 else 1.0

        for src, tgt in pairs:
            # Base demand varies by node pair
            pair_hash = hash((src, tgt)) % 1000 / 1000.0
            base = 200 + 800 * pair_hash  # Mbps range

            # Add noise and patterns
            noise = rng.exponential(50)
            demand = base * diurnal * weekly + noise

            # Occasional spikes
            if rng.random() < 0.002:
                demand *= rng.uniform(3, 8)

            records.append((t, src, tgt, max(0, demand)))

    return records


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    # --- Parse topology ---
    print("=== Parsing Topology ===")
    topo_path = os.path.join(RAW_DIR, 'abilene.xml')
    nodes, links = None, None

    if os.path.exists(topo_path):
        print(f"Found topology file: {topo_path}")
        nodes, links = parse_topology_xml(topo_path)
        if nodes:
            print(f"  Parsed {len(nodes)} nodes, {len(links)} links from XML")
        else:
            print("  XML parsing returned no data")

    if not nodes:
        print("Using hardcoded Abilene topology (12 nodes, 15 links)")
        nodes = ABILENE_NODES
        links = ABILENE_LINKS

    # Save nodes
    node_rows = [(nid, xy[0], xy[1]) for nid, xy in nodes.items()]
    nodes_df = pd.DataFrame(node_rows, columns=['node_id', 'x', 'y'])
    nodes_df.to_csv(os.path.join(DATA_DIR, 'nodes.csv'), index=False)
    print(f"Saved {len(nodes_df)} nodes to data/nodes.csv")

    # Save links
    link_rows = [(f"{s}__{t}", s, t, c) for s, t, c in links]
    links_df = pd.DataFrame(link_rows, columns=['link_id', 'source', 'target', 'capacity'])
    links_df.to_csv(os.path.join(DATA_DIR, 'links.csv'), index=False)
    print(f"Saved {len(links_df)} links to data/links.csv")

    node_list = list(nodes.keys())

    # --- Parse demands ---
    print("\n=== Parsing Demands ===")
    demand_records = []

    # Try parsing from downloaded files
    demand_files = []
    if os.path.exists(DEMANDS_DIR):
        demand_files = sorted(glob.glob(os.path.join(DEMANDS_DIR, '*.xml')))
        demand_files += sorted(glob.glob(os.path.join(DEMANDS_DIR, '**', '*.xml'), recursive=True))

    if demand_files:
        print(f"Found {len(demand_files)} demand file(s)")
        for fpath in demand_files[:5]:  # Try first few
            records = parse_demands_xml(fpath, node_list)
            if records:
                demand_records.extend(records)
                print(f"  Parsed {len(records)} demand records from {os.path.basename(fpath)}")

    if len(demand_records) < 100:
        print("Insufficient demand data from XML. Generating synthetic demands...")
        print(f"  Generating {WEEK_LIMIT} timesteps of synthetic traffic...")
        demand_records = generate_synthetic_demands(node_list, WEEK_LIMIT)
        print(f"  Generated {len(demand_records)} demand records")

    # Save demands
    demands_df = pd.DataFrame(demand_records,
                              columns=['time_index', 'source', 'target', 'demand_value'])
    demands_df.to_csv(os.path.join(DATA_DIR, 'demands.csv'), index=False)
    print(f"Saved {len(demands_df)} demand records to data/demands.csv")

    n_times = demands_df['time_index'].nunique()
    n_pairs = demands_df.groupby(['source', 'target']).ngroups
    print(f"  {n_times} timesteps × {n_pairs} node pairs")

    print("\n=== Parse Complete ===")
    print("Proceed to: python scripts/03_compute_utilization.py")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
01_download_sndlib.py
Download the SNDlib Abilene network topology and traffic matrices.

SNDlib provides the data in their native XML format. The Abilene instance has:
- 12 nodes, 15 links
- 48,096 demand matrices at 5-minute resolution over ~6 months

We download the topology and demand files into data/raw/.
"""

import os
import requests
import zipfile
import io

# --- Configuration ---
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
RAW_DIR = os.path.join(DATA_DIR, 'raw')

# SNDlib base URL — these are the direct download links for native format
# If these fail, go to https://sndlib.put.poznan.pl/home.action manually
TOPOLOGY_URL = "https://sndlib.put.poznan.pl/download/sndlib-network-abilene.xml"
DEMANDS_URL = "https://sndlib.put.poznan.pl/download/sndlib-demandmatrix-abilene-5min.zip"

# Fallback: sometimes SNDlib uses different URL patterns
ALT_TOPOLOGY_URL = "https://sndlib.put.poznan.pl/networks/abilene/abilene.xml"
ALT_DEMANDS_URL = "https://sndlib.put.poznan.pl/networks/abilene/demandmatrices/abilene-5min.zip"


def download_file(url, dest_path, description="file"):
    """Download a file with basic error handling and retries."""
    print(f"Downloading {description} from {url} ...")
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        return resp.content
    except requests.RequestException as e:
        print(f"  Failed: {e}")
        return None


def main():
    os.makedirs(RAW_DIR, exist_ok=True)

    # --- Download topology ---
    topo_path = os.path.join(RAW_DIR, 'abilene.xml')
    if os.path.exists(topo_path):
        print(f"Topology already exists at {topo_path}, skipping download.")
    else:
        content = download_file(TOPOLOGY_URL, topo_path, "topology")
        if content is None:
            content = download_file(ALT_TOPOLOGY_URL, topo_path, "topology (alt URL)")
        if content is None:
            print("\n*** MANUAL DOWNLOAD REQUIRED ***")
            print("Go to https://sndlib.put.poznan.pl/home.action")
            print("Navigate to: Networks → abilene → download native XML format")
            print(f"Save the topology file as: {topo_path}")
            print("Then re-run this script or proceed to script 02.")
        else:
            with open(topo_path, 'wb') as f:
                f.write(content)
            print(f"  Saved topology to {topo_path}")

    # --- Download demand matrices ---
    demands_dir = os.path.join(RAW_DIR, 'demands')
    if os.path.exists(demands_dir) and len(os.listdir(demands_dir)) > 0:
        print(f"Demands already exist at {demands_dir}, skipping download.")
    else:
        os.makedirs(demands_dir, exist_ok=True)
        content = download_file(DEMANDS_URL, None, "demand matrices")
        if content is None:
            content = download_file(ALT_DEMANDS_URL, None, "demand matrices (alt URL)")

        if content is None:
            # If zip download fails, try downloading a single combined XML
            print("Zip download failed. Trying single-file demand format...")
            single_url = "https://sndlib.put.poznan.pl/networks/abilene/abilene-demandmatrix.xml"
            content = download_file(single_url, None, "combined demand XML")
            if content:
                dest = os.path.join(demands_dir, 'abilene-demands.xml')
                with open(dest, 'wb') as f:
                    f.write(content)
                print(f"  Saved combined demand file to {dest}")
            else:
                print("\n*** MANUAL DOWNLOAD REQUIRED ***")
                print("Go to https://sndlib.put.poznan.pl/home.action")
                print("Navigate to: Networks → abilene → demand matrices → 5min")
                print(f"Extract contents into: {demands_dir}/")
                print("Then proceed to script 02.")
        else:
            # Try to unzip
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    zf.extractall(demands_dir)
                print(f"  Extracted demand matrices to {demands_dir}")
                print(f"  Found {len(os.listdir(demands_dir))} files.")
            except zipfile.BadZipFile:
                # Maybe it was a single XML file, not a zip
                dest = os.path.join(demands_dir, 'abilene-demands.xml')
                with open(dest, 'wb') as f:
                    f.write(content)
                print(f"  Saved as single file: {dest}")

    # --- Summary ---
    print("\n=== Download Summary ===")
    print(f"Topology: {topo_path} — exists: {os.path.exists(topo_path)}")
    if os.path.exists(demands_dir):
        n_files = len(os.listdir(demands_dir))
        print(f"Demands:  {demands_dir} — {n_files} file(s)")
    else:
        print(f"Demands:  {demands_dir} — NOT FOUND")
    print("\nIf downloads failed, see CLAUDE_CODE_INSTRUCTIONS.md for manual steps.")
    print("Proceed to: python scripts/02_parse_sndlib.py")


if __name__ == '__main__':
    main()

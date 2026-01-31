
import csv
from pathlib import Path

import argparse

def main():
    parser = argparse.ArgumentParser(description="Rebuild index.csv for a dataset directory.")
    parser.add_argument("root_dir", type=Path, help="Root directory containing 'examples' subdirectory.")
    args = parser.parse_args()

    root = args.root_dir
    examples_dir = root / "examples"
    index_csv = root / "index.csv"
    
    if not examples_dir.exists():
        print(f"Directory not found: {examples_dir}")
        return
        
    print(f"Scanning {examples_dir}...")
    files = sorted(list(examples_dir.glob("*.npz")))
    print(f"Found {len(files)} NPZ files.")
    
    with index_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["npz_path"])
        writer.writeheader()
        for p in files:
            # Path relative to root (where index.csv is)
            # root/examples/foo.npz -> examples/foo.npz
            rel_path = f"examples/{p.name}"
            writer.writerow({"npz_path": rel_path})
            
    print(f"Wrote {index_csv}")

if __name__ == "__main__":
    main()

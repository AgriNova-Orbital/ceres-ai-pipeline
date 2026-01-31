
import numpy as np
from pathlib import Path

def check_data():
    files = list(Path("data/wheat_risk/stage1_v2/examples").glob("*.npz"))
    if not files:
        print("No NPZ files found.")
        return

    print(f"Checking {len(files)} files...")
    
    n_nan_x = 0
    n_nan_y = 0
    max_val = -float('inf')
    min_val = float('inf')

    for i, f in enumerate(files):
        try:
            data = np.load(f)
            X = data["X"]
            y = data["y"]
            
            if np.isnan(X).any():
                n_nan_x += 1
            if np.isnan(y).all(): # If ALL labels are NaN (masked), that's okay/handled, but good to know
                n_nan_y += 1
                
            curr_max = np.nanmax(X)
            curr_min = np.nanmin(X)
            if curr_max > max_val: max_val = curr_max
            if curr_min < min_val: min_val = curr_min
            
            if i % 500 == 0:
                print(f"Scanned {i}/{len(files)}...")
        except Exception as e:
            print(f"Error reading {f}: {e}")

    print(f"Done. Files with NaN X: {n_nan_x}")
    print(f"Files with ALL NaN y: {n_nan_y}")
    print(f"Global X min/max: {min_val} / {max_val}")

if __name__ == "__main__":
    check_data()

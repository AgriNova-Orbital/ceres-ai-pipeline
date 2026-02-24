#!/usr/bin/env python3
"""
Wheat Risk Model - Demonstration Script
=======================================

This script demonstrates the trained model's ability to predict wheat rust risk
based on satellite time-series data.

It performs the following steps:
1. Loads a trained model checkpoint (e.g., Stage 3).
2. Loads a random sample from the validation dataset.
3. Runs the model to predict risk scores for each week.
4. Visualizes the results:
   - A time-series plot of Predicted Risk vs Ground Truth.
   - A sequence of NDVI heatmaps showing the field's health over time.
"""

import argparse
import random
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import torch
from torch.utils.data import DataLoader

# Ensure modules are importable
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from modules.wheat_risk.dataset import WheatRiskNpzSequenceDataset
from modules.wheat_risk.model import CnnLstmRisk

def _import_torch() -> Any:
    return torch

def demo(args):
    device = torch.device(args.device)
    print(f"🚀 Starting Demo on {device}...")

    # 1. Load Dataset
    print(f"📂 Loading dataset index: {args.index_csv}")
    if not args.index_csv.exists():
        print(f"❌ Error: Index file not found: {args.index_csv}")
        print("   Did you run the data build script?")
        sys.exit(1)

    ds = WheatRiskNpzSequenceDataset(index_csv=args.index_csv)
    print(f"   Found {len(ds)} samples.")

    # 2. Pick a Sample
    idx = args.sample_idx
    if idx < 0:
        idx = random.randint(0, len(ds) - 1)
    
    print(f"🔍 Inspecting Sample #{idx}...")
    x, y = ds[idx]  # x: (T, C, H, W), y: (T,)
    
    # 3. Load Model
    print(f"🧠 Loading model checkpoint: {args.checkpoint}")
    if not args.checkpoint.exists():
        print(f"❌ Error: Checkpoint not found: {args.checkpoint}")
        sys.exit(1)

    # Infer input channels from data
    T, C, H, W = x.shape
    model = CnnLstmRisk(in_channels=C, embed_dim=args.embed_dim, hidden_dim=args.hidden_dim)
    
    # Load weights
    state = torch.load(args.checkpoint, map_location=device)
    model.load_state_dict(state)
    model.to(device)
    model.eval()

    # 4. Inference
    print("🔮 Running inference...")
    # Add batch dim: (1, T, C, H, W)
    x_tensor = torch.from_numpy(x).unsqueeze(0).to(device)
    
    with torch.no_grad():
        logits = model(x_tensor) # (1, T)
        probs = torch.sigmoid(logits).cpu().numpy()[0] # (T,)

    # 5. Visualization
    print("📊 Generating visualization...")
    
    weeks = range(1, T + 1)
    
    # Setup plot
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(3, 1, height_ratios=[2, 1, 1])
    
    # Subplot 1: Risk Curve
    ax_curve = fig.add_subplot(gs[0])
    ax_curve.plot(weeks, probs, 'b-o', linewidth=2, label='Predicted Risk')
    
    # Handle NaN in ground truth for plotting
    y_clean = y.copy()
    mask = ~np.isnan(y)
    if mask.any():
        ax_curve.plot(np.array(weeks)[mask], y[mask], 'r--x', linewidth=1, alpha=0.7, label='Ground Truth (Avg)')
    else:
        ax_curve.text(0.5, 0.5, "(No Ground Truth Data)", transform=ax_curve.transAxes, ha='center', alpha=0.5)

    ax_curve.set_title(f"Wheat Rust Risk Evolution (Sample #{idx})", fontsize=16)
    ax_curve.set_ylabel("Risk Probability (0-1)", fontsize=12)
    ax_curve.set_xlabel("Week", fontsize=12)
    ax_curve.set_ylim(-0.05, 1.05)
    ax_curve.grid(True, alpha=0.3)
    ax_curve.legend()

    # Subplot 2 & 3: NDVI Imagery (thumbnails)
    # We'll show the sequence of NDVI images (Channel 0)
    # If T is large (18), we split into 2 rows.
    
    # Helper to plot a strip of images
    def plot_strip(row_idx, start_t, end_t):
        n = end_t - start_t
        if n <= 0: return
        inner_gs = gs[row_idx].subgridspec(1, n, wspace=0.1)
        for i in range(n):
            t_step = start_t + i
            ax = fig.add_subplot(inner_gs[i])
            
            # Get NDVI (Channel 0)
            ndvi = x[t_step, 0, :, :] # (H, W)
            
            im = ax.imshow(ndvi, cmap='RdYlGn', vmin=-1, vmax=1) # Red (Soil) -> Green (Crop)
            ax.axis('off')
            ax.set_title(f"W{t_step+1}\nP={probs[t_step]:.2f}", fontsize=8)

    mid = (T + 1) // 2
    plot_strip(1, 0, mid)
    plot_strip(2, mid, T)

    plt.tight_layout()
    
    out_file = args.output
    plt.savefig(out_file, dpi=150)
    print(f"✅ Demo result saved to: {out_file}")
    
    # Try to open it automatically on Windows
    import os
    if os.name == 'nt':
        os.startfile(out_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wheat Risk Model Demo")
    parser.add_argument("--checkpoint", type=Path, default=Path("checkpoints/stage3/model_seed1.pt"), help="Model checkpoint path")
    parser.add_argument("--index-csv", type=Path, default=Path("data/wheat_risk/stage3/index.csv"), help="Dataset index CSV")
    parser.add_argument("--sample-idx", type=int, default=-1, help="Index of sample to inspect (-1 for random)")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--output", type=str, default="demo_result.png", help="Output image file")
    
    # Model config (must match training)
    parser.add_argument("--embed-dim", type=int, default=64)
    parser.add_argument("--hidden-dim", type=int, default=128)

    args = parser.parse_args()
    demo(args)

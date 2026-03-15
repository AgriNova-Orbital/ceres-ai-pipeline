"""Tests for the NDVI forecast training pipeline components.

Covers:
- NdviForecastDataset: loading scalar-y NPZ format
- CnnLstmRegressor: forward pass shape and scalar output
- train_ndvi_forecast.py: end-to-end CLI smoke test
"""
import csv
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ndvi_npz(out_dir: Path, name: str, *, W: int, C: int, H: int, width: int, y_val: float = 0.5):
    """Write one NDVI-forecast-format NPZ file."""
    X = np.random.rand(W, C, H, width).astype(np.float32)
    M = np.ones((W, 1, H, width), dtype=np.float32)
    X_full = np.concatenate([X, M], axis=1)  # (W, C+1, H, width)
    y = np.float32(y_val)
    np.savez_compressed(out_dir / name, X=X_full, y=y, M=M)
    return name


def _make_dataset(tmp_path: Path, n: int = 5, *, W: int = 4, C: int = 10, H: int = 8, width: int = 8):
    """Create a minimal NDVI forecast dataset directory."""
    examples = tmp_path / "examples"
    examples.mkdir()
    names = []
    for i in range(n):
        name = f"patch_{i:03d}.npz"
        _make_ndvi_npz(examples, name, W=W, C=C, H=H, width=width, y_val=0.3 + 0.1 * i)
        names.append(f"examples/{name}")

    index_csv = tmp_path / "index.csv"
    with index_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["npz_path"])
        w.writeheader()
        for npz_name in names:
            w.writerow({"npz_path": npz_name})

    return index_csv


# ---------------------------------------------------------------------------
# NdviForecastDataset
# ---------------------------------------------------------------------------

class TestNdviForecastDataset:
    def test_len_matches_index(self, tmp_path):
        from modules.wheat_risk.dataset import NdviForecastDataset

        _make_dataset(tmp_path, n=3)
        ds = NdviForecastDataset(index_csv=tmp_path / "index.csv")
        assert len(ds) == 3

    def test_x_shape(self, tmp_path):
        from modules.wheat_risk.dataset import NdviForecastDataset

        _make_dataset(tmp_path, n=1, W=4, C=10, H=8, width=8)
        ds = NdviForecastDataset(index_csv=tmp_path / "index.csv")
        x, y = ds[0]
        assert x.ndim == 4
        assert x.shape == (4, 11, 8, 8)  # C+1 = 11

    def test_y_is_scalar(self, tmp_path):
        from modules.wheat_risk.dataset import NdviForecastDataset

        _make_dataset(tmp_path, n=1)
        ds = NdviForecastDataset(index_csv=tmp_path / "index.csv")
        _, y = ds[0]
        assert y.ndim == 0

    def test_y_value(self, tmp_path):
        from modules.wheat_risk.dataset import NdviForecastDataset

        examples = tmp_path / "examples"
        examples.mkdir()
        _make_ndvi_npz(examples, "p.npz", W=4, C=10, H=8, width=8, y_val=0.42)
        index_csv = tmp_path / "index.csv"
        with index_csv.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["npz_path"])
            w.writeheader()
            w.writerow({"npz_path": "examples/p.npz"})

        ds = NdviForecastDataset(index_csv=index_csv)
        _, y = ds[0]
        assert float(y) == pytest.approx(0.42, abs=1e-6)

    def test_nan_y_loads_as_nan(self, tmp_path):
        from modules.wheat_risk.dataset import NdviForecastDataset

        examples = tmp_path / "examples"
        examples.mkdir()
        _make_ndvi_npz(examples, "p.npz", W=4, C=10, H=8, width=8, y_val=float("nan"))
        index_csv = tmp_path / "index.csv"
        with index_csv.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["npz_path"])
            w.writeheader()
            w.writerow({"npz_path": "examples/p.npz"})

        ds = NdviForecastDataset(index_csv=index_csv)
        _, y = ds[0]
        assert torch.isnan(y)

    def test_rejects_sequence_y(self, tmp_path):
        """Scalar dataset should reject sequence (T,) y arrays."""
        from modules.wheat_risk.dataset import NdviForecastDataset

        examples = tmp_path / "examples"
        examples.mkdir()
        X = np.random.rand(4, 11, 8, 8).astype(np.float32)
        y = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)  # (T,) not scalar
        np.savez_compressed(examples / "bad.npz", X=X, y=y)
        index_csv = tmp_path / "index.csv"
        with index_csv.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["npz_path"])
            w.writeheader()
            w.writerow({"npz_path": "examples/bad.npz"})

        ds = NdviForecastDataset(index_csv=index_csv)
        with pytest.raises(ValueError, match="scalar"):
            ds[0]


# ---------------------------------------------------------------------------
# CnnLstmRegressor
# ---------------------------------------------------------------------------

class TestCnnLstmRegressor:
    def test_forward_shape(self):
        from modules.wheat_risk.model import CnnLstmRegressor

        b, t, c, h, w = 2, 4, 11, 8, 8
        x = torch.randn(b, t, c, h, w, dtype=torch.float32)
        model = CnnLstmRegressor(in_channels=c, embed_dim=32, hidden_dim=64)
        y = model(x)
        assert tuple(y.shape) == (b,)

    def test_output_is_finite(self):
        from modules.wheat_risk.model import CnnLstmRegressor

        b, t, c, h, w = 4, 4, 11, 8, 8
        x = torch.randn(b, t, c, h, w, dtype=torch.float32)
        model = CnnLstmRegressor(in_channels=c, embed_dim=32, hidden_dim=64)
        y = model(x)
        assert torch.isfinite(y).all()

    def test_single_sample(self):
        from modules.wheat_risk.model import CnnLstmRegressor

        x = torch.randn(1, 4, 11, 8, 8, dtype=torch.float32)
        model = CnnLstmRegressor(in_channels=11, embed_dim=16, hidden_dim=32)
        y = model(x)
        assert tuple(y.shape) == (1,)


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

class TestTrainNdviForecastCLI:
    def test_help(self):
        result = subprocess.run(
            [sys.executable, "scripts/train_ndvi_forecast.py", "--help"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert result.returncode == 0
        assert "NDVI" in result.stdout

    def test_end_to_end(self, tmp_path):
        index_csv = _make_dataset(tmp_path, n=8, W=4, C=10, H=8, width=8)
        save_path = tmp_path / "model.pt"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/train_ndvi_forecast.py",
                "--index-csv", str(index_csv),
                "--root-dir", str(tmp_path),
                "--epochs", "2",
                "--batch-size", "4",
                "--device", "cpu",
                "--seed", "42",
                "--save-path", str(save_path),
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
        assert save_path.exists()
        assert "epoch 1/2" in result.stdout
        assert "epoch 2/2" in result.stdout

    def test_load_and_continue(self, tmp_path):
        index_csv = _make_dataset(tmp_path, n=8, W=4, C=10, H=8, width=8)
        save_path = tmp_path / "model.pt"

        # First run: train and save
        subprocess.run(
            [
                sys.executable,
                "scripts/train_ndvi_forecast.py",
                "--index-csv", str(index_csv),
                "--root-dir", str(tmp_path),
                "--epochs", "1",
                "--batch-size", "4",
                "--device", "cpu",
                "--save-path", str(save_path),
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
            check=True,
        )
        assert save_path.exists()

        # Second run: load and continue
        result = subprocess.run(
            [
                sys.executable,
                "scripts/train_ndvi_forecast.py",
                "--index-csv", str(index_csv),
                "--root-dir", str(tmp_path),
                "--epochs", "1",
                "--batch-size", "4",
                "--device", "cpu",
                "--load-path", str(save_path),
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

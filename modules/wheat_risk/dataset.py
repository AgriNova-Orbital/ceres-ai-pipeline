from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


def _import_torch() -> Any:
    try:
        import torch  # type: ignore

        return torch
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "PyTorch is required for wheat risk datasets. Install it (e.g. `uv sync --extra ml`)"
        ) from e


@dataclass(frozen=True, slots=True)
class NpzSequenceExample:
    npz_path: Path


def _read_index_csv(index_csv: Path) -> list[NpzSequenceExample]:
    rows: list[NpzSequenceExample] = []
    with index_csv.open(newline="") as f:
        reader = csv.reader(f)
        first = next(reader, None)
        if first is None:
            raise ValueError(f"Empty index CSV: {index_csv}")

        header = [c.strip().lower() for c in first]
        if any(h in {"path", "npz", "npz_path", "file", "filename"} for h in header):
            # Header row; map first recognized column.
            col = None
            for i, h in enumerate(header):
                if h in {"path", "npz", "npz_path", "file", "filename"}:
                    col = i
                    break
            if col is None:
                raise ValueError(
                    f"Could not determine NPZ path column from header in {index_csv}: {first}"
                )
        else:
            # No header.
            col = 0
            p0 = first[col].strip()
            if p0:
                rows.append(NpzSequenceExample(npz_path=Path(p0)))

        for r in reader:
            if not r:
                continue
            p = (r[col] if col < len(r) else "").strip()
            if not p:
                continue
            rows.append(NpzSequenceExample(npz_path=Path(p)))

    return rows


class WheatRiskNpzSequenceDataset:
    """Dataset of NPZ sequences for wheat risk training.

    Each NPZ must contain:
    - X: (T, C, H, W)
    - y: (T,)
    """

    def __init__(
        self, index_csv: str | Path, root_dir: str | Path | None = None
    ) -> None:
        self.index_csv = Path(index_csv)
        self.root_dir = (
            Path(root_dir) if root_dir is not None else self.index_csv.parent
        )

        if not self.index_csv.exists():
            raise FileNotFoundError(self.index_csv)

        self.examples = _read_index_csv(self.index_csv)
        if not self.examples:
            raise ValueError(f"No examples found in {self.index_csv}")

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int):
        torch = _import_torch()

        ex = self.examples[idx]
        p = ex.npz_path
        if not p.is_absolute():
            p = self.root_dir / p

        with np.load(p, allow_pickle=False) as z:
            if "X" not in z or "y" not in z:
                raise KeyError(f"NPZ must contain arrays 'X' and 'y': {p}")
            x = z["X"]
            y = z["y"]

        if x.ndim != 4:
            raise ValueError(f"X must have shape (T, C, H, W), got {x.shape} from {p}")
        if y.ndim != 1:
            raise ValueError(f"y must have shape (T,), got {y.shape} from {p}")
        if x.shape[0] != y.shape[0]:
            raise ValueError(
                f"X and y must agree on T; got X.T={x.shape[0]} y.T={y.shape[0]} from {p}"
            )

        x_t = torch.from_numpy(np.asarray(x)).to(dtype=torch.float32)
        y_t = torch.from_numpy(np.asarray(y)).to(dtype=torch.float32)
        return x_t, y_t


class NdviForecastDataset:
    """Dataset of NPZ samples for NDVI forecasting (scalar regression).

    Each NPZ must contain:
    - X: (W, C, H, W) — W input weeks of feature bands (+ mask channel)
    - y: scalar float32 — next-week mean NDVI
    """

    def __init__(
        self, index_csv: str | Path, root_dir: str | Path | None = None
    ) -> None:
        self.index_csv = Path(index_csv)
        self.root_dir = (
            Path(root_dir) if root_dir is not None else self.index_csv.parent
        )

        if not self.index_csv.exists():
            raise FileNotFoundError(self.index_csv)

        self.examples = _read_index_csv(self.index_csv)
        if not self.examples:
            raise ValueError(f"No examples found in {self.index_csv}")

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int):
        torch = _import_torch()

        ex = self.examples[idx]
        p = ex.npz_path
        if not p.is_absolute():
            p = self.root_dir / p

        with np.load(p, allow_pickle=False) as z:
            if "X" not in z or "y" not in z:
                raise KeyError(f"NPZ must contain arrays 'X' and 'y': {p}")
            x = z["X"]
            y = z["y"]

        if x.ndim != 4:
            raise ValueError(f"X must have shape (W, C, H, W), got {x.shape} from {p}")
        if y.ndim != 0:
            raise ValueError(f"y must be a scalar, got shape {y.shape} from {p}")

        x_t = torch.from_numpy(np.asarray(x)).to(dtype=torch.float32)
        y_t = torch.tensor(float(y), dtype=torch.float32)
        return x_t, y_t

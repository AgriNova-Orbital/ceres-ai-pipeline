from __future__ import annotations

import csv
from bisect import bisect_right
from collections import OrderedDict
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


@dataclass(frozen=True, slots=True)
class ShardedNpzShard:
    shard_path: Path
    num_samples: int
    split: str | None


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


def _read_sharded_index_csv(
    index_csv: Path, *, split: str | None = None
) -> list[ShardedNpzShard]:
    rows: list[ShardedNpzShard] = []
    with index_csv.open(newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Empty index CSV: {index_csv}")

        fieldnames = {name.strip() for name in reader.fieldnames}
        missing = {"shard_path", "num_samples"} - fieldnames
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise ValueError(f"Missing required columns in {index_csv}: {missing_list}")
        if split is not None and "split" not in fieldnames:
            raise ValueError(f"Missing required column in {index_csv}: split")

        for row in reader:
            row_split = (row.get("split") or "").strip() or None
            if split is not None and row_split != split:
                continue

            shard_path = (row.get("shard_path") or "").strip()
            if not shard_path:
                continue
            num_samples = int((row.get("num_samples") or "0").strip())
            if num_samples <= 0:
                continue
            rows.append(
                ShardedNpzShard(
                    shard_path=Path(shard_path),
                    num_samples=num_samples,
                    split=row_split,
                )
            )
    return rows


class WheatRiskShardedNpzDataset:
    """Dataset backed by shard-level NPZ files.

    Each shard must contain:
    - X: (N, C, H, W)
    - y: (N,)
    - valid_mask: (N, H, W), required only when return_mask=True
    """

    def __init__(
        self,
        index_csv: str | Path,
        root_dir: str | Path | None = None,
        *,
        split: str | None = None,
        return_mask: bool = False,
        cache_size: int = 2,
    ) -> None:
        self.index_csv = Path(index_csv)
        self.root_dir = (
            Path(root_dir) if root_dir is not None else self.index_csv.parent
        )
        self.split = split
        self.return_mask = bool(return_mask)
        self.cache_size = max(0, int(cache_size))
        self._cache: OrderedDict[Path, dict[str, np.ndarray]] = OrderedDict()

        if not self.index_csv.exists():
            raise FileNotFoundError(self.index_csv)

        self.shards = _read_sharded_index_csv(self.index_csv, split=split)
        if not self.shards:
            suffix = f" for split={split!r}" if split is not None else ""
            raise ValueError(f"No shard rows found in {self.index_csv}{suffix}")

        total = 0
        self._cumulative: list[int] = []
        for shard in self.shards:
            total += int(shard.num_samples)
            self._cumulative.append(total)

    def __len__(self) -> int:
        return self._cumulative[-1]

    def _resolve_shard_path(self, shard_path: Path) -> Path:
        if shard_path.is_absolute():
            return shard_path
        return self.root_dir / shard_path

    def _load_shard(self, shard_path: Path) -> dict[str, np.ndarray]:
        path = self._resolve_shard_path(shard_path)
        if self.cache_size > 0 and path in self._cache:
            arrays = self._cache.pop(path)
            self._cache[path] = arrays
            return arrays

        with np.load(path, allow_pickle=False) as z:
            required = {"X", "y"}
            if self.return_mask:
                required.add("valid_mask")
            missing = required - set(z.files)
            if missing:
                missing_list = ", ".join(sorted(missing))
                raise KeyError(f"Shard missing required arrays {missing_list}: {path}")

            arrays = {key: np.asarray(z[key]) for key in required}

        x = arrays["X"]
        y = arrays["y"]
        if x.ndim != 4:
            raise ValueError(f"X must have shape (N, C, H, W), got {x.shape}: {path}")
        if y.ndim != 1:
            raise ValueError(f"y must have shape (N,), got {y.shape}: {path}")
        if x.shape[0] != y.shape[0]:
            raise ValueError(
                f"X and y must agree on N; got X.N={x.shape[0]} y.N={y.shape[0]}: {path}"
            )
        if self.return_mask:
            mask = arrays["valid_mask"]
            if mask.ndim != 3:
                raise ValueError(
                    f"valid_mask must have shape (N, H, W), got {mask.shape}: {path}"
                )
            if mask.shape[0] != x.shape[0]:
                raise ValueError(
                    "valid_mask and X must agree on N; "
                    f"got mask.N={mask.shape[0]} X.N={x.shape[0]}: {path}"
                )

        if self.cache_size > 0:
            self._cache[path] = arrays
            while len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)

        return arrays

    def __getitem__(self, idx: int):
        torch = _import_torch()

        n = len(self)
        if idx < 0:
            idx += n
        if idx < 0 or idx >= n:
            raise IndexError(idx)

        shard_idx = bisect_right(self._cumulative, idx)
        prev = 0 if shard_idx == 0 else self._cumulative[shard_idx - 1]
        local_idx = idx - prev
        shard = self.shards[shard_idx]
        arrays = self._load_shard(shard.shard_path)

        x = arrays["X"][local_idx]
        y = arrays["y"][local_idx]

        x_t = torch.from_numpy(np.asarray(x)).to(dtype=torch.float32)
        y_t = torch.from_numpy(np.asarray(y)).to(dtype=torch.float32)

        if not self.return_mask:
            return x_t, y_t

        mask = arrays["valid_mask"][local_idx]
        mask_t = torch.from_numpy(np.asarray(mask)).to(dtype=torch.bool)
        return x_t, y_t, mask_t

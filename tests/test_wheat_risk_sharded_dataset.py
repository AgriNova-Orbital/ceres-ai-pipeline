from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest


class _FakeTensor:
    def __init__(self, array: np.ndarray) -> None:
        self.array = np.asarray(array)

    @property
    def shape(self) -> tuple[int, ...]:
        return self.array.shape

    @property
    def dtype(self):
        return self.array.dtype.type

    def to(self, *, dtype):
        return _FakeTensor(self.array.astype(dtype))

    def flatten(self):
        return _FakeTensor(self.array.flatten())

    def __getitem__(self, idx):
        return _FakeTensor(self.array[idx])

    def item(self):
        return self.array.item()


class _FakeTorch:
    float32 = np.float32
    bool = np.bool_

    @staticmethod
    def from_numpy(array: np.ndarray) -> _FakeTensor:
        return _FakeTensor(array)


def _write_shard(
    root: Path,
    relpath: str,
    *,
    start_value: float,
    num_samples: int,
    patch_size: int,
    split: str,
) -> None:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)

    x = np.arange(
        start_value,
        start_value + num_samples * 10 * patch_size * patch_size,
        dtype=np.float32,
    ).reshape(num_samples, 10, patch_size, patch_size)
    y = np.linspace(start_value, start_value + num_samples - 1, num_samples).astype(
        np.float32
    )
    valid_mask = np.ones((num_samples, patch_size, patch_size), dtype=bool)

    np.savez_compressed(
        path,
        X=x,
        y=y,
        valid_mask=valid_mask,
        week_key=np.asarray(["2025W36"] * num_samples),
        tile_key=np.asarray(["r0000000000_c0000000000"] * num_samples),
        tile_id=np.zeros((num_samples,), dtype=np.int16),
        split=np.asarray([split] * num_samples),
        row=np.arange(num_samples, dtype=np.int32),
        col=np.arange(num_samples, dtype=np.int32),
        patch_size=np.asarray(patch_size, dtype=np.int16),
    )


def _write_index(root: Path, rows: list[dict[str, object]]) -> Path:
    index_csv = root / "index.csv"
    with index_csv.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "shard_path",
                "patch_size",
                "num_samples",
                "week_key",
                "tile_key",
                "tile_id",
                "split",
                "row_start",
                "row_end",
                "col_offset",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return index_csv


def test_sharded_dataset_indexes_samples_across_shards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import modules.wheat_risk.dataset as dataset_module

    monkeypatch.setattr(dataset_module, "_import_torch", lambda: _FakeTorch)
    WheatRiskShardedNpzDataset = dataset_module.WheatRiskShardedNpzDataset

    _write_shard(
        tmp_path,
        "shards/train_a.npz",
        start_value=0,
        num_samples=2,
        patch_size=4,
        split="train",
    )
    _write_shard(
        tmp_path,
        "shards/train_b.npz",
        start_value=1000,
        num_samples=3,
        patch_size=4,
        split="train",
    )
    index_csv = _write_index(
        tmp_path,
        [
            {
                "shard_path": "shards/train_a.npz",
                "patch_size": 4,
                "num_samples": 2,
                "week_key": "2025W36",
                "tile_key": "tile-a",
                "tile_id": 0,
                "split": "train",
                "row_start": 0,
                "row_end": 3,
                "col_offset": 0,
            },
            {
                "shard_path": "shards/train_b.npz",
                "patch_size": 4,
                "num_samples": 3,
                "week_key": "2025W36",
                "tile_key": "tile-b",
                "tile_id": 1,
                "split": "train",
                "row_start": 0,
                "row_end": 3,
                "col_offset": 0,
            },
        ],
    )

    dataset = WheatRiskShardedNpzDataset(index_csv)

    assert len(dataset) == 5
    x0, y0 = dataset[0]
    x3, y3 = dataset[3]
    assert tuple(x0.shape) == (10, 4, 4)
    assert y0.shape == ()
    assert float(y0.item()) == 0.0
    assert float(x3.flatten()[0].item()) == pytest.approx(1160.0)
    assert float(y3.item()) == pytest.approx(1001.0)


def test_sharded_dataset_filters_by_split_and_can_return_mask(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import modules.wheat_risk.dataset as dataset_module

    monkeypatch.setattr(dataset_module, "_import_torch", lambda: _FakeTorch)
    WheatRiskShardedNpzDataset = dataset_module.WheatRiskShardedNpzDataset

    _write_shard(
        tmp_path,
        "shards/train.npz",
        start_value=0,
        num_samples=2,
        patch_size=4,
        split="train",
    )
    _write_shard(
        tmp_path,
        "shards/val.npz",
        start_value=100,
        num_samples=1,
        patch_size=4,
        split="val",
    )
    index_csv = _write_index(
        tmp_path,
        [
            {
                "shard_path": "shards/train.npz",
                "patch_size": 4,
                "num_samples": 2,
                "week_key": "2025W36",
                "tile_key": "tile-a",
                "tile_id": 0,
                "split": "train",
                "row_start": 0,
                "row_end": 3,
                "col_offset": 0,
            },
            {
                "shard_path": "shards/val.npz",
                "patch_size": 4,
                "num_samples": 1,
                "week_key": "2025W36",
                "tile_key": "tile-b",
                "tile_id": 1,
                "split": "val",
                "row_start": 0,
                "row_end": 3,
                "col_offset": 0,
            },
        ],
    )

    dataset = WheatRiskShardedNpzDataset(index_csv, split="val", return_mask=True)

    assert len(dataset) == 1
    x, y, mask = dataset[0]
    assert tuple(x.shape) == (10, 4, 4)
    assert float(y.item()) == pytest.approx(100.0)
    assert tuple(mask.shape) == (4, 4)
    assert mask.dtype == np.bool_

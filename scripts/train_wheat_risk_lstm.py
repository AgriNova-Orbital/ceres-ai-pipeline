from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _seed_worker(worker_id: int, *, base_seed: int) -> None:
    # Keep worker seeding minimal: torch's per-worker seed is handled by DataLoader;
    # we only seed python/numpy for common transforms.
    import random

    import numpy as np

    s = int(base_seed) + int(worker_id)
    random.seed(s)
    np.random.seed(s)


def _import_torch() -> Any:
    try:
        import torch  # type: ignore

        return torch
    except ImportError as e:
        raise SystemExit(
            "PyTorch is required for training. Install it with `uv sync --extra ml` (or add "
            "torch to your environment), then re-run."
        ) from e


@dataclass(frozen=True, slots=True)
class TrainArgs:
    index_csv: Path
    root_dir: Path | None
    epochs: int
    batch_size: int
    lr: float
    embed_dim: int
    hidden_dim: int
    num_workers: int
    device: str
    max_invalid_ratio: float
    feature_abs_clip: float
    seed: int | None
    deterministic: bool
    save_path: Path | None
    load_path: Path | None


def _parse_args(argv: list[str] | None = None) -> TrainArgs:
    p = argparse.ArgumentParser(
        description=(
            "Train CNN+LSTM wheat risk baseline (seq2seq).\n\n"
            "⚠️  TARGET LEAKAGE WARNING\n"
            "Statistical analysis of the France 2025 GeoTIFF dataset shows that\n"
            "the risk band (band_last) equals 1 − NDVI (band_1) to within float32\n"
            "precision for every valid pixel. Training on these labels teaches the\n"
            "model the trivial identity 'risk = 1 − ndvi', not genuine predictive\n"
            "signal.\n\n"
            "This script expects y to be a (T,) sequence and trains with\n"
            "BCEWithLogitsLoss (binary classification). It is NOT compatible with\n"
            "the scalar-regression NDVI forecasting dataset produced by\n"
            "scripts/build_ndvi_forecast_dataset.py. For leakage-free NDVI\n"
            "forecasting, a dedicated regression training script is required."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--index-csv", type=Path, required=True, help="CSV with NPZ paths")
    p.add_argument(
        "--root-dir",
        type=Path,
        default=None,
        help="Optional root directory for relative NPZ paths",
    )
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--embed-dim", type=int, default=64)
    p.add_argument("--hidden-dim", type=int, default=128)
    p.add_argument("--num-workers", type=int, default=0)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument(
        "--max-invalid-ratio",
        type=float,
        default=0.5,
        help="Skip batches whose non-finite X ratio is above this threshold (0-1).",
    )
    p.add_argument(
        "--feature-abs-clip",
        type=float,
        default=1000.0,
        help="Clip absolute feature values after sanitization.",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional RNG seed for python/numpy/torch and DataLoader shuffling",
    )
    p.add_argument(
        "--deterministic",
        action="store_true",
        help="Enable cudnn deterministic settings when running on CUDA",
    )
    p.add_argument(
        "--save-path",
        type=Path,
        default=None,
        help="Save model checkpoint to this path",
    )
    p.add_argument(
        "--load-path",
        type=Path,
        default=None,
        help="Load model checkpoint from this path",
    )
    ns = p.parse_args(argv)

    if ns.epochs <= 0:
        raise SystemExit("--epochs must be > 0")
    if ns.batch_size <= 0:
        raise SystemExit("--batch-size must be > 0")
    if ns.lr <= 0:
        raise SystemExit("--lr must be > 0")
    if ns.embed_dim <= 0:
        raise SystemExit("--embed-dim must be > 0")
    if ns.hidden_dim <= 0:
        raise SystemExit("--hidden-dim must be > 0")
    if ns.num_workers < 0:
        raise SystemExit("--num-workers must be >= 0")
    if ns.max_invalid_ratio < 0.0 or ns.max_invalid_ratio > 1.0:
        raise SystemExit("--max-invalid-ratio must be between 0 and 1")
    if ns.feature_abs_clip <= 0:
        raise SystemExit("--feature-abs-clip must be > 0")

    return TrainArgs(
        index_csv=ns.index_csv,
        root_dir=ns.root_dir,
        epochs=ns.epochs,
        batch_size=ns.batch_size,
        lr=ns.lr,
        embed_dim=ns.embed_dim,
        hidden_dim=ns.hidden_dim,
        num_workers=ns.num_workers,
        device=ns.device,
        max_invalid_ratio=ns.max_invalid_ratio,
        feature_abs_clip=ns.feature_abs_clip,
        seed=ns.seed,
        deterministic=bool(ns.deterministic),
        save_path=ns.save_path,
        load_path=ns.load_path,
    )


def _sanitize_x_batch(xb: Any, *, torch_module: Any, abs_clip: float) -> Any:
    y = torch_module.nan_to_num(xb, nan=0.0, posinf=0.0, neginf=0.0)
    return torch_module.clamp(y, min=-float(abs_clip), max=float(abs_clip))


def _masked_loss_mean(
    per_elem: Any, valid_target_mask: Any, *, torch_module: Any
) -> Any | None:
    mask = valid_target_mask & torch_module.isfinite(per_elem)
    if not bool(mask.any().detach().cpu().item()):
        return None
    loss = per_elem[mask].mean()
    if not bool(torch_module.isfinite(loss).detach().cpu().item()):
        return None
    return loss


def _compute_masked_bce_loss(
    logits: Any,
    targets: Any,
    *,
    loss_fn: Any,
    torch_module: Any,
) -> Any | None:
    # BCE kernels can propagate NaN target values into gradient paths even when
    # later masked out. Replace invalid targets with 0 first, then apply mask.
    valid_target_mask = torch_module.isfinite(targets)
    if not bool(valid_target_mask.any().detach().cpu().item()):
        return None

    safe_targets = torch_module.where(
        valid_target_mask,
        targets,
        torch_module.zeros_like(targets),
    )
    per_elem = loss_fn(logits, safe_targets)
    return _masked_loss_mean(per_elem, valid_target_mask, torch_module=torch_module)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    torch = _import_torch()
    import functools

    from torch.utils.data import DataLoader

    from modules.wheat_risk.dataset import WheatRiskNpzSequenceDataset
    from modules.wheat_risk.model import CnnLstmRisk

    device = torch.device(args.device)
    if args.seed is not None:
        import random

        import numpy as np

        seed = int(args.seed)
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

    if args.deterministic and device.type == "cuda" and torch.cuda.is_available():
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    ds = WheatRiskNpzSequenceDataset(index_csv=args.index_csv, root_dir=args.root_dir)

    # Infer in_channels from the first sample.
    x0, y0 = ds[0]
    if x0.ndim != 4:
        raise SystemExit(f"Expected X to be (T,C,H,W), got {tuple(x0.shape)}")
    if y0.ndim != 1:
        raise SystemExit(f"Expected y to be (T,), got {tuple(y0.shape)}")
    in_channels = int(x0.shape[1])

    model = CnnLstmRisk(
        in_channels=in_channels, embed_dim=args.embed_dim, hidden_dim=args.hidden_dim
    )
    model.to(device)

    print(
        "train_wheat_risk_lstm | "
        f"device={device} seed={args.seed} deterministic={args.deterministic} "
        f"epochs={args.epochs} batch={args.batch_size} lr={args.lr} "
        f"workers={args.num_workers} max_invalid_ratio={args.max_invalid_ratio} "
        f"feature_abs_clip={args.feature_abs_clip} "
        f"index_csv={args.index_csv} root_dir={args.root_dir}"
    )

    generator = None
    worker_init_fn = None
    if args.seed is not None:
        generator = torch.Generator()
        generator.manual_seed(int(args.seed))
        if args.num_workers > 0:
            worker_init_fn = functools.partial(_seed_worker, base_seed=int(args.seed))

    dl = DataLoader(
        ds,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        generator=generator,
        worker_init_fn=worker_init_fn,
    )

    optim = torch.optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = torch.nn.BCEWithLogitsLoss(reduction="none")

    if args.load_path and args.load_path.exists():
        print(f"Loading checkpoint from {args.load_path}")
        # Use strict=False to allow flexibility if needed, but usually we want strict=True
        # We start with strict=True to ensure architecture matches.
        state = torch.load(args.load_path, map_location=device)
        model.load_state_dict(state)

    model.train()
    for epoch in range(1, args.epochs + 1):
        total_loss = 0.0
        n_batches = 0
        skipped_invalid_x = 0
        skipped_invalid_loss = 0
        skipped_invalid_grad = 0

        for xb, yb in dl:
            # xb: (B, T, C, H, W) because dataset returns (T,C,H,W) per item.
            xb = xb.to(device)
            yb = yb.to(device)
            if yb.dtype != torch.float32:
                yb = yb.float()

            # Measure the invalid-pixel ratio on the raw batch BEFORE sanitization
            # so that --max-invalid-ratio accurately reflects how corrupt the input
            # data is. After _sanitize_x_batch() replaces NaN/inf with 0, the ratio
            # would always be 0 and the check would be meaningless.
            invalid_ratio = float(
                (~torch.isfinite(xb)).float().mean().detach().cpu().item()
            )
            if invalid_ratio > float(args.max_invalid_ratio):
                skipped_invalid_x += 1
                continue

            xb = _sanitize_x_batch(
                xb,
                torch_module=torch,
                abs_clip=float(args.feature_abs_clip),
            )

            logits = model(xb)
            if logits.shape != yb.shape:
                raise RuntimeError(
                    f"Shape mismatch: logits={tuple(logits.shape)} y={tuple(yb.shape)}"
                )

            loss = _compute_masked_bce_loss(
                logits,
                yb,
                loss_fn=loss_fn,
                torch_module=torch,
            )
            if loss is None:
                skipped_invalid_loss += 1
                continue

            optim.zero_grad(set_to_none=True)
            loss.backward()

            grads_ok = True
            for p in model.parameters():
                if p.grad is None:
                    continue
                if not bool(torch.isfinite(p.grad).all().detach().cpu().item()):
                    grads_ok = False
                    break
            if not grads_ok:
                optim.zero_grad(set_to_none=True)
                skipped_invalid_grad += 1
                continue

            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optim.step()

            total_loss += float(loss.detach().cpu().item())
            n_batches += 1

        if n_batches == 0:
            raise SystemExit(
                "No valid batches this epoch after filtering; "
                "adjust --max-invalid-ratio or dataset quality filters."
            )
        avg = total_loss / max(n_batches, 1)
        if not bool(torch.isfinite(torch.tensor(avg)).detach().cpu().item()):
            raise SystemExit(
                "Encountered non-finite epoch loss; check data quality and NaN filters."
            )
        print(
            f"epoch {epoch}/{args.epochs} loss={avg:.6f} "
            f"skipped_x={skipped_invalid_x} skipped_loss={skipped_invalid_loss} "
            f"skipped_grad={skipped_invalid_grad}"
        )

    if args.save_path:
        print(f"Saving checkpoint to {args.save_path}")
        args.save_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), args.save_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

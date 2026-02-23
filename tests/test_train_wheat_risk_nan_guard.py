from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")


def test_sanitize_x_batch_replaces_non_finite_values() -> None:
    from scripts.train_wheat_risk_lstm import _sanitize_x_batch

    x = torch.tensor(
        [[[[[float("nan"), float("inf")], [float("-inf"), 1.0]]]]],
        dtype=torch.float32,
    )
    y = _sanitize_x_batch(x, torch_module=torch, abs_clip=1000.0)

    assert bool(torch.isfinite(y).all().detach().cpu().item())
    assert float(y[0, 0, 0, 0, 0].item()) == 0.0
    assert float(y[0, 0, 0, 0, 1].item()) == 0.0
    assert float(y[0, 0, 0, 1, 0].item()) == 0.0


def test_sanitize_x_batch_clips_extreme_values() -> None:
    from scripts.train_wheat_risk_lstm import _sanitize_x_batch

    x = torch.tensor([[[[[1.0e6, -1.0e6], [5.0, -5.0]]]]], dtype=torch.float32)
    y = _sanitize_x_batch(x, torch_module=torch, abs_clip=1000.0)

    assert float(y.max().detach().cpu().item()) <= 1000.0
    assert float(y.min().detach().cpu().item()) >= -1000.0


def test_masked_loss_mean_ignores_non_finite_entries() -> None:
    from scripts.train_wheat_risk_lstm import _masked_loss_mean

    per_elem = torch.tensor([[0.2, float("nan"), 0.6]], dtype=torch.float32)
    y = torch.tensor([[1.0, 0.0, float("nan")]], dtype=torch.float32)
    valid_mask = torch.isfinite(y)
    loss = _masked_loss_mean(per_elem, valid_mask, torch_module=torch)

    assert loss is not None
    assert float(loss.detach().cpu().item()) == pytest.approx(0.2)


def test_masked_loss_mean_returns_none_when_no_valid_values() -> None:
    from scripts.train_wheat_risk_lstm import _masked_loss_mean

    per_elem = torch.tensor([[float("nan"), float("nan")]], dtype=torch.float32)
    y = torch.tensor([[float("nan"), float("nan")]], dtype=torch.float32)
    valid_mask = torch.isfinite(y)

    assert _masked_loss_mean(per_elem, valid_mask, torch_module=torch) is None

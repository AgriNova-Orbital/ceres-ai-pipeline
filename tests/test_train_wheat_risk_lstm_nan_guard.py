from __future__ import annotations

import pytest


def test_compute_masked_bce_loss_keeps_grad_finite_with_nan_targets() -> None:
    torch = pytest.importorskip("torch")
    from scripts.train_wheat_risk_lstm import _compute_masked_bce_loss

    logits = torch.tensor([[0.5, -0.2, 1.1]], dtype=torch.float32, requires_grad=True)
    targets = torch.tensor([[1.0, float("nan"), 0.0]], dtype=torch.float32)
    loss_fn = torch.nn.BCEWithLogitsLoss(reduction="none")

    loss = _compute_masked_bce_loss(
        logits, targets, loss_fn=loss_fn, torch_module=torch
    )
    assert loss is not None
    assert bool(torch.isfinite(loss).item())

    loss.backward()
    assert logits.grad is not None
    assert bool(torch.isfinite(logits.grad).all().item())


def test_compute_masked_bce_loss_returns_none_when_all_targets_nan() -> None:
    torch = pytest.importorskip("torch")
    from scripts.train_wheat_risk_lstm import _compute_masked_bce_loss

    logits = torch.tensor([[0.5, -0.2, 1.1]], dtype=torch.float32)
    targets = torch.tensor(
        [[float("nan"), float("nan"), float("nan")]], dtype=torch.float32
    )
    loss_fn = torch.nn.BCEWithLogitsLoss(reduction="none")

    loss = _compute_masked_bce_loss(
        logits, targets, loss_fn=loss_fn, torch_module=torch
    )
    assert loss is None

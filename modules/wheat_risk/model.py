from __future__ import annotations

from typing import Any


def _import_torch() -> Any:
    try:
        import torch  # type: ignore

        return torch
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "PyTorch is required for wheat risk modeling. Install it (e.g. `uv sync --extra ml`)"
        ) from e


def _import_nn() -> Any:
    torch = _import_torch()
    return torch.nn


class _LazyTorchModuleMeta(type):
    """Metaclass that defers importing torch until instantiation.

    This lets `import modules.wheat_risk.model` succeed even when torch isn't
    installed, while still producing a real `torch.nn.Module` instance when the
    model is constructed.
    """

    _real_cls: type | None = None

    def _get_real_cls(cls) -> type:
        real = getattr(cls, "_real_cls", None)
        if real is not None:
            return real

        nn = _import_nn()

        class _Real(cls, nn.Module):  # type: ignore[misc]
            _torch_real = True

        cls._real_cls = _Real
        return _Real

    def __call__(cls, *args: Any, **kwargs: Any):
        if getattr(cls, "_torch_real", False):
            return super().__call__(*args, **kwargs)

        real_cls = cls._get_real_cls()
        return real_cls(*args, **kwargs)


class CnnLstmRisk(metaclass=_LazyTorchModuleMeta):
    """CNN+LSTM baseline for per-timestep risk logits.

    Input:  x (B, T, C, H, W)
    Output: y (B, T) logits
    """

    _torch_real = False

    def __init__(self, in_channels: int, embed_dim: int, hidden_dim: int) -> None:
        super().__init__()
        nn = _import_nn()

        if not isinstance(in_channels, int) or in_channels <= 0:
            raise ValueError("in_channels must be a positive int")
        if not isinstance(embed_dim, int) or embed_dim <= 0:
            raise ValueError("embed_dim must be a positive int")
        if not isinstance(hidden_dim, int) or hidden_dim <= 0:
            raise ValueError("hidden_dim must be a positive int")

        self.in_channels = in_channels
        self.embed_dim = embed_dim
        self.hidden_dim = hidden_dim

        self.cnn = nn.Sequential(
            nn.BatchNorm2d(in_channels),
            nn.Conv2d(in_channels, 16, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.proj = nn.Linear(32, embed_dim)
        self.lstm = nn.LSTM(
            input_size=embed_dim, hidden_size=hidden_dim, batch_first=True
        )
        self.head = nn.Linear(hidden_dim, 1)

    def forward(self, x: Any):
        torch = _import_torch()  # ensure torch is available

        if not hasattr(x, "shape"):
            raise TypeError("x must be a torch.Tensor")
        if x.ndim != 5:
            raise ValueError("x must have shape (B, T, C, H, W)")

        b, t, c, h, w = x.shape
        if c != self.in_channels:
            raise ValueError(
                f"x has C={int(c)}, but model was created with in_channels={self.in_channels}"
            )
        if h <= 0 or w <= 0:
            raise ValueError("H and W must be positive")

        x2 = x.reshape(b * t, c, h, w)
        # Fix data issues: fill NaNs, clamp outliers, then scale
        x2 = torch.nan_to_num(x2, nan=0.0, posinf=10000.0, neginf=-10000.0)
        x2 = torch.clamp(x2, min=-10000.0, max=10000.0)
        x2 = x2 / 1000.0
        feats = self.cnn(x2).reshape(b * t, -1)
        emb = self.proj(feats).reshape(b, t, self.embed_dim)
        out, _ = self.lstm(emb)
        logits = self.head(out).squeeze(-1)
        return logits

import pytest


torch = pytest.importorskip("torch")


def test_cnn_lstm_risk_forward_shapes():
    from modules.wheat_risk.model import CnnLstmRisk

    b, t, c, h, w = 2, 5, 3, 16, 16
    x = torch.randn(b, t, c, h, w, dtype=torch.float32)

    model = CnnLstmRisk(in_channels=c, embed_dim=32, hidden_dim=64)
    y = model(x)

    assert tuple(y.shape) == (b, t)

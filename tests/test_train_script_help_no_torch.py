import os
import subprocess
import sys


def test_train_script_help_does_not_require_torch():
    proc = subprocess.run(
        [sys.executable, "scripts/train_wheat_risk_lstm.py", "--help"],
        check=False,
        cwd=os.path.abspath(os.path.dirname(__file__) + "/.."),
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Train CNN+LSTM" in proc.stdout

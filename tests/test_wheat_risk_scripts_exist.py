import importlib.util
from pathlib import Path


def test_export_weekly_risk_rasters_script_importable_without_ee():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "export_weekly_risk_rasters.py"
    assert script_path.exists(), f"Missing script: {script_path}"

    spec = importlib.util.spec_from_file_location(
        "scripts.export_weekly_risk_rasters", script_path
    )
    assert spec is not None and spec.loader is not None

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert hasattr(mod, "main")

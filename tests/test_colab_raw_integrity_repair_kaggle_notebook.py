from __future__ import annotations

import json
from pathlib import Path


NOTEBOOK = Path("notebooks/colab_raw_integrity_repair_kaggle.ipynb")


def _sources() -> tuple[dict, str]:
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    sources = "\n".join("".join(cell.get("source", [])) for cell in nb["cells"])
    return nb, sources


def test_raw_integrity_repair_notebook_exists_with_expected_sections() -> None:
    assert NOTEBOOK.exists()
    nb, sources = _sources()

    assert nb["nbformat"] == 4
    assert "RAW_DIR = DRIVE_ROOT / \"wheat_data_v2.0-beta\"" in sources
    assert "REPORT_ROOT = DRIVE_ROOT / \"Ceres\" / \"raw_integrity_reports\"" in sources
    assert "REPAIR_ROOT = DRIVE_ROOT / \"Ceres\" / \"raw_repairs\"" in sources
    assert "scan_raw_batch" in sources
    assert "build_repair_candidates" in sources
    assert "Earth Engine repair export" in sources
    assert "plan_kaggle_shards" in sources


def test_raw_integrity_repair_notebook_code_cells_compile() -> None:
    nb, _ = _sources()
    for index, cell in enumerate(nb["cells"]):
        if cell.get("cell_type") == "code":
            compile("".join(cell.get("source", [])), f"{NOTEBOOK}:cell-{index}", "exec")


def test_raw_integrity_repair_notebook_does_not_embed_secrets() -> None:
    _, sources = _sources()
    forbidden = ("kaggle.json", "KAGGLE_KEY=", "ghp_", "sk_live_", "sk_test_", "Bearer ")
    for token in forbidden:
        assert token not in sources

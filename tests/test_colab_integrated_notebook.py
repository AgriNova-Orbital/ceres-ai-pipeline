from __future__ import annotations

import ast
import json
from pathlib import Path


NOTEBOOK = Path("notebooks/colab_raw_to_p128_kaggle_pipeline.ipynb")


def _notebook_sources() -> tuple[dict, str]:
    nb = json.loads(NOTEBOOK.read_text())
    sources = "\n".join("".join(cell.get("source", [])) for cell in nb["cells"])
    return nb, sources


def test_integrated_colab_notebook_exists_with_expected_config() -> None:
    assert NOTEBOOK.exists()
    nb, sources = _notebook_sources()

    assert nb["nbformat"] == 4
    assert 'RAW_DIR = DRIVE_ROOT / "wheat_data_v2.0-beta"' in sources
    assert 'OUTPUT_ROOT = DRIVE_ROOT / "Ceres" / "staged" / "2025w36_w52_grid_v1_p128"' in sources
    assert 'PATCH_SIZES = (128,)' in sources
    assert 'WEEK_START = "2025W36"' in sources
    assert 'WEEK_END = "2025W52"' in sources
    assert "scan_raw_integrity" in sources
    assert "run_patch_factory" in sources
    assert "sample_balanced_season_from_p128_tile_counts" in sources
    assert "kaggle datasets create" in sources


def test_integrated_colab_notebook_uses_drive_tmp_not_local_tmp() -> None:
    _nb, sources = _notebook_sources()

    assert "/content/ceres_tmp_shards" not in sources
    assert 'tmp_path = final_path.with_suffix(".tmp.npz")' in sources


def test_integrated_colab_notebook_markdown_has_no_literal_backslash_n() -> None:
    nb, _sources = _notebook_sources()

    for cell in nb["cells"]:
        if cell.get("cell_type") != "markdown":
            continue
        markdown = "".join(cell.get("source", []))
        assert "\\n" not in markdown


def test_integrated_colab_notebook_code_cells_compile() -> None:
    nb, _sources = _notebook_sources()

    for i, cell in enumerate(nb["cells"]):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        compile(source, f"{NOTEBOOK}:cell-{i}", "exec")


def test_raw_integrity_scan_buffers_csv_rows_instead_of_appending_per_file() -> None:
    nb, _sources = _notebook_sources()
    scan_function = None

    for cell in nb["cells"]:
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "scan_raw_integrity":
                scan_function = node
                break
        if scan_function is not None:
            break

    assert scan_function is not None
    append_calls = [
        node
        for node in ast.walk(scan_function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "append_csv"
    ]
    assert append_calls == []

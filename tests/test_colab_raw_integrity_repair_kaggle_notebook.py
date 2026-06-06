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


def test_raw_integrity_repair_notebook_sets_up_repo_before_importing_helpers() -> None:
    _, sources = _sources()

    import_index = sources.index("from modules.wheat_risk.raw_integrity import")
    setup_source = sources[:import_index]
    assert "CERES_REPO_URL" in setup_source
    assert "CERES_REPO_REF" in setup_source
    assert '"git", "clone"' in setup_source
    assert '"git", "-C", str(REPO_DIR), "fetch"' in setup_source
    assert '"git", "-C", str(REPO_DIR), "checkout", "FETCH_HEAD"' in setup_source
    assert "sys.path.insert(0, str(REPO_DIR))" in setup_source


def test_raw_integrity_repair_notebook_scans_once_after_completed_loop() -> None:
    _, sources = _sources()

    assert "\ncandidates = sorted(RAW_DIR.rglob(\"*.tif\"))" in sources
    assert "\nrecords = scan_raw_batch(selected, raw_root=RAW_DIR, read_sample=READ_SAMPLE)" in sources
    assert "\nbatch_path = next_batch_path(batch_dir)" in sources
    assert "\nall_records = load_scan_records(batch_dir)" in sources
    assert "write_summary_json(REPORT_ROOT / \"summary.json\", all_records)" in sources
    assert "build_repair_candidates(all_records" in sources


def test_raw_integrity_repair_notebook_curated_example_uses_all_scan_records() -> None:
    _, sources = _sources()

    assert "# all_records = load_scan_records(REPORT_ROOT / \"batches\")" in sources
    assert "# curated = build_curated_manifest(all_records" in sources

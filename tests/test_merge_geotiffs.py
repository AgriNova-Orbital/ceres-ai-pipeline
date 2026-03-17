from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


def test_group_split_files_recognizes_tile_suffixed_week_names(tmp_path: Path) -> None:
    from modules.merge_geotiffs import group_split_files

    names = [
        "fr_wheat_feat_2021W01-0000000000-0000000000.tif",
        "fr_wheat_feat_2021W01-0000009984-0000000000.tif",
        "fr_wheat_feat_2021W02-0000000000-0000000000.tif",
    ]
    for name in names:
        (tmp_path / name).touch()

    groups = group_split_files(tmp_path)

    assert sorted(groups) == ["2021W01", "2021W02"]
    assert [p.name for p in groups["2021W01"]] == names[:2]


def test_ingest_downloaded_geotiffs_moves_tiles_after_successful_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from modules.merge_geotiffs import ingest_downloaded_geotiffs

    tile_a = tmp_path / "fr_wheat_feat_2021W01-0000000000-0000000000.tif"
    tile_b = tmp_path / "fr_wheat_feat_2021W01-0000009984-0000000000.tif"
    tile_a.touch()
    tile_b.touch()

    calls: list[tuple[object, ...]] = []

    class FakeGdal:
        @staticmethod
        def BuildVRT(vrt_path: str, sources: list[str]):
            calls.append(("vrt", vrt_path, sources))
            Path(vrt_path).write_text("vrt", encoding="utf-8")

        @staticmethod
        def Translate(out_path: str, vrt_path: str, creationOptions: list[str]):
            calls.append(("translate", out_path, vrt_path, creationOptions))
            Path(out_path).write_text("merged", encoding="utf-8")

    monkeypatch.setattr("modules.merge_geotiffs._import_gdal", lambda: FakeGdal)
    monkeypatch.setattr(
        "modules.merge_geotiffs.validate_canonical_geotiff",
        lambda path: {"warnings": []},
    )

    result = ingest_downloaded_geotiffs(tmp_path)

    assert (tmp_path / "fr_wheat_feat_2021W01.tif").exists()
    assert (tmp_path / "_tiles" / "2021W01" / tile_a.name).exists()
    assert (tmp_path / "_tiles" / "2021W01" / tile_b.name).exists()
    assert result["merged_weeks"] == ["2021W01"]
    assert result["failed_weeks"] == []
    assert calls


def test_validate_canonical_geotiff_hard_fails_on_wrong_band_count(
    tmp_path: Path,
) -> None:
    import rasterio
    from rasterio.transform import from_origin

    from modules.merge_geotiffs import validate_canonical_geotiff

    tif_path = tmp_path / "fr_wheat_feat_2021W01.tif"
    with rasterio.open(
        tif_path,
        "w",
        driver="GTiff",
        width=4,
        height=4,
        count=10,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(0, 0, 1, 1),
        nodata=-32768,
    ) as dst:
        for idx in range(1, 11):
            dst.write(np.zeros((4, 4), dtype=np.float32), idx)

    with pytest.raises(RuntimeError, match="11 bands"):
        validate_canonical_geotiff(tif_path)


def test_validate_canonical_geotiff_warns_when_band_descriptions_missing(
    tmp_path: Path,
) -> None:
    import rasterio
    from rasterio.transform import from_origin

    from modules.merge_geotiffs import validate_canonical_geotiff

    tif_path = tmp_path / "fr_wheat_feat_2021W01.tif"
    with rasterio.open(
        tif_path,
        "w",
        driver="GTiff",
        width=4,
        height=4,
        count=11,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(0, 0, 1, 1),
        nodata=-32768,
    ) as dst:
        for idx in range(1, 12):
            dst.write(np.zeros((4, 4), dtype=np.float32), idx)

    report = validate_canonical_geotiff(tif_path)

    assert report["warnings"]

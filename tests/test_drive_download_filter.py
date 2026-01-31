from __future__ import annotations


def test_filter_weekly_geotiffs_sorts_and_filters():
    from modules.drive_download import filter_weekly_geotiffs

    files = [
        {"id": "1", "name": "notes.txt"},
        {"id": "2", "name": "fr_wheat_feat_2025W02.tif"},
        {"id": "3", "name": "fr_wheat_feat_2025W01.tif"},
        {"id": "4", "name": "fr_wheat_feat_2024W52.tif"},
        {"id": "5", "name": "fr_wheat_feat_2025W02.tif.aux.xml"},
        {"id": "6", "name": "fr_wheat_feat_2025_data_W03.tif"},
        {"id": "7", "name": "fr_wheat_feat_2025_data_W04.tif"},
        {"id": "8", "name": "fr_wheat_feat_2025_data_001.tif"},
    ]

    out = filter_weekly_geotiffs(files)
    assert [f["name"] for f in out] == [
        "fr_wheat_feat_2024W52.tif",
        "fr_wheat_feat_2025W01.tif",
        "fr_wheat_feat_2025W02.tif",
        "fr_wheat_feat_2025_data_W03.tif",
        "fr_wheat_feat_2025_data_W04.tif",
        "fr_wheat_feat_2025_data_001.tif",
    ]


def test_filter_weekly_geotiffs_numeric_suffix_is_descending_old_to_new():
    from modules.drive_download import filter_weekly_geotiffs

    files = [
        {"id": "1", "name": "fr_wheat_feat_2025_data_001.tif"},
        {"id": "2", "name": "fr_wheat_feat_2025_data_002.tif"},
        {"id": "3", "name": "fr_wheat_feat_2025_data_010.tif"},
    ]

    out = filter_weekly_geotiffs(files)
    assert [f["name"] for f in out] == [
        "fr_wheat_feat_2025_data_010.tif",
        "fr_wheat_feat_2025_data_002.tif",
        "fr_wheat_feat_2025_data_001.tif",
    ]

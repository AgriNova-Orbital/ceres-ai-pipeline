import importlib
import importlib.util
import sys
from types import SimpleNamespace

import pytest


def test_wheat_risk_masks_module_exists() -> None:
    assert importlib.util.find_spec("modules.wheat_risk.masks") is not None


def test_import_ee_raises_friendly_message(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = importlib.import_module("modules.wheat_risk.masks")

    def _boom(name: str) -> object:
        assert name == "ee"
        raise ImportError("no module named ee")

    monkeypatch.setattr(mod.importlib, "import_module", _boom)

    with pytest.raises(ImportError, match=r"Earth Engine|earthengine-api"):
        mod._import_ee()


def test_validate_bbox_accepts_sequence_and_normalizes() -> None:
    mod = importlib.import_module("modules.wheat_risk.masks")

    bbox = mod.validate_bbox([-1, 47, 6.5, 50.9])
    assert bbox == (-1.0, 47.0, 6.5, 50.9)
    assert isinstance(bbox, tuple)


def test_validate_bbox_accepts_numpy_scalars() -> None:
    mod = importlib.import_module("modules.wheat_risk.masks")
    import numpy as np

    bbox = mod.validate_bbox(
        [np.float64(-1), np.float64(47), np.float64(6.5), np.float64(50.9)]
    )
    assert bbox == (-1.0, 47.0, 6.5, 50.9)


@pytest.mark.parametrize(
    "bbox",
    [
        None,
        1,
        "-1,47,6,50",
        (1.0, 2.0, 3.0),
        (1.0, 2.0, 3.0, 4.0, 5.0),
        (1.0, "nope", 2.0, 3.0),
        (True, 0.0, 1.0, 2.0),
    ],
)
def test_validate_bbox_rejects_bad_shape_or_types(bbox: object) -> None:
    mod = importlib.import_module("modules.wheat_risk.masks")
    with pytest.raises(ValueError):
        mod.validate_bbox(bbox)  # type: ignore[arg-type]


def test_validate_bbox_rejects_inverted_or_degenerate_ranges() -> None:
    mod = importlib.import_module("modules.wheat_risk.masks")

    with pytest.raises(ValueError, match=r"min_lon < max_lon"):
        mod.validate_bbox((10.0, 0.0, 10.0, 1.0))

    with pytest.raises(ValueError, match=r"min_lat < max_lat"):
        mod.validate_bbox((0.0, 5.0, 1.0, 5.0))


@pytest.mark.parametrize(
    "bbox",
    [
        (-181.0, 0.0, 0.0, 1.0),
        (0.0, 0.0, 181.0, 1.0),
        (0.0, -91.0, 1.0, 0.0),
        (0.0, 0.0, 1.0, 91.0),
    ],
)
def test_validate_bbox_rejects_out_of_bounds(
    bbox: tuple[float, float, float, float],
) -> None:
    mod = importlib.import_module("modules.wheat_risk.masks")
    with pytest.raises(ValueError, match=r"latitude|longitude"):
        mod.validate_bbox(bbox)


def test_build_aoi_uses_ee_geometry_rectangle(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = importlib.import_module("modules.wheat_risk.masks")

    calls: list[tuple[str, object]] = []

    class _Geometry:
        @staticmethod
        def Rectangle(coords: object) -> object:
            calls.append(("Rectangle", coords))
            return ("rect", coords)

    fake_ee = SimpleNamespace(Geometry=_Geometry)
    monkeypatch.setitem(sys.modules, "ee", fake_ee)

    aoi = mod.build_aoi((-1.5, 47.0, 6.5, 50.9))
    assert aoi == ("rect", (-1.5, 47.0, 6.5, 50.9))
    assert calls == [("Rectangle", (-1.5, 47.0, 6.5, 50.9))]


def test_cropland_mask_worldcover_builds_class_40_mask(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = importlib.import_module("modules.wheat_risk.masks")
    collections = importlib.import_module("modules.wheat_risk.collections")

    log: list[tuple[str, object]] = []

    class _Image:
        def __init__(self, tag: str) -> None:
            self.tag = tag

        def select(self, band: str) -> "_Image":
            log.append(("select", band))
            return self

        def eq(self, value: int) -> "_Image":
            log.append(("eq", value))
            return self

        def selfMask(self) -> "_Image":
            log.append(("selfMask", self.tag))
            return self

        def clip(self, aoi: object) -> "_Image":
            log.append(("clip", aoi))
            return self

    class _ImageCollection:
        def __init__(self, cid: str) -> None:
            self.cid = cid
            log.append(("ImageCollection", cid))

        def filterBounds(self, aoi: object) -> "_ImageCollection":
            log.append(("filterBounds", aoi))
            return self

        def first(self) -> _Image:
            log.append(("first", self.cid))
            return _Image(tag=f"first:{self.cid}")

    fake_ee = SimpleNamespace(ImageCollection=_ImageCollection)
    monkeypatch.setitem(sys.modules, "ee", fake_ee)

    aoi = ("rect", (-1.5, 47.0, 6.5, 50.9))
    out = mod.cropland_mask_worldcover(aoi)
    assert isinstance(out, _Image)

    assert ("ImageCollection", collections.CollectionIds.WORLDCOVER) in log
    assert ("select", "Map") in log
    assert ("eq", 40) in log
    assert ("clip", aoi) in log


def test_cropland_mask_dynamicworld_builds_class_4_mask(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = importlib.import_module("modules.wheat_risk.masks")

    log: list[tuple[str, object]] = []

    class _Reducer:
        @staticmethod
        def mode() -> str:
            return "mode"

    class _Image:
        def select(self, band: str) -> "_Image":
            log.append(("select", band))
            return self

        def reduce(self, reducer: object) -> "_Image":
            log.append(("reduce", reducer))
            return self

        def eq(self, value: int) -> "_Image":
            log.append(("eq", value))
            return self

        def selfMask(self) -> "_Image":
            log.append(("selfMask", None))
            return self

        def clip(self, aoi: object) -> "_Image":
            log.append(("clip", aoi))
            return self

    class _ImageCollection:
        def __init__(self, cid: str) -> None:
            log.append(("ImageCollection", cid))

        def filterBounds(self, aoi: object) -> "_ImageCollection":
            log.append(("filterBounds", aoi))
            return self

        def filterDate(self, start: str, end: str) -> "_ImageCollection":
            log.append(("filterDate", (start, end)))
            return self

        def select(self, band: str) -> _Image:
            log.append(("collection.select", band))
            return _Image()

    fake_ee = SimpleNamespace(ImageCollection=_ImageCollection, Reducer=_Reducer)
    monkeypatch.setitem(sys.modules, "ee", fake_ee)

    aoi = ("rect", (-1.5, 47.0, 6.5, 50.9))
    out = mod.cropland_mask_dynamicworld(aoi, "2025-01-01", "2025-12-31")
    assert isinstance(out, _Image)

    assert ("ImageCollection", "GOOGLE/DYNAMICWORLD/V1") in log
    assert ("collection.select", "label") in log
    assert ("reduce", "mode") in log
    assert ("eq", 4) in log
    assert ("clip", aoi) in log


def test_get_cropland_mask_selects_dynamicworld_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = importlib.import_module("modules.wheat_risk.masks")
    cfg_mod = importlib.import_module("modules.wheat_risk.config")

    monkeypatch.setattr(mod, "build_aoi", lambda _bbox: "aoi")
    monkeypatch.setattr(mod, "cropland_mask_worldcover", lambda _aoi: "wc")
    monkeypatch.setattr(
        mod,
        "cropland_mask_dynamicworld",
        lambda _aoi, _start, _end: "dw",
    )

    stage = cfg_mod.StagePreset.stage1()
    cfg = cfg_mod.PipelineConfig(
        bbox=(-1.5, 47.0, 6.5, 50.9),
        start_date="2025-01-01",
        end_date="2025-12-31",
        stage=stage,
        use_dynamicworld=True,
    )

    assert mod.get_cropland_mask(cfg) == "dw"


def test_get_cropland_mask_dynamicworld_requires_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = importlib.import_module("modules.wheat_risk.masks")
    cfg_mod = importlib.import_module("modules.wheat_risk.config")

    monkeypatch.setattr(mod, "build_aoi", lambda _bbox: "aoi")
    monkeypatch.setattr(mod, "cropland_mask_worldcover", lambda _aoi: "wc")
    monkeypatch.setattr(
        mod,
        "cropland_mask_dynamicworld",
        lambda _aoi, _start, _end: "dw",
    )

    stage = cfg_mod.StagePreset.stage1()
    cfg = cfg_mod.PipelineConfig(
        bbox=(-1.5, 47.0, 6.5, 50.9),
        start_date="",
        end_date="",
        stage=stage,
        use_dynamicworld=True,
    )

    with pytest.raises(ValueError, match=r"Dynamic World"):
        mod.get_cropland_mask(cfg)


def test_get_cropland_mask_selects_worldcover_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = importlib.import_module("modules.wheat_risk.masks")
    cfg_mod = importlib.import_module("modules.wheat_risk.config")

    class _Geometry:
        @staticmethod
        def Rectangle(coords: object) -> object:
            return ("rect", coords)

    class _Image:
        pass

    class _ImageCollection:
        def __init__(self, _cid: str) -> None:
            pass

        def filterBounds(self, _aoi: object) -> "_ImageCollection":
            return self

        def first(self) -> object:
            class _Clipper:
                def clip(self, _a: object) -> _Image:
                    return _Image()

            class _Masker:
                def selfMask(self) -> _Clipper:
                    return _Clipper()

            class _Eq:
                def eq(self, _v: object) -> _Masker:
                    return _Masker()

            class _Select:
                def select(self, _b: object) -> _Eq:
                    return _Eq()

            return _Select()

    fake_ee = SimpleNamespace(Geometry=_Geometry, ImageCollection=_ImageCollection)
    monkeypatch.setitem(sys.modules, "ee", fake_ee)

    stage = cfg_mod.StagePreset.stage1()
    cfg = cfg_mod.PipelineConfig(
        bbox=(-1.5, 47.0, 6.5, 50.9),
        start_date="2025-01-01",
        end_date="2025-12-31",
        stage=stage,
        use_dynamicworld=False,
    )

    assert isinstance(mod.get_cropland_mask(cfg), _Image)

import builtins
import importlib.util
import inspect
from pathlib import Path
import sys

import pytest


def _load_export_wheat_patches_module():
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "export_wheat_patches.py"
    )
    spec = importlib.util.spec_from_file_location("export_wheat_patches", script_path)
    assert spec is not None
    assert spec.loader is not None

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_dry_run_allows_omitting_samples_and_drive_folder(capsys, monkeypatch):
    mod = _load_export_wheat_patches_module()

    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "ee" or name.startswith("ee."):
            raise AssertionError("ee import attempted during --dry-run")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    rc = mod.main(["--stage", "1", "--dry-run"])
    assert rc == 0

    out = capsys.readouterr().out
    assert "DRY RUN" in out


def test_default_is_dry_run_and_allows_omitting_samples_and_drive_folder(
    capsys, monkeypatch
):
    mod = _load_export_wheat_patches_module()

    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "ee" or name.startswith("ee."):
            raise AssertionError("ee import attempted during default dry-run")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    rc = mod.main(["--stage", "1"])
    assert rc == 0

    out = capsys.readouterr().out
    assert "DRY RUN" in out


def test_run_requires_samples_and_drive_folder():
    mod = _load_export_wheat_patches_module()

    with pytest.raises(SystemExit) as exc:
        mod.main(["--stage", "1", "--run"])

    assert exc.value.code == 2


def test_require_ee_raises_friendly_message_when_ee_missing(monkeypatch):
    import modules.ee_import as ee_import

    real_import = builtins.__import__

    def missing_ee_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "ee":
            raise ModuleNotFoundError("No module named 'ee'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", missing_ee_import)

    with pytest.raises(RuntimeError) as exc:
        ee_import.require_ee("tests")

    msg = str(exc.value)
    assert "earthengine-api" in msg
    assert "earthengine authenticate" in msg


def test_export_patch_tensors_stub_has_explicit_signature():
    from modules.wheat_risk import export_patches

    sig = inspect.signature(export_patches.export_patch_tensors_to_drive)
    kinds = [p.kind for p in sig.parameters.values()]

    assert kinds == [
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ]
    assert list(sig.parameters.keys()) == ["grid", "cfg"]


def test_gee_api_import_does_not_require_ee(monkeypatch):
    import importlib

    real_import = builtins.__import__

    def missing_ee_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "ee":
            raise ModuleNotFoundError("No module named 'ee'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", missing_ee_import)

    sys.modules.pop("modules.gee_api", None)
    mod = importlib.import_module("modules.gee_api")
    assert hasattr(mod, "initialize_ee")

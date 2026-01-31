import builtins
import importlib
import sys


def test_model_module_import_does_not_require_torch(monkeypatch):
    # Ensure a fresh import of the module under test.
    sys.modules.pop("modules.wheat_risk.model", None)

    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "torch" or name.startswith("torch."):
            raise ImportError("torch import blocked by test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    mod = importlib.import_module("modules.wheat_risk.model")
    assert hasattr(mod, "CnnLstmRisk")

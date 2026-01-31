"""Pytest configuration.

Ensure repository-local imports (e.g. `modules.*`) work regardless of where
pytest is invoked from.
"""

from __future__ import annotations

import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_root_str = str(_REPO_ROOT)
if _root_str not in sys.path:
    sys.path.insert(0, _root_str)

"""SpriCO adapter layer for vendored or installed PyRIT features."""

from pyrit.backend.sprico.pyrit_adapter.compatibility import get_pyrit_version_info, load_compatibility_matrix
from pyrit.backend.sprico.pyrit_adapter.runner import PyRITScanRunner
from pyrit.backend.sprico.pyrit_adapter.target_factory import PyRITTargetFactory

__all__ = [
    "PyRITScanRunner",
    "PyRITTargetFactory",
    "get_pyrit_version_info",
    "load_compatibility_matrix",
]

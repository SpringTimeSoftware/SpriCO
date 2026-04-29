"""Optional promptfoo runtime integration for SpriCO."""

from pyrit.backend.sprico.integrations.promptfoo.catalog import build_promptfoo_catalog
from pyrit.backend.sprico.integrations.promptfoo.discovery import (
    discover_promptfoo_plugins,
    get_promptfoo_status,
    resolve_promptfoo_command,
)
from pyrit.backend.sprico.integrations.promptfoo.runner import PromptfooRuntimeRunner

__all__ = [
    "PromptfooRuntimeRunner",
    "build_promptfoo_catalog",
    "discover_promptfoo_plugins",
    "get_promptfoo_status",
    "resolve_promptfoo_command",
]

"""Compatibility matrix for installed garak features."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from pyrit.backend.sprico.integrations.garak.discovery import PLUGIN_CATEGORIES, discover_plugins
from pyrit.backend.sprico.integrations.garak.version import get_garak_version_info


@dataclass(slots=True)
class GarakCompatibilityFeature:
    id: str
    category: str
    code_present: bool
    import_supported: bool
    backend_supported: bool
    api_supported: bool
    ui_supported: bool
    persisted: bool
    tested: bool
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_compatibility_matrix() -> dict[str, Any]:
    version_info = get_garak_version_info()
    discovery = discover_plugins() if version_info.get("available") else {
        "plugins": {category: [] for category in PLUGIN_CATEGORIES},
        "errors": {"garak": version_info.get("error")},
    }
    features: list[dict[str, Any]] = []
    for category_plural, plugin_ids in (discovery.get("plugins") or {}).items():
        category = category_plural[:-1] if category_plural.endswith("s") else category_plural
        for plugin_id in plugin_ids:
            features.append(
                GarakCompatibilityFeature(
                    id=f"garak.{category_plural}.{plugin_id}",
                    category=category,
                    code_present=True,
                    import_supported=True,
                    backend_supported=True,
                    api_supported=True,
                    ui_supported=False,
                    persisted=True,
                    tested=False,
                    status="API_SUPPORTED",
                ).to_dict()
            )

    return {
        "garak": {
            "version": version_info.get("version") or "",
            "import_path": version_info.get("import_path") or "",
            "install_mode": version_info.get("install_mode") or "unknown",
            "discovered_at": datetime.now(timezone.utc).isoformat(),
            "available": bool(version_info.get("available")),
            "error": version_info.get("error"),
        },
        "features": features,
        "discovery_errors": discovery.get("errors") or {},
    }

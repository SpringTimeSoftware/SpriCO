"""Whitelisted external engine and open-source component metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyrit.backend.sprico.integrations.garak.version import get_garak_version_info
from pyrit.backend.sprico.integrations.promptfoo.discovery import get_promptfoo_status
from pyrit.backend.sprico.judge import get_judge_status


@dataclass(frozen=True)
class LegalComponent:
    component_id: str
    name: str
    license_id: str
    license_name: str
    upstream_url: str
    local_use: str
    license_file: str
    source_file: str
    version_file: str


LEGAL_COMPONENTS: dict[str, LegalComponent] = {
    "garak": LegalComponent(
        component_id="garak",
        name="garak",
        license_id="Apache-2.0",
        license_name="Apache License 2.0",
        upstream_url="https://github.com/NVIDIA/garak",
        local_use="Optional scanner/evidence engine. garak evidence is never SpriCO's final verdict.",
        license_file="third_party/garak/LICENSE.txt",
        source_file="third_party/garak/SOURCE.txt",
        version_file="third_party/garak/VERSION.txt",
    ),
    "deepteam": LegalComponent(
        component_id="deepteam",
        name="DeepTeam",
        license_id="Apache-2.0",
        license_name="Apache License 2.0",
        upstream_url="https://github.com/confident-ai/deepteam",
        local_use="Optional attack/evidence engine metadata. Not a mandatory SpriCO runtime dependency.",
        license_file="third_party/deepteam/LICENSE.txt",
        source_file="third_party/deepteam/SOURCE.txt",
        version_file="third_party/deepteam/VERSION.txt",
    ),
    "promptfoo": LegalComponent(
        component_id="promptfoo",
        name="promptfoo",
        license_id="MIT",
        license_name="MIT License",
        upstream_url="https://github.com/promptfoo/promptfoo",
        local_use="Optional runtime and assertion evidence adapter. promptfoo evidence never overrides SpriCO's final verdict.",
        license_file="third_party/promptfoo/LICENSE.txt",
        source_file="third_party/promptfoo/SOURCE.txt",
        version_file="third_party/promptfoo/VERSION.txt",
    ),
}

ATTACK_ENGINE_IDS = (
    "sprico_manual",
    "pyrit",
    "garak",
    "deepteam",
    "promptfoo_import_or_assertions",
)

EVIDENCE_ENGINE_IDS = (
    "sprico_domain_signals",
    "garak_detector",
    "deepteam_metric",
    "promptfoo_assertion",
    "pyrit_scorer",
    "openai_judge",
)

FINAL_VERDICT_AUTHORITY = {
    "id": "sprico_policy_decision_engine",
    "name": "SpriCO PolicyDecisionEngine",
    "engine_type": "final_verdict_authority",
    "available": True,
    "locked_for_regulated_domains": True,
    "final_verdict_capable": True,
    "can_generate_attacks": False,
    "can_generate_evidence": False,
    "can_produce_final_verdict": True,
    "license_id": None,
    "source_url": None,
    "source_file": None,
    "installed_version": "native",
    "install_hint": None,
    "description": "Final policy-aware verdict authority for regulated SpriCO audits.",
}


def list_open_source_components() -> list[dict[str, Any]]:
    return [_component_payload(component) for component in LEGAL_COMPONENTS.values()]


def get_open_source_component(component_id: str) -> dict[str, Any] | None:
    component = LEGAL_COMPONENTS.get(component_id)
    if component is None:
        return None
    return _component_payload(component)


def read_component_file(component_id: str, file_kind: str) -> str | None:
    component = LEGAL_COMPONENTS.get(component_id)
    if component is None:
        return None
    if file_kind not in {"license", "source", "version"}:
        return None
    rel_path = {
        "license": component.license_file,
        "source": component.source_file,
        "version": component.version_file,
    }[file_kind]
    path = _repo_root() / rel_path
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def external_engine_matrix() -> dict[str, Any]:
    garak_status = get_garak_version_info()
    promptfoo_status = get_promptfoo_status()
    judge_status = get_judge_status()
    legal = {component_id: _component_payload(component) for component_id, component in LEGAL_COMPONENTS.items()}
    return {
        "message": "External engines provide attack/evidence signals. SpriCO produces the final policy-aware verdict.",
        "attack_engines": [
            _engine("sprico_manual", "SpriCO Manual", "attack", True, None, can_generate_attacks=True),
            _engine("pyrit", "PyRIT", "attack", True, None, can_generate_attacks=True),
            _engine(
                "garak",
                "garak",
                "attack",
                bool(garak_status.get("available")),
                "garak",
                can_generate_attacks=True,
                installed_version=garak_status.get("version"),
                install_hint=garak_status.get("install_hint"),
            ),
            _engine("deepteam", "DeepTeam", "attack", False, "deepteam", metadata_only=True, can_generate_attacks=True),
            _engine(
                "promptfoo_import_or_assertions",
                "promptfoo runtime/assertions",
                "attack",
                bool(promptfoo_status.get("available")),
                "promptfoo",
                can_generate_attacks=True,
                installed_version=promptfoo_status.get("version"),
                install_hint=promptfoo_status.get("install_hint"),
            ),
        ],
        "evidence_engines": [
            _engine("sprico_domain_signals", "SpriCO domain signals", "evidence", True, None, can_generate_evidence=True),
            _engine(
                "garak_detector",
                "garak detector evidence",
                "evidence",
                bool(garak_status.get("available")),
                "garak",
                can_generate_evidence=True,
                installed_version=garak_status.get("version"),
                install_hint=garak_status.get("install_hint"),
            ),
            _engine("deepteam_metric", "DeepTeam metric evidence", "evidence", False, "deepteam", metadata_only=True, can_generate_evidence=True),
            _engine(
                "promptfoo_assertion",
                "promptfoo assertion evidence",
                "evidence",
                bool(promptfoo_status.get("available")),
                "promptfoo",
                can_generate_evidence=True,
                installed_version=promptfoo_status.get("version"),
                install_hint=promptfoo_status.get("install_hint"),
            ),
            _engine("pyrit_scorer", "PyRIT scorer evidence", "evidence", True, None, can_generate_evidence=True),
            _engine(
                "openai_judge",
                "OpenAI judge evidence",
                "evidence",
                bool(judge_status.get("configured")),
                None,
                disabled_by_default=True,
                can_generate_evidence=True,
                install_hint="Configure backend judge secrets under Settings -> Judge Models.",
            ),
        ],
        "optional_judge_models": judge_status.get("providers", []),
        "domain_policy_pack_required": True,
        "final_verdict_authority": FINAL_VERDICT_AUTHORITY,
        "regulated_domain_lock": {
            "locked": True,
            "authority_id": FINAL_VERDICT_AUTHORITY["id"],
            "reason": "Regulated domains require SpriCO policy context, authorization, purpose, scope, and minimum-necessary checks.",
        },
        "garak_status": garak_status,
        "promptfoo_status": promptfoo_status,
        "legal_components": legal,
    }


def _engine(
    engine_id: str,
    name: str,
    engine_type: str,
    available: bool,
    component_id: str | None,
    *,
    metadata_only: bool = False,
    disabled_by_default: bool = False,
    can_generate_attacks: bool = False,
    can_generate_evidence: bool = False,
    installed_version: Any | None = None,
    install_hint: str | None = None,
) -> dict[str, Any]:
    component = LEGAL_COMPONENTS.get(component_id or "")
    component_payload = _component_payload(component) if component else None
    return {
        "id": engine_id,
        "name": name,
        "engine_type": engine_type,
        "available": available,
        "optional": engine_id != "sprico_domain_signals",
        "metadata_only": metadata_only,
        "enabled_by_default": not disabled_by_default and available,
        "final_verdict_capable": False,
        "can_generate_attacks": bool(can_generate_attacks),
        "can_generate_evidence": bool(can_generate_evidence),
        "can_produce_final_verdict": False,
        "license_id": component.license_id if component else None,
        "source_url": component.upstream_url if component else None,
        "source_file": component.source_file if component else None,
        "license_component_id": component.component_id if component else None,
        "installed_version": installed_version or (component_payload or {}).get("version") or None,
        "install_hint": install_hint
        or ("Metadata/status only in this phase; no runtime dependency is installed." if metadata_only else None),
    }


def _component_payload(component: LegalComponent) -> dict[str, Any]:
    version = read_component_file(component.component_id, "version").strip()
    source = read_component_file(component.component_id, "source").strip()
    return {
        "id": component.component_id,
        "name": component.name,
        "license_id": component.license_id,
        "license_name": component.license_name,
        "upstream_url": component.upstream_url,
        "local_use": component.local_use,
        "version": version,
        "source_notice": source,
        "license_file": component.license_file,
        "source_file": component.source_file,
        "version_file": component.version_file,
        "license_url": f"/api/legal/open-source-components/{component.component_id}/license",
        "source_url": f"/api/legal/open-source-components/{component.component_id}/source",
        "version_url": f"/api/legal/open-source-components/{component.component_id}/version",
    }


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "THIRD_PARTY_NOTICES.md").exists():
            return parent
    return current.parents[3]

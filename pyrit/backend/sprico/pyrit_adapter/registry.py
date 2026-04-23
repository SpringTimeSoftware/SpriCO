"""Static and dynamic feature registry for productized PyRIT features."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class CompatibilityFeature:
    id: str
    category: str
    name: str
    pyrit_class: str
    code_present: bool
    import_supported: bool
    backend_supported: bool
    api_supported: bool
    ui_supported: bool
    persisted: bool
    tested: bool
    status: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_feature_registry() -> list[CompatibilityFeature]:
    return [
        CompatibilityFeature(
            id="pyrit.target.openai_chat",
            category="target",
            name="OpenAI Chat Target",
            pyrit_class="pyrit.prompt_target.openai.OpenAIChatTarget",
            code_present=True,
            import_supported=True,
            backend_supported=True,
            api_supported=True,
            ui_supported=True,
            persisted=True,
            tested=True,
            status="audit_supported",
            notes="Backed by SpriCO target registry and interactive audit.",
        ),
        CompatibilityFeature(
            id="pyrit.target.openai_vector_store",
            category="target",
            name="OpenAI Vector Store Target",
            pyrit_class="pyrit.prompt_target.openai.OpenAIVectorStoreTarget",
            code_present=True,
            import_supported=True,
            backend_supported=True,
            api_supported=True,
            ui_supported=True,
            persisted=True,
            tested=True,
            status="audit_supported",
            notes="Retrieval-backed target with persisted config and evidence preservation.",
        ),
        CompatibilityFeature(
            id="pyrit.target.gemini_file_search",
            category="target",
            name="Gemini File Search Target",
            pyrit_class="pyrit.prompt_target.gemini.GeminiFileSearchTarget",
            code_present=True,
            import_supported=True,
            backend_supported=True,
            api_supported=True,
            ui_supported=True,
            persisted=True,
            tested=True,
            status="audit_supported",
            notes="Provider-specific retrieval execution path productized in SpriCO.",
        ),
        CompatibilityFeature(
            id="pyrit.target.http",
            category="target",
            name="HTTP Target",
            pyrit_class="pyrit.prompt_target.http.HTTPTarget",
            code_present=True,
            import_supported=True,
            backend_supported=True,
            api_supported=True,
            ui_supported=True,
            persisted=True,
            tested=False,
            status="backend",
            notes="Available through current target registry for generic callback-style integration.",
        ),
        CompatibilityFeature(
            id="pyrit.scorer.hospital_privacy_composite",
            category="scorer",
            name="Hospital Privacy Composite",
            pyrit_class="scoring.packs.hospital_privacy.HospitalPrivacyCompositeScorer",
            code_present=True,
            import_supported=True,
            backend_supported=True,
            api_supported=True,
            ui_supported=True,
            persisted=True,
            tested=True,
            status="audit_supported",
            notes="Deterministic context-aware privacy scorer layered on top of PyRIT flows.",
        ),
        CompatibilityFeature(
            id="pyrit.scorer.adapter",
            category="scorer",
            name="PyRIT Scorer Adapter",
            pyrit_class="pyrit.backend.sprico.pyrit_adapter.scorer_factory.PyRITScorerAdapter",
            code_present=True,
            import_supported=True,
            backend_supported=True,
            api_supported=False,
            ui_supported=False,
            persisted=False,
            tested=False,
            status="backend",
            notes="Adapter surface exists; explicit scan API wiring remains incremental.",
        ),
        CompatibilityFeature(
            id="pyrit.feature.compatibility_matrix",
            category="platform",
            name="Compatibility Matrix",
            pyrit_class="pyrit.backend.sprico.pyrit_adapter.compatibility",
            code_present=True,
            import_supported=True,
            backend_supported=True,
            api_supported=True,
            ui_supported=False,
            persisted=False,
            tested=True,
            status="api",
            notes="Exposed through /api/pyrit/compatibility.",
        ),
    ]

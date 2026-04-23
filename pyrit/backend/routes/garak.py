"""garak integration and scan APIs."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from pyrit.backend.sprico.integrations.garak.compatibility import build_compatibility_matrix
from pyrit.backend.sprico.integrations.garak.discovery import discover_plugins
from pyrit.backend.sprico.integrations.garak.errors import GarakScanValidationError
from pyrit.backend.sprico.integrations.garak.profiles import SCAN_PROFILES, get_scan_profiles
from pyrit.backend.sprico.integrations.garak.reports import build_garak_scan_report, build_garak_scan_reports, summarize_garak_scan_reports
from pyrit.backend.sprico.integrations.garak.runner import GarakScanRunner
from pyrit.backend.sprico.integrations.garak.version import get_garak_version_info
from pyrit.backend.sprico.storage import get_storage_backend
from pyrit.backend.sprico.judge import get_judge_status
from pyrit.backend.services.target_service import get_target_service

router = APIRouter(tags=["garak"])
_runner = GarakScanRunner()


class GarakGeneratorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = "test"
    name: str = "Blank"
    options: dict[str, Any] = Field(default_factory=dict)


class JudgeSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    provider: str = "openai"
    mode: str = "redacted"
    judge_only_ambiguous: bool = True


class GarakScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: str = ""
    policy_id: str = ""
    scan_profile: str = "quick_baseline"
    vulnerability_categories: list[str] = Field(default_factory=list)
    max_attempts: int = Field(default=1, ge=1, le=20)
    generator: Optional[GarakGeneratorRequest] = None
    probes: list[str] = Field(default_factory=list)
    detectors: list[str] = Field(default_factory=list)
    extended_detectors: bool = False
    buffs: list[str] = Field(default_factory=list)
    generations: int = Field(default=1, ge=1)
    seed: Optional[int] = None
    parallel_requests: int = Field(default=1, ge=1)
    parallel_attempts: int = Field(default=1, ge=1)
    timeout_seconds: int = Field(default=3600, ge=1)
    budget: dict[str, Any] = Field(default_factory=dict)
    permission_attestation: bool = False
    cross_domain_override: bool = False
    judge_settings: JudgeSettingsRequest = Field(default_factory=JudgeSettingsRequest)
    policy_context: dict[str, Any] = Field(default_factory=dict)


@router.get("/integrations/garak/status")
async def garak_status() -> dict[str, Any]:
    return get_garak_version_info()


@router.get("/garak/status")
async def garak_status_alias() -> dict[str, Any]:
    return get_garak_version_info()


@router.get("/integrations/garak/plugins")
async def garak_plugins() -> dict[str, Any]:
    return discover_plugins()


@router.get("/garak/plugins")
async def garak_plugins_alias() -> dict[str, Any]:
    return discover_plugins()


@router.get("/garak/probes")
async def garak_probes() -> dict[str, Any]:
    plugins = discover_plugins()
    return {"available": plugins.get("available", False), "probes": (plugins.get("plugins") or {}).get("probes", [])}


@router.get("/garak/detectors")
async def garak_detectors() -> dict[str, Any]:
    plugins = discover_plugins()
    return {"available": plugins.get("available", False), "detectors": (plugins.get("plugins") or {}).get("detectors", [])}


@router.get("/garak/generators")
async def garak_generators() -> dict[str, Any]:
    plugins = discover_plugins()
    return {"available": plugins.get("available", False), "generators": (plugins.get("plugins") or {}).get("generators", [])}


@router.get("/garak/profiles")
async def garak_profiles() -> dict[str, Any]:
    return {"profiles": get_scan_profiles()}


@router.get("/integrations/garak/compatibility")
async def garak_compatibility() -> dict[str, Any]:
    return build_compatibility_matrix()


@router.get("/garak/compatibility")
async def garak_compatibility_alias() -> dict[str, Any]:
    return build_compatibility_matrix()


@router.post("/scans/garak", status_code=status.HTTP_201_CREATED)
async def create_garak_scan(request: GarakScanRequest) -> dict[str, Any]:
    target_id = request.target_id.strip()
    if not target_id:
        return _validation_failed(
            [{"field": "target_id", "reason": "Target is required."}],
            ["Select a configured target."],
        )
    policy_id = request.policy_id.strip()
    if not policy_id:
        return _validation_failed(
            [{"field": "policy_id", "reason": "Policy is required."}],
            ["Choose a domain policy pack."],
        )
    if not request.permission_attestation:
        return _validation_failed(
            [{"field": "permission_attestation", "reason": "Permission attestation is required."}],
            ["Confirm permission attestation."],
        )
    if request.scan_profile not in SCAN_PROFILES:
        return _validation_failed(
            [{"field": "scan_profile", "reason": f"Selected scan profile '{request.scan_profile}' is not allowed for this target."}],
            ["Choose an allowlisted scan profile."],
        )

    target_config = await get_target_service().get_target_config_async(target_registry_name=target_id)
    if target_config is None:
        return _validation_failed(
            [{"field": "target_id", "reason": f"Target '{target_id}' was not found in the configured target registry."}],
            ["Select a configured target.", "Open Target Configuration to verify the target registry."],
        )
    target_domain = _domain_for_target_config(target_config)
    policy_domain = _policy_domain_from_request(policy_id=policy_id, policy_context=request.policy_context)
    if _domains_mismatch(target_domain, policy_domain) and not request.cross_domain_override:
        target_canonical = _canonical_domain(target_domain)
        policy_canonical = _canonical_domain(policy_domain)
        return _validation_failed(
            [
                {
                    "field": "cross_domain_override",
                    "reason": (
                        f"Target domain {target_domain if target_canonical != target_domain else target_canonical} "
                        f"does not match policy domain {policy_canonical}."
                    ),
                }
            ],
            ["Choose a matching policy pack.", "Or confirm cross-domain evaluation if this is intentional."],
        )
    judge_error = _validate_judge_settings(
        judge_settings=request.judge_settings,
        target_domain=target_domain,
        policy_domain=policy_domain,
    )
    if judge_error:
        return judge_error

    payload = request.model_dump(exclude_none=True)
    payload["target_id"] = target_id
    payload["policy_id"] = policy_id
    payload["probes"] = []
    payload["detectors"] = []
    payload["buffs"] = []
    payload["generations"] = request.max_attempts
    policy_context = dict(payload.get("policy_context") or {})
    policy_context.update(
        {
            "policy_id": policy_id,
            "target_id": target_id,
            "target_name": target_config.display_name,
            "target_type": target_config.target_type,
            "selected_target_domain": target_domain,
            "policy_domain": policy_domain,
            "cross_domain_override": request.cross_domain_override,
            "judge_settings": request.judge_settings.model_dump(),
            "scan_profile": request.scan_profile,
            "vulnerability_categories": request.vulnerability_categories,
        }
    )
    payload["policy_context"] = policy_context
    payload["target_name"] = target_config.display_name
    payload["target_type"] = target_config.target_type

    if not target_config.endpoint:
        return _validation_failed(
            [{"field": "target_id", "reason": "Selected target is missing scanner endpoint mapping."}],
            ["Configure scanner-compatible endpoint mapping in Target Configuration."],
        )

    try:
        generator = _resolve_garak_generator(target_config=target_config, request_generator=request.generator)
    except GarakScanValidationError as exc:
        return _validation_failed(
            [{"field": "target_id", "reason": str(exc)}],
            ["Configure garak scanner compatibility in Target Configuration."],
        )

    payload["generator"] = generator
    try:
        return _runner.run(payload)
    except GarakScanValidationError as exc:
        return _validation_failed(
            [{"field": "scan_profile", "reason": str(exc)}],
            ["Choose an allowlisted scan profile.", "Configure garak scanner compatibility in Target Configuration."],
        )


def _validation_failed(details: list[dict[str, str]], next_steps: list[str]) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "validation_failed",
            "message": "Cannot start scanner run.",
            "details": details,
            "next_steps": next_steps,
        },
    )


def _validate_judge_settings(
    *,
    judge_settings: JudgeSettingsRequest,
    target_domain: str,
    policy_domain: str,
) -> JSONResponse | None:
    if not judge_settings.enabled:
        return None
    provider = judge_settings.provider.strip().lower()
    if provider != "openai":
        return _validation_failed(
            [{"field": "judge_settings.provider", "reason": f"Judge provider '{judge_settings.provider}' is not supported."}],
            ["Choose provider 'openai' or disable judge evidence for this scan."],
        )
    status_payload = get_judge_status()
    providers = {
        str(item.get("id")): item
        for item in status_payload.get("providers", [])
        if isinstance(item, dict)
    }
    provider_status = providers.get(provider) or {}
    if not provider_status.get("configured"):
        return _validation_failed(
            [{"field": "judge_settings", "reason": "OpenAI Judge is not configured in the backend environment."}],
            ["Configure SPRICO_OPENAI_JUDGE_MODEL and OPENAI_API_KEY on the backend.", "Keep judge evidence disabled for this scan."],
        )
    if not provider_status.get("enabled"):
        return _validation_failed(
            [{"field": "judge_settings", "reason": "OpenAI Judge is configured but not enabled by backend policy."}],
            ["Set SPRICO_OPENAI_JUDGE_ENABLED=true on the backend if judge evidence is approved.", "Keep judge evidence disabled for this scan."],
        )
    allowed_modes = {str(mode).lower() for mode in provider_status.get("allowed_modes", [])}
    mode = judge_settings.mode.strip().lower()
    regulated = {_canonical_domain(target_domain), _canonical_domain(policy_domain)} & {"healthcare"}
    if regulated and mode != "redacted":
        return _validation_failed(
            [{"field": "judge_settings.mode", "reason": "Healthcare/PHI scans require redacted judge evidence mode by default."}],
            ["Use redacted mode.", "Do not send PHI/PII/hospital data to external APIs without explicit approval."],
        )
    if mode not in allowed_modes:
        return _validation_failed(
            [{"field": "judge_settings.mode", "reason": f"Judge mode '{judge_settings.mode}' is not allowed by backend policy."}],
            ["Use redacted mode or disable judge evidence."],
        )
    return None


def _resolve_garak_generator(*, target_config: Any, request_generator: GarakGeneratorRequest | None) -> dict[str, Any]:
    params = dict(getattr(target_config, "provider_settings", None) or {})
    runtime = dict(getattr(target_config, "runtime_summary", None) or {})
    target_type = str(getattr(target_config, "target_type", "") or "")
    model_name = str(getattr(target_config, "model_name", "") or params.get("model_name") or runtime.get("model_name") or "").strip()

    explicit_type = str(params.get("garak_generator_type") or params.get("garak_type") or "").strip()
    explicit_name = str(params.get("garak_generator_name") or params.get("garak_model_name") or "").strip()
    if explicit_type and explicit_name:
        return {"type": explicit_type, "name": explicit_name, "options": {}}

    if request_generator and (request_generator.type, request_generator.name) != ("test", "Blank"):
        raise GarakScanValidationError(
            "Raw garak generator overrides are not accepted through the scanner API. Configure garak_generator_type and garak_generator_name on the target instead."
        )

    lowered = target_type.lower()
    if "texttarget" in lowered:
        raise GarakScanValidationError(
            "Selected target is configured for Interactive Audit but not yet compatible with garak scanner execution."
        )
    if "geminifilesearchtarget" in lowered:
        raise GarakScanValidationError(
            "GeminiFileSearchTarget requires explicit scanner generator mapping before garak can run."
        )
    if "openai" in lowered:
        if not model_name:
            raise GarakScanValidationError("Selected OpenAI target is missing a model name required for garak scanner execution.")
        return {"type": "openai", "name": model_name, "options": {}}
    if "azure" in lowered:
        if not model_name:
            raise GarakScanValidationError("Selected Azure target is missing a deployment/model name required for garak scanner execution.")
        return {"type": "azure", "name": model_name, "options": {}}
    if "gemini" in lowered or "google" in lowered:
        if not model_name:
            raise GarakScanValidationError("Selected Gemini target is missing a model name required for garak scanner execution.")
        return {"type": "google", "name": model_name, "options": {}}
    if "local" in lowered or "huggingface" in lowered:
        if not model_name:
            raise GarakScanValidationError("Selected local target is missing a model name required for garak scanner execution.")
        return {"type": "huggingface", "name": model_name, "options": {}}
    raise GarakScanValidationError(
        "Selected target is configured for Interactive Audit but not yet compatible with garak scanner execution."
    )


def _domain_for_target_config(target_config: Any) -> str:
    params = dict(getattr(target_config, "provider_settings", None) or {})
    runtime = dict(getattr(target_config, "runtime_summary", None) or {})
    explicit = (
        params.get("target_domain")
        or params.get("domain")
        or params.get("industry")
        or params.get("policy_domain")
        or runtime.get("target_domain")
    )
    if explicit:
        return str(explicit)
    haystack = f"{getattr(target_config, 'display_name', '')} {getattr(target_config, 'target_registry_name', '')}".lower()
    if any(term in haystack for term in ("hospital", "health", "clinical")):
        return "Healthcare"
    if "legal" in haystack:
        return "Legal"
    if "hr" in haystack or "human resources" in haystack:
        return "HR"
    if "finance" in haystack or "bank" in haystack:
        return "Financial"
    return "General AI"


def _policy_domain_from_request(*, policy_id: str, policy_context: dict[str, Any]) -> str:
    value = policy_context.get("policy_domain") or policy_context.get("target_domain") or policy_context.get("domain")
    if value:
        return str(value)
    lowered = policy_id.lower()
    if "hospital" in lowered or "health" in lowered or "clinical" in lowered:
        return "hospital"
    if "legal" in lowered:
        return "legal"
    if "hr" in lowered or "human" in lowered:
        return "hr"
    if "finance" in lowered or "bank" in lowered:
        return "financial"
    return "general"


def _domains_mismatch(target_domain: str, policy_domain: str) -> bool:
    target = _canonical_domain(target_domain)
    policy = _canonical_domain(policy_domain)
    return bool(target and policy and target != "general" and policy != "general" and target != policy)


def _canonical_domain(value: str) -> str:
    text = str(value or "").strip().lower().replace("_", " ")
    if text in {"hospital", "healthcare", "health", "clinical", "medical"}:
        return "healthcare"
    if text in {"hr", "human resources", "people"}:
        return "hr"
    if text in {"financial", "finance", "banking"}:
        return "financial"
    if text in {"legal", "law"}:
        return "legal"
    if text in {"enterprise", "general ai", "general", "unknown"}:
        return "general"
    return text


@router.get("/scans/garak")
async def list_garak_scans() -> list[dict[str, Any]]:
    return _runner.list_scans()


@router.get("/scans/garak/reports/summary")
async def get_garak_scan_report_summary() -> dict[str, Any]:
    reports = _garak_reports()
    return summarize_garak_scan_reports(reports)


@router.get("/scans/garak/reports")
async def list_garak_scan_reports() -> dict[str, Any]:
    reports = _garak_reports()
    return {
        "reports": reports,
        "summary": summarize_garak_scan_reports(reports),
    }


@router.get("/scans/garak/reports/{scan_id}")
async def get_garak_scan_report(scan_id: str) -> dict[str, Any]:
    result = _runner.get_scan(scan_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"garak scan '{scan_id}' not found")
    return build_garak_scan_report(result, policy_names=_policy_name_map())


@router.get("/scans/garak/{scan_id}")
async def get_garak_scan(scan_id: str) -> dict[str, Any]:
    # Defensive compatibility: older route ordering treated "reports" as a scan_id.
    # Keep the static reports endpoint authoritative, but do not return a misleading
    # "garak scan 'reports' not found" if this dynamic handler is reached.
    if scan_id == "reports":
        return await list_garak_scan_reports()
    result = _runner.get_scan(scan_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"garak scan '{scan_id}' not found")
    return result


@router.get("/scans/garak/{scan_id}/artifacts")
async def get_garak_scan_artifacts(scan_id: str) -> dict[str, Any]:
    artifacts = _runner.list_artifacts(scan_id)
    if not artifacts:
        result = _runner.get_scan(scan_id)
        if result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"garak scan '{scan_id}' not found")
    return {"scan_id": scan_id, "artifacts": artifacts}


@router.get("/scans/garak/{scan_id}/findings")
async def get_garak_scan_findings(scan_id: str) -> dict[str, Any]:
    result = _runner.get_scan(scan_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"garak scan '{scan_id}' not found")
    return {
        "scan_id": scan_id,
        "raw_findings": result.get("raw_findings") or [],
        "signals": result.get("signals") or [],
        "findings": result.get("findings") or [],
        "aggregate": result.get("aggregate") or {},
    }


def _garak_reports() -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for item in _runner.list_scans():
        scan_id = str(item.get("scan_id") or item.get("id") or "")
        if scan_id:
            runs.append(_runner.get_scan(scan_id) or item)
        else:
            runs.append(item)
    return build_garak_scan_reports(runs, policy_names=_policy_name_map())


def _policy_name_map() -> dict[str, str]:
    try:
        return {
            str(policy.get("id")): str(policy.get("name") or policy.get("id"))
            for policy in get_storage_backend().list_records("policies")
            if policy.get("id")
        }
    except Exception:
        return {}

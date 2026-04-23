"""garak CLI runner and artifact capture."""

from __future__ import annotations

import json
from pathlib import Path
import re
import hashlib
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

from pyrit.backend.sprico.integrations.garak.config import GarakGeneratorConfig, GarakScanConfig
from pyrit.backend.sprico.integrations.garak.discovery import discover_plugins
from pyrit.backend.sprico.integrations.garak.errors import GarakScanValidationError
from pyrit.backend.sprico.integrations.garak.normalizer import normalize_findings
from pyrit.backend.sprico.integrations.garak.parser import parse_artifacts
from pyrit.backend.sprico.integrations.garak.profiles import resolve_scan_profile
from pyrit.backend.sprico.integrations.garak.version import get_garak_version_info
from pyrit.backend.sprico.evidence_store import SpriCOEvidenceStore
from pyrit.backend.sprico.storage import StorageBackend, get_storage_backend
from pyrit.common.path import DB_DATA_PATH
from scoring.policy_context import build_policy_context
from scoring.policy_decision_engine import PolicyDecisionEngine

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)(api[_-]?key|token|authorization|password)\s*[:=]\s*[^\s,;]+"),
)
_GARAK_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")


class GarakScanRunner:
    """Run garak as scanner evidence and apply SpriCO policy after parsing."""

    def __init__(self, artifact_root: Path | None = None, backend: StorageBackend | None = None) -> None:
        self.artifact_root = artifact_root or (DB_DATA_PATH / "garak_scans")
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self._policy_engine = PolicyDecisionEngine()
        self._backend = backend or get_storage_backend()
        self._evidence_store = SpriCOEvidenceStore(backend=self._backend)

    def run(self, config: GarakScanConfig | dict[str, Any]) -> dict[str, Any]:
        started_at = _utc_now()
        scan_config = _ensure_config(config)
        _validate_scan_config(scan_config)
        if not scan_config.permission_attestation:
            raise GarakScanValidationError("permission_attestation must be true before running a garak scan")

        scan_dir = self.artifact_root / scan_config.scan_id
        scan_dir.mkdir(parents=True, exist_ok=True)

        version_info = get_garak_version_info()
        _apply_scan_profile(scan_config=scan_config, version_info=version_info)
        _validate_scan_config(scan_config)
        _write_json(scan_dir / "config.json", scan_config.to_dict())

        if not version_info.get("available"):
            result = _not_evaluated_result(
                scan_config=scan_config,
                scan_dir=scan_dir,
                status="unavailable",
                started_at=started_at,
                failure_reason="garak is not installed; scanner evidence could not be collected.",
                garak=version_info,
            )
            _write_json(scan_dir / "scan_result.json", result)
            self._persist_run(scan_config=scan_config, result=result)
            return result

        command = self._build_command(scan_config=scan_config, scan_dir=scan_dir)
        _write_json(scan_dir / "command.json", {"command": _redact_command(command), "shell": False})

        try:
            completed = subprocess.run(
                command,
                cwd=str(scan_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=scan_config.timeout_seconds,
                check=False,
                shell=False,
            )
            status = "completed" if completed.returncode == 0 else "failed"
            stdout = _redact_text(completed.stdout or "")
            stderr = _redact_text(completed.stderr or "")
            (scan_dir / "stdout.txt").write_text(stdout, encoding="utf-8")
            (scan_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
            (scan_dir / "exit_code.txt").write_text(str(completed.returncode), encoding="utf-8")
        except subprocess.TimeoutExpired as exc:
            status = "timeout"
            (scan_dir / "stdout.txt").write_text(_redact_text(exc.stdout or ""), encoding="utf-8")
            (scan_dir / "stderr.txt").write_text(_redact_text(exc.stderr or ""), encoding="utf-8")
            (scan_dir / "exit_code.txt").write_text("timeout", encoding="utf-8")

        if status in {"timeout", "failed"}:
            reason = "Scanner timed out before producing usable evidence." if status == "timeout" else _failure_reason(scan_dir)
            result = _not_evaluated_result(
                scan_config=scan_config,
                scan_dir=scan_dir,
                status=status,
                started_at=started_at,
                failure_reason=reason,
                garak=version_info,
            )
            _write_json(scan_dir / "scan_result.json", result)
            self._persist_run(scan_config=scan_config, result=result)
            return result

        try:
            raw_findings = parse_artifacts(scan_dir=scan_dir, engine_version=version_info.get("version"))
        except Exception as exc:
            result = _not_evaluated_result(
                scan_config=scan_config,
                scan_dir=scan_dir,
                status="parsing_failed",
                started_at=started_at,
                failure_reason=f"Scanner artifacts could not be parsed: {exc}",
                garak=version_info,
            )
            _write_json(scan_dir / "scan_result.json", result)
            self._persist_run(scan_config=scan_config, result=result)
            return result
        signals = normalize_findings(raw_findings)
        signal_payloads = [signal.to_dict() for signal in signals]
        policy_context = build_policy_context(metadata=scan_config.policy_context, prompt_text="")
        decision = self._policy_engine.decide(
            signals=signals,
            policy_context=policy_context,
            conversation_context={"engine": "garak", "scan_id": scan_config.scan_id, "scan_profile": scan_config.scan_profile},
        )
        scanner_evidence = [
            _scanner_evidence_payload(finding=finding, artifact_root=scan_dir, scan_id=scan_config.scan_id)
            for finding in raw_findings
        ]
        final_verdict = _decision_payload(decision)
        findings = _actionable_findings(
            scan_config=scan_config,
            scanner_evidence=scanner_evidence,
            final_verdict=final_verdict,
            signals=signal_payloads,
        )
        finished_at = _utc_now()
        effective_status = "completed" if findings else "completed_no_findings"
        result = {
            "scan_id": scan_config.scan_id,
            "status": effective_status,
            "started_at": started_at,
            "finished_at": finished_at,
            **_scan_identity(scan_config),
            "evaluation_status": "evaluated",
            "failure_reason": None,
            "evidence_count": len(scanner_evidence),
            "findings_count": len(findings),
            "final_verdict": final_verdict.get("verdict"),
            "risk": final_verdict.get("violation_risk"),
            "garak": version_info,
            "raw_findings": [finding.to_dict() for finding in raw_findings],
            "scanner_evidence": scanner_evidence,
            "signals": signal_payloads,
            "findings": findings,
            "sprico_final_verdict": final_verdict,
            "aggregate": {
                "final_verdict": decision.verdict,
                "worst_risk": decision.risk,
                "data_sensitivity": decision.data_sensitivity,
                "reason": decision.explanation,
                "raw_signal_count": len(signals),
                "evidence_count": len(scanner_evidence),
                "findings_count": len(findings),
            },
            "artifacts": _artifact_refs(scan_dir),
        }
        _write_json(scan_dir / "scan_result.json", result)
        self._persist_run(scan_config=scan_config, result=result)
        return result

    def record_not_evaluated(
        self,
        config: GarakScanConfig | dict[str, Any],
        *,
        status: str,
        failure_reason: str,
        garak: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        started_at = _utc_now()
        scan_config = _ensure_config(config)
        scan_dir = self.artifact_root / scan_config.scan_id
        scan_dir.mkdir(parents=True, exist_ok=True)
        _write_json(scan_dir / "config.json", scan_config.to_dict())
        result = _not_evaluated_result(
            scan_config=scan_config,
            scan_dir=scan_dir,
            status=status,
            started_at=started_at,
            failure_reason=failure_reason,
            garak=garak or get_garak_version_info(),
        )
        _write_json(scan_dir / "scan_result.json", result)
        self._persist_run(scan_config=scan_config, result=result)
        return result

    def get_scan(self, scan_id: str) -> dict[str, Any] | None:
        result_path = self.artifact_root / scan_id / "scan_result.json"
        if not result_path.exists():
            run = self._backend.get_record("garak_runs", scan_id)
            return run
        return json.loads(result_path.read_text(encoding="utf-8"))

    def list_scans(self) -> list[dict[str, Any]]:
        return self._backend.list_records("garak_runs")

    def list_artifacts(self, scan_id: str) -> list[dict[str, Any]]:
        scan_dir = self.artifact_root / scan_id
        return _artifact_refs(scan_dir)

    def _persist_run(self, *, scan_config: GarakScanConfig, result: dict[str, Any]) -> None:
        self._backend.upsert_record(
            "garak_runs",
            scan_config.scan_id,
            {
                "id": scan_config.scan_id,
                "scan_id": scan_config.scan_id,
                "target_id": scan_config.target_id,
                "target_name": result.get("target_name"),
                "target_type": result.get("target_type"),
                "policy_id": result.get("policy_id"),
                "scan_profile": result.get("scan_profile"),
                "started_at": result.get("started_at"),
                "finished_at": result.get("finished_at"),
                "status": result.get("status"),
                "evaluation_status": result.get("evaluation_status"),
                "failure_reason": result.get("failure_reason"),
                "final_verdict": result.get("final_verdict"),
                "risk": result.get("risk"),
                "garak": result.get("garak") or {},
                "sprico_final_verdict": result.get("sprico_final_verdict") or {},
                "aggregate": result.get("aggregate") or {},
                "attempts": scan_config.generations,
                "evidence_count": len(result.get("scanner_evidence") or []),
                "findings_count": len(result.get("findings") or []),
                "config": scan_config.to_dict(),
                "artifacts": result.get("artifacts") or [],
            },
        )
        self._backend.upsert_record(
            "scans",
            scan_config.scan_id,
            {
                "id": scan_config.scan_id,
                "scan_id": scan_config.scan_id,
                "scan_type": "llm_vulnerability_scanner",
                "engine": "garak",
                "status": result.get("status"),
                "evaluation_status": result.get("evaluation_status"),
                "failure_reason": result.get("failure_reason"),
                "final_verdict": result.get("final_verdict"),
                "risk": result.get("risk"),
                "target_id": result.get("target_id"),
                "target_name": result.get("target_name"),
                "target_type": result.get("target_type"),
                "policy_id": result.get("policy_id"),
                "scan_profile": result.get("scan_profile"),
                "started_at": result.get("started_at"),
                "finished_at": result.get("finished_at"),
                "aggregate": result.get("aggregate") or {},
            },
        )
        self._backend.upsert_record(
            "scan_results",
            scan_config.scan_id,
            {
                "id": scan_config.scan_id,
                "scan_id": scan_config.scan_id,
                "scan_type": "llm_vulnerability_scanner",
                "result": result,
            },
        )
        for artifact in result.get("artifacts") or []:
            artifact_id = str(artifact.get("artifact_id") or f"{scan_config.scan_id}:{artifact.get('name')}")
            self._backend.upsert_record(
                "garak_artifacts",
                artifact_id,
                {"id": artifact_id, "scan_id": scan_config.scan_id, **artifact},
            )
        for index, evidence in enumerate(result.get("scanner_evidence") or [], start=1):
            evidence_id = evidence.get("evidence_id") or f"garak_{scan_config.scan_id}_{index}"
            evidence_signals = _signals_for_evidence(result.get("signals") or [], evidence)
            self._evidence_store.append_event(
                {
                    "finding_id": evidence_id,
                    "engine": "garak",
                    "engine_id": "garak",
                    "engine_name": "garak LLM Scanner",
                    "engine_type": "scanner",
                    "source_type": "external_scanner",
                    "engine_version": evidence.get("engine_version"),
                    "license_id": "Apache-2.0",
                    "source_url": "https://github.com/NVIDIA/garak",
                    "source_file": "third_party/garak/SOURCE.txt",
                    "target_id": scan_config.target_id,
                    "target_name": result.get("target_name"),
                    "target_type": result.get("target_type"),
                    "scan_id": scan_config.scan_id,
                    "policy_id": result.get("policy_id"),
                    "policy_context": scan_config.policy_context,
                    "evidence_type": "scanner_evidence",
                    "raw_result": evidence,
                    "scanner_result": evidence.get("scanner_result") or {},
                    "artifact_refs": evidence.get("artifact_refs") or [],
                    "normalized_signal": evidence_signals,
                    "matched_signals": evidence_signals,
                    "final_verdict": (result.get("sprico_final_verdict") or {}).get("verdict"),
                    "violation_risk": (result.get("sprico_final_verdict") or {}).get("violation_risk"),
                    "data_sensitivity": (result.get("sprico_final_verdict") or {}).get("data_sensitivity"),
                    "sprico_final_verdict": result.get("sprico_final_verdict") or {},
                    "explanation": (result.get("sprico_final_verdict") or {}).get("explanation"),
                    "redaction_status": "payload_redacted",
                }
            )
        for finding in result.get("findings") or []:
            finding_id = str(finding.get("finding_id") or f"garak_finding_{scan_config.scan_id}_{uuid.uuid4().hex[:8]}")
            self._backend.upsert_record("findings", finding_id, {"id": finding_id, **finding})

    def _build_command(self, *, scan_config: GarakScanConfig, scan_dir: Path) -> list[str]:
        help_text = _garak_help()
        target_type_flag = "--target_type" if "--target_type" in help_text else "--model_type"
        target_name_flag = "--target_name" if "--target_name" in help_text else "--model_name"
        report_prefix = scan_dir / "garak_report"

        command = [
            sys.executable,
            "-m",
            "garak",
            target_type_flag,
            scan_config.generator.type,
            target_name_flag,
            scan_config.generator.name,
            "--generations",
            str(scan_config.generations),
            "--report_prefix",
            str(report_prefix),
        ]
        _extend_option(command, "--probes", scan_config.probes)
        _extend_option(command, "--detectors", scan_config.detectors)
        _extend_option(command, "--buffs", scan_config.buffs)
        if scan_config.extended_detectors:
            command.append("--extended_detectors")
        if scan_config.seed is not None:
            command.extend(["--seed", str(scan_config.seed)])
        if "--parallel_requests" in help_text:
            command.extend(["--parallel_requests", str(scan_config.parallel_requests)])
        if "--parallel_attempts" in help_text:
            command.extend(["--parallel_attempts", str(scan_config.parallel_attempts)])
        return command


def _ensure_config(config: GarakScanConfig | dict[str, Any]) -> GarakScanConfig:
    if isinstance(config, GarakScanConfig):
        return config
    payload = dict(config)
    generator_payload = dict(payload.get("generator") or {})
    policy_context = dict(payload.get("policy_context") or {})
    policy_id = str(payload.get("policy_id") or policy_context.get("policy_id") or "") or None
    max_attempts = max(1, int(payload.get("max_attempts") or payload.get("generations") or 1))
    return GarakScanConfig(
        scan_id=str(payload.get("scan_id") or uuid.uuid4()),
        target_id=str(payload.get("target_id") or ""),
        policy_id=policy_id,
        scan_profile=str(payload.get("scan_profile") or policy_context.get("scan_profile") or "quick_baseline"),
        vulnerability_categories=[str(item) for item in payload.get("vulnerability_categories") or policy_context.get("vulnerability_categories") or []],
        target_name=str(payload.get("target_name") or policy_context.get("target_name") or "") or None,
        target_type=str(payload.get("target_type") or policy_context.get("target_type") or "") or None,
        generator=GarakGeneratorConfig(
            type=str(generator_payload.get("type") or "test"),
            name=str(generator_payload.get("name") or "Blank"),
            options=dict(generator_payload.get("options") or {}),
        ),
        probes=[str(item) for item in payload.get("probes") or []],
        detectors=[str(item) for item in payload.get("detectors") or []],
        extended_detectors=bool(payload.get("extended_detectors", False)),
        buffs=[str(item) for item in payload.get("buffs") or []],
        generations=max_attempts,
        max_attempts=max_attempts,
        seed=_optional_int(payload.get("seed"), "seed"),
        parallel_requests=max(1, int(payload.get("parallel_requests") or 1)),
        parallel_attempts=max(1, int(payload.get("parallel_attempts") or 1)),
        timeout_seconds=max(1, int(payload.get("timeout_seconds") or 3600)),
        budget=dict(payload.get("budget") or {}),
        permission_attestation=bool(payload.get("permission_attestation", False)),
        judge_settings=dict(payload.get("judge_settings") or {}),
        policy_context=policy_context,
    )


def _validate_scan_config(scan_config: GarakScanConfig) -> None:
    if not scan_config.target_id.strip():
        raise GarakScanValidationError("target_id is required for garak scans")
    _validate_garak_token("generator.type", scan_config.generator.type)
    _validate_garak_token("generator.name", scan_config.generator.name)
    for option_name, values in {
        "probes": scan_config.probes,
        "detectors": scan_config.detectors,
        "buffs": scan_config.buffs,
    }.items():
        for value in values:
            _validate_garak_token(option_name, value)
    if scan_config.generations < 1:
        raise GarakScanValidationError("generations must be at least 1")
    if scan_config.parallel_requests < 1 or scan_config.parallel_attempts < 1:
        raise GarakScanValidationError("parallel request and attempt counts must be at least 1")


def _apply_scan_profile(*, scan_config: GarakScanConfig, version_info: dict[str, Any]) -> None:
    if scan_config.probes or scan_config.detectors or scan_config.buffs:
        scan_config.profile_resolution = {
            "source": "explicit_runner_config",
            "scan_profile": scan_config.scan_profile,
            "categories": scan_config.vulnerability_categories,
            "probes": scan_config.probes,
            "detectors": scan_config.detectors,
            "buffs": scan_config.buffs,
            "skipped": {},
        }
        return

    available_plugins: dict[str, list[str]] | None = None
    if version_info.get("available"):
        try:
            discovered = discover_plugins(timeout_seconds=20)
            available_plugins = discovered.get("plugins") if discovered.get("available") else None
        except Exception:
            available_plugins = None

    try:
        resolution = resolve_scan_profile(
            scan_profile=scan_config.scan_profile,
            vulnerability_categories=scan_config.vulnerability_categories,
            available_plugins=available_plugins,
        )
    except ValueError as exc:
        raise GarakScanValidationError(str(exc)) from exc

    scan_config.profile_resolution = resolution
    scan_config.probes = list(resolution.get("probes") or [])
    scan_config.detectors = list(resolution.get("detectors") or [])
    scan_config.buffs = list(resolution.get("buffs") or [])
    if version_info.get("available") and available_plugins and not scan_config.probes:
        raise GarakScanValidationError(
            "No compatible garak probes were available for the selected scan profile and vulnerability categories."
        )


def _scan_identity(scan_config: GarakScanConfig) -> dict[str, Any]:
    target_name = scan_config.target_name or scan_config.policy_context.get("target_name") or scan_config.target_id
    target_type = scan_config.target_type or scan_config.policy_context.get("target_type")
    policy_id = scan_config.policy_id or scan_config.policy_context.get("policy_id")
    return {
        "target_id": scan_config.target_id,
        "target_name": target_name,
        "target_type": target_type,
        "policy_id": policy_id,
        "scan_profile": scan_config.scan_profile,
        "vulnerability_categories": scan_config.vulnerability_categories,
        "profile_resolution": scan_config.profile_resolution,
    }


def _not_evaluated_result(
    *,
    scan_config: GarakScanConfig,
    scan_dir: Path,
    status: str,
    started_at: str,
    failure_reason: str,
    garak: dict[str, Any],
) -> dict[str, Any]:
    finished_at = _utc_now()
    final_verdict = {
        "verdict": "NOT_EVALUATED",
        "violation_risk": "NOT_AVAILABLE",
        "data_sensitivity": "NOT_AVAILABLE",
        "policy_mode": scan_config.policy_context.get("policy_mode") or scan_config.policy_context.get("mode") or "UNKNOWN",
        "access_context": scan_config.policy_context.get("access_context") or "UNKNOWN",
        "authorization_source": scan_config.policy_context.get("authorization_source") or "NONE",
        "disclosure_type": "NOT_EVALUATED",
        "matched_signals": [],
        "explanation": failure_reason,
    }
    return {
        "scan_id": scan_config.scan_id,
        "status": status,
        "evaluation_status": "not_evaluated",
        "failure_reason": failure_reason,
        "started_at": started_at,
        "finished_at": finished_at,
        **_scan_identity(scan_config),
        "garak": garak,
        "raw_findings": [],
        "scanner_evidence": [],
        "signals": [],
        "findings": [],
        "sprico_final_verdict": final_verdict,
        "final_verdict": "NOT_EVALUATED",
        "risk": "NOT_AVAILABLE",
        "evidence_count": 0,
        "findings_count": 0,
        "aggregate": {
            "final_verdict": "NOT_EVALUATED",
            "worst_risk": "NOT_AVAILABLE",
            "data_sensitivity": "NOT_AVAILABLE",
            "reason": failure_reason,
            "raw_signal_count": 0,
            "evidence_count": 0,
            "findings_count": 0,
        },
        "artifacts": _artifact_refs(scan_dir),
    }


def _failure_reason(scan_dir: Path) -> str:
    stderr_path = scan_dir / "stderr.txt"
    stdout_path = scan_dir / "stdout.txt"
    for path in (stderr_path, stdout_path):
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                return f"Scanner failed before producing usable evidence. {text[:500]}"
    return "Scanner failed before producing usable evidence."


def _validate_garak_token(field_name: str, value: str) -> None:
    token = str(value or "").strip()
    if not token:
        raise GarakScanValidationError(f"{field_name} cannot be empty")
    if token.startswith("-") or not _GARAK_TOKEN_PATTERN.fullmatch(token):
        raise GarakScanValidationError(f"{field_name} contains unsupported garak option characters")


def _optional_int(value: Any, field_name: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise GarakScanValidationError(f"{field_name} must be an integer") from exc


def _garak_help() -> str:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "garak", "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=20,
        )
        return "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    except Exception:
        return ""


def _extend_option(command: list[str], flag: str, values: list[str]) -> None:
    if values:
        command.extend([flag, ",".join(values)])


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _artifact_refs(scan_dir: Path) -> list[dict[str, Any]]:
    if not scan_dir.exists():
        return []
    refs = []
    for path in sorted(item for item in scan_dir.iterdir() if item.is_file()):
        artifact_type = _artifact_type(path)
        refs.append(
            {
                "artifact_id": f"{scan_dir.name}:{path.name}",
                "name": path.name,
                "artifact_type": artifact_type,
                "path": str(path),
                "size": path.stat().st_size,
                "sha256": _sha256(path),
                "created_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            }
        )
    return refs


def _artifact_type(path: Path) -> str:
    name = path.name.lower()
    if "hitlog" in name or "hit" in name:
        return "hitlog"
    if name.endswith(".jsonl") or "report" in name:
        return "report"
    if name == "stdout.txt":
        return "stdout"
    if name == "stderr.txt":
        return "stderr"
    if name == "command.json":
        return "command_metadata"
    if name == "config.json":
        return "scan_config"
    return "artifact"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _redact_command(command: list[str]) -> list[str]:
    redacted: list[str] = []
    for item in command:
        redacted.append(_redact_text(str(item)))
    return redacted


def _redact_text(text: Any) -> str:
    if isinstance(text, str):
        redacted = text
    else:
        try:
            redacted = json.dumps(text, ensure_ascii=True, sort_keys=True, default=str)
        except TypeError:
            redacted = str(text)
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted


def _scanner_evidence_payload(*, finding, artifact_root: Path, scan_id: str) -> dict[str, Any]:
    raw = finding.to_dict()
    artifact_ref = Path(finding.artifact_refs[0]).name if finding.artifact_refs else None
    evidence_id = f"garak_{scan_id}_{uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(raw, sort_keys=True, default=str)).hex[:12]}"
    hit = _scanner_hit(finding)
    return {
        "evidence_id": evidence_id,
        "engine_id": "garak",
        "engine_name": "garak LLM Scanner",
        "engine_type": "scanner",
        "source_type": "external_scanner",
        "engine": finding.engine,
        "engine_version": finding.engine_version,
        "probe": finding.probe_id,
        "detector": finding.detector_id,
        "generator": finding.generator_id,
        "prompt": _redact_text(finding.prompt or "") if finding.prompt is not None else None,
        "output": _redact_text(finding.response or "") if finding.response is not None else None,
        "raw_score": finding.failure_rate if finding.failure_rate is not None else finding.detector_result,
        "raw_status": finding.pass_fail,
        "artifact_ref": artifact_ref,
        "artifact_refs": [artifact_ref] if artifact_ref else [],
        "scanner_result": {
            "probe": finding.probe_id,
            "detector": finding.detector_id,
            "generator": finding.generator_id,
            "hit": hit,
            "score": finding.failure_rate if finding.failure_rate is not None else finding.detector_result,
            "raw_status": finding.pass_fail,
        },
        "raw_record": raw,
        "artifact_set": artifact_root.name,
    }


def _scanner_hit(finding) -> bool:
    text = f"{finding.pass_fail} {finding.detector_result}".lower()
    if any(term in text for term in ("fail", "hit", "true", "success", "vulnerable")):
        return True
    if finding.failure_rate is not None and finding.failure_rate > 0:
        return True
    return False


def _actionable_findings(
    *,
    scan_config: GarakScanConfig,
    scanner_evidence: list[dict[str, Any]],
    final_verdict: dict[str, Any],
    signals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    verdict = str(final_verdict.get("verdict") or "").upper()
    risk = str(final_verdict.get("violation_risk") or "").upper()
    sensitivity = str(final_verdict.get("data_sensitivity") or "").upper()
    actionable = verdict == "FAIL" or risk in {"HIGH", "CRITICAL"} or (
        verdict == "NEEDS_REVIEW" and sensitivity in {"HIGH", "CRITICAL"}
    )
    if not actionable:
        return []

    findings: list[dict[str, Any]] = []
    for index, evidence in enumerate(scanner_evidence or [{}], start=1):
        finding_id = f"garak_finding_{scan_config.scan_id}_{index}"
        findings.append(
            {
                "finding_id": finding_id,
                "id": finding_id,
                "scan_id": scan_config.scan_id,
                "target_id": scan_config.target_id,
                "target_name": scan_config.target_name or scan_config.policy_context.get("target_name") or scan_config.target_id,
                "target_type": scan_config.target_type or scan_config.policy_context.get("target_type"),
                "policy_id": scan_config.policy_id or scan_config.policy_context.get("policy_id"),
                "evidence_id": evidence.get("evidence_id"),
                "artifact_refs": evidence.get("artifact_refs") or [],
                "source": "garak LLM Scanner",
                "source_type": "scanner_evidence",
                "final_sprico_verdict": final_verdict,
                "severity": risk or "MEDIUM",
                "data_sensitivity": sensitivity or final_verdict.get("data_sensitivity"),
                "matched_signals": signals,
                "created_at": _utc_now(),
                "summary": final_verdict.get("explanation") or "SpriCO policy decision created an actionable scanner finding.",
            }
        )
    return findings


def _signals_for_evidence(signals: list[dict[str, Any]], evidence: dict[str, Any]) -> list[dict[str, Any]]:
    probe = str(evidence.get("probe") or "")
    detector = str(evidence.get("detector") or "")
    matched: list[dict[str, Any]] = []
    for signal in signals:
        raw = signal.get("raw") if isinstance(signal, dict) else None
        raw_finding = raw.get("raw_scanner_finding") if isinstance(raw, dict) else None
        if not isinstance(raw_finding, dict):
            continue
        if raw_finding.get("probe_id") == probe and raw_finding.get("detector_id") == detector:
            matched.append(signal)
    return matched


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decision_payload(decision) -> dict[str, Any]:
    return {
        "verdict": decision.verdict,
        "violation_risk": decision.risk,
        "data_sensitivity": decision.data_sensitivity,
        "safety": decision.safety,
        "attack_intent": decision.attack_intent,
        "outcome": decision.outcome,
        "access_context": decision.access_context,
        "authorization_source": decision.authorization_source,
        "policy_mode": decision.policy_mode,
        "purpose": decision.purpose,
        "scope_fit": decision.scope_fit,
        "minimum_necessary": decision.minimum_necessary,
        "disclosure_type": decision.disclosure_type,
        "matched_signals": decision.matched_signals,
        "explanation": decision.explanation,
    }

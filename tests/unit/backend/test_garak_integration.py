import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from pyrit.backend.main import app
from pyrit.backend.sprico.integrations.garak.compatibility import build_compatibility_matrix
from pyrit.backend.sprico.integrations.garak.discovery import _parse_plugin_listing
from pyrit.backend.sprico.integrations.garak.errors import GarakScanValidationError
from pyrit.backend.sprico.integrations.garak.runner import GarakScanRunner
from pyrit.backend.sprico.integrations.garak.normalizer import normalize_findings
from pyrit.backend.sprico.integrations.garak.parser import parse_jsonl_file
from pyrit.backend.sprico.integrations.garak.version import get_garak_version_info
from pyrit.backend.sprico.storage import SqliteStorageBackend


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_parse_plugin_listing_extracts_dynamic_tokens() -> None:
    plugins = _parse_plugin_listing("probes.encoding.InjectBase64\nencoding.InjectHex detectors.always.Fail\n")

    assert "encoding.InjectBase64" in plugins
    assert "encoding.InjectHex" in plugins
    assert "always.Fail" in plugins


def test_compatibility_matrix_serializes_when_garak_absent_or_present() -> None:
    matrix = build_compatibility_matrix()

    assert "garak" in matrix
    assert "features" in matrix
    json.dumps(matrix)


def test_parse_representative_jsonl_and_normalize_signal(tmp_path) -> None:
    path = FIXTURE_DIR / "garak_report.jsonl"

    findings = parse_jsonl_file(path=path, engine_version="test")
    signals = normalize_findings(findings)

    assert findings[0].probe_id == "leakreplay.GuardianComplete"
    assert signals[0].requires_authorization is True
    assert signals[0].data_sensitivity == "HIGH"


def test_parse_hitlog_jsonl_and_normalize_signal() -> None:
    findings = parse_jsonl_file(path=FIXTURE_DIR / "garak_hitlog.jsonl", engine_version="test")
    signals = normalize_findings(findings)

    assert findings[0].probe_id == "promptinject.HijackHateHumans"
    assert findings[1].detector_id == "leakreplay.StartsWith"
    assert signals[0].category == "data_leakage"


def test_garak_status_schema_has_install_hint_when_unavailable() -> None:
    status = get_garak_version_info()

    assert {"available", "version", "python", "executable", "import_error", "cli_error", "install_hint"} <= set(status)
    assert "advanced" in status
    assert "python_executable" in status["advanced"]
    if not status["available"]:
        assert "pip install" in status["install_hint"]


def test_judge_status_returns_openai_provider_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SPRICO_OPENAI_JUDGE_ENABLED", raising=False)
    monkeypatch.delenv("SPRICO_OPENAI_JUDGE_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(app)

    response = client.get("/api/judge/status")

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["configured"] is False
    assert body["final_verdict_authority"] == "sprico_policy_decision_engine"
    provider = body["providers"][0]
    assert provider["id"] == "openai"
    assert provider["configured"] is False
    assert provider["enabled_by_default"] is False
    assert provider["final_verdict_capable"] is False
    assert provider["supports_redaction"] is True
    assert provider["allowed_modes"] == ["disabled", "redacted"]
    assert "healthcare" in provider["blocked_for_domains_by_default"]


def test_garak_scan_api_rejects_missing_target_id() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/scans/garak",
        json={
            "permission_attestation": True,
            "generator": {"type": "test", "name": "Blank"},
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "validation_failed"
    assert body["message"] == "Cannot start scanner run."
    assert body["details"] == [{"field": "target_id", "reason": "Target is required."}]
    assert "Select a configured target." in body["next_steps"]


def test_garak_scan_api_rejects_missing_permission_attestation() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/scans/garak",
        json={
            "target_id": "OpenAIVectorStoreTarget::safe",
            "policy_id": "policy_hospital_strict_v1",
            "permission_attestation": False,
            "generator": {"type": "test", "name": "Blank"},
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "validation_failed"
    assert body["details"] == [
        {"field": "permission_attestation", "reason": "Permission attestation is required."}
    ]


def test_garak_scan_api_rejects_disallowed_profile() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/scans/garak",
        json={
            "target_id": "OpenAIVectorStoreTarget::safe",
            "policy_id": "policy_hospital_strict_v1",
            "scan_profile": "unsafe_profile",
            "permission_attestation": True,
            "generator": {"type": "test", "name": "Blank"},
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "validation_failed"
    assert body["details"][0]["field"] == "scan_profile"
    assert "not allowed" in body["details"][0]["reason"]


def test_garak_scan_rejects_openai_judge_when_not_configured(monkeypatch) -> None:
    import pyrit.backend.routes.garak as garak_routes

    monkeypatch.delenv("SPRICO_OPENAI_JUDGE_ENABLED", raising=False)
    monkeypatch.delenv("SPRICO_OPENAI_JUDGE_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    class FakeTargetService:
        async def get_target_config_async(self, *, target_registry_name: str):
            return SimpleNamespace(
                target_registry_name=target_registry_name,
                display_name="SpriCo Hospital Data",
                target_type="OpenAIVectorStoreTarget",
                endpoint="https://api.openai.com/v1",
                model_name="gpt-4.1",
                provider_settings={"target_domain": "Healthcare"},
                runtime_summary={},
            )

    monkeypatch.setattr(garak_routes, "get_target_service", lambda: FakeTargetService())
    client = TestClient(app)

    response = client.post(
        "/api/scans/garak",
        json={
            "target_id": "healthcare-target",
            "policy_id": "policy_hospital_strict_v1",
            "scan_profile": "quick_baseline",
            "vulnerability_categories": ["Privacy & Data Leakage"],
            "permission_attestation": True,
            "judge_settings": {"enabled": True, "provider": "openai", "mode": "redacted", "judge_only_ambiguous": True},
            "policy_context": {"policy_domain": "hospital", "policy_mode": "REDTEAM_STRICT"},
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "validation_failed"
    assert body["details"][0]["field"] == "judge_settings"
    assert "not configured" in body["details"][0]["reason"]


def test_garak_scan_accepts_judge_disabled_without_configuration(monkeypatch) -> None:
    import pyrit.backend.routes.garak as garak_routes

    monkeypatch.delenv("SPRICO_OPENAI_JUDGE_ENABLED", raising=False)
    monkeypatch.delenv("SPRICO_OPENAI_JUDGE_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    captured_payload: dict[str, object] = {}

    class FakeTargetService:
        async def get_target_config_async(self, *, target_registry_name: str):
            return SimpleNamespace(
                target_registry_name=target_registry_name,
                display_name="SpriCo Hospital Data",
                target_type="OpenAIVectorStoreTarget",
                endpoint="https://api.openai.com/v1",
                model_name="gpt-4.1",
                provider_settings={"target_domain": "Healthcare"},
                runtime_summary={},
            )

    def fake_run(payload: dict[str, object]) -> dict[str, object]:
        captured_payload.update(payload)
        return {
            "scan_id": "scan-ok",
            "status": "completed_no_findings",
            "evaluation_status": "evaluated",
            "sprico_final_verdict": {"verdict": "PASS", "violation_risk": "LOW"},
            "aggregate": {"final_verdict": "PASS", "worst_risk": "LOW"},
        }

    monkeypatch.setattr(garak_routes, "get_target_service", lambda: FakeTargetService())
    monkeypatch.setattr(garak_routes._runner, "run", fake_run)
    client = TestClient(app)

    response = client.post(
        "/api/scans/garak",
        json={
            "target_id": "healthcare-target",
            "policy_id": "policy_hospital_strict_v1",
            "scan_profile": "quick_baseline",
            "vulnerability_categories": ["Privacy & Data Leakage"],
            "permission_attestation": True,
            "judge_settings": {"enabled": False, "provider": "openai", "mode": "redacted", "judge_only_ambiguous": True},
            "policy_context": {"policy_domain": "hospital", "policy_mode": "REDTEAM_STRICT"},
        },
    )

    assert response.status_code == 201
    assert captured_payload["judge_settings"] == {
        "enabled": False,
        "provider": "openai",
        "mode": "redacted",
        "judge_only_ambiguous": True,
    }


def test_garak_scan_rejects_healthcare_raw_judge_mode_by_default(monkeypatch) -> None:
    import pyrit.backend.routes.garak as garak_routes

    monkeypatch.setenv("SPRICO_OPENAI_JUDGE_ENABLED", "true")
    monkeypatch.setenv("SPRICO_OPENAI_JUDGE_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("SPRICO_OPENAI_JUDGE_ALLOW_RAW", raising=False)

    class FakeTargetService:
        async def get_target_config_async(self, *, target_registry_name: str):
            return SimpleNamespace(
                target_registry_name=target_registry_name,
                display_name="SpriCo Hospital Data",
                target_type="OpenAIVectorStoreTarget",
                endpoint="https://api.openai.com/v1",
                model_name="gpt-4.1",
                provider_settings={"target_domain": "Healthcare"},
                runtime_summary={},
            )

    monkeypatch.setattr(garak_routes, "get_target_service", lambda: FakeTargetService())
    client = TestClient(app)

    response = client.post(
        "/api/scans/garak",
        json={
            "target_id": "healthcare-target",
            "policy_id": "policy_hospital_strict_v1",
            "scan_profile": "quick_baseline",
            "vulnerability_categories": ["Privacy & Data Leakage"],
            "permission_attestation": True,
            "judge_settings": {"enabled": True, "provider": "openai", "mode": "raw", "judge_only_ambiguous": True},
            "policy_context": {"policy_domain": "hospital", "policy_mode": "REDTEAM_STRICT"},
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["details"][0] == {
        "field": "judge_settings.mode",
        "reason": "Healthcare/PHI scans require redacted judge evidence mode by default.",
    }


def test_garak_scan_accepts_configured_redacted_judge_as_evidence_only(monkeypatch) -> None:
    import pyrit.backend.routes.garak as garak_routes

    monkeypatch.setenv("SPRICO_OPENAI_JUDGE_ENABLED", "true")
    monkeypatch.setenv("SPRICO_OPENAI_JUDGE_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    captured_payload: dict[str, object] = {}

    class FakeTargetService:
        async def get_target_config_async(self, *, target_registry_name: str):
            return SimpleNamespace(
                target_registry_name=target_registry_name,
                display_name="SpriCo Hospital Data",
                target_type="OpenAIVectorStoreTarget",
                endpoint="https://api.openai.com/v1",
                model_name="gpt-4.1",
                provider_settings={"target_domain": "Healthcare"},
                runtime_summary={},
            )

    def fake_run(payload: dict[str, object]) -> dict[str, object]:
        captured_payload.update(payload)
        return {
            "scan_id": "scan-ok",
            "status": "completed_no_findings",
            "evaluation_status": "evaluated",
            "sprico_final_verdict": {"verdict": "PASS", "violation_risk": "LOW"},
            "aggregate": {"final_verdict": "PASS", "worst_risk": "LOW"},
        }

    monkeypatch.setattr(garak_routes, "get_target_service", lambda: FakeTargetService())
    monkeypatch.setattr(garak_routes._runner, "run", fake_run)
    client = TestClient(app)

    response = client.post(
        "/api/scans/garak",
        json={
            "target_id": "healthcare-target",
            "policy_id": "policy_hospital_strict_v1",
            "scan_profile": "quick_baseline",
            "vulnerability_categories": ["Privacy & Data Leakage"],
            "permission_attestation": True,
            "judge_settings": {"enabled": True, "provider": "openai", "mode": "redacted", "judge_only_ambiguous": True},
            "policy_context": {"policy_domain": "hospital", "policy_mode": "REDTEAM_STRICT"},
        },
    )

    assert response.status_code == 201
    assert captured_payload["judge_settings"] == {
        "enabled": True,
        "provider": "openai",
        "mode": "redacted",
        "judge_only_ambiguous": True,
    }
    assert captured_payload["policy_context"]["judge_settings"]["enabled"] is True


def test_garak_scan_request_accepts_cross_domain_override_field_without_extra_field_422() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/scans/garak",
        json={
            "target_id": "__missing_target__",
            "policy_id": "policy_hospital_strict_v1",
            "scan_profile": "quick_baseline",
            "vulnerability_categories": ["Privacy & Data Leakage"],
            "permission_attestation": True,
            "cross_domain_override": False,
        },
    )

    assert response.status_code != 422
    body = response.json()
    assert body["error"] == "validation_failed"
    assert body["details"][0]["field"] == "target_id"
    assert "cross_domain_override" not in json.dumps(body)


def test_garak_scan_api_rejects_raw_cli_args() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/scans/garak",
        json={
            "target_id": "OpenAIVectorStoreTarget::safe",
            "policy_id": "policy_hospital_strict_v1",
            "scan_profile": "quick_baseline",
            "permission_attestation": True,
            "raw_cli_args": ["--help"],
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "Request validation failed"
    assert body["errors"] == [
        {"field": "body.raw_cli_args", "message": "Extra inputs are not permitted", "code": "extra_forbidden"}
    ]


def test_runner_keeps_scanner_evidence_separate_from_final_verdict(tmp_path) -> None:
    scan_dir = tmp_path / "scan"
    scan_dir.mkdir()
    report = scan_dir / "sample.jsonl"
    report.write_text((FIXTURE_DIR / "garak_report.jsonl").read_text(encoding="utf-8"), encoding="utf-8")

    findings = parse_jsonl_file(path=report, engine_version="fixture")
    signals = normalize_findings(findings)

    assert findings[0].to_dict()["engine"] == "garak"
    assert signals[0].to_dict()["raw"]["raw_scanner_finding"]["probe_id"] == "leakreplay.GuardianComplete"


def test_runner_rejects_cli_option_injection_before_execution(tmp_path) -> None:
    runner = GarakScanRunner(artifact_root=tmp_path)

    with pytest.raises(GarakScanValidationError):
        runner.run(
            {
                "target_id": "mock_hospital_target",
                "generator": {"type": "test", "name": "Blank --help"},
                "probes": ["--help"],
                "detectors": [],
                "permission_attestation": True,
                "policy_context": {"policy_mode": "REDTEAM_STRICT"},
            }
        )


def test_runner_persists_artifacts_evidence_history_and_findings(tmp_path, monkeypatch) -> None:
    from pyrit.backend.sprico.integrations.garak import runner as runner_module

    backend = SqliteStorageBackend(tmp_path / "sprico.sqlite3")

    def fake_run(command, **kwargs):
        assert isinstance(command, list)
        assert kwargs.get("shell") is False
        scan_dir = Path(kwargs["cwd"])
        (scan_dir / "garak_report.jsonl").write_text(
            (FIXTURE_DIR / "garak_report.jsonl").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(
        runner_module,
        "get_garak_version_info",
        lambda: {
            "available": True,
            "version": "fixture",
            "install_hint": "python -m pip install -e \".[garak]\"",
            "advanced": {"python_executable": "python", "import_error": None, "cli_error": None},
        },
    )
    monkeypatch.setattr(runner_module, "discover_plugins", lambda timeout_seconds=20: {"available": False, "plugins": {}})
    monkeypatch.setattr(runner_module, "_garak_help", lambda: "--model_type --model_name --parallel_requests --parallel_attempts")
    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)

    runner = GarakScanRunner(artifact_root=tmp_path / "garak_scans", backend=backend)
    result = runner.run(
        {
            "target_id": "target-1",
            "target_name": "Fixture Target",
            "target_type": "OpenAIVectorStoreTarget",
            "policy_id": "policy_hospital_strict_v1",
            "scan_profile": "quick_baseline",
            "vulnerability_categories": ["Privacy & Data Leakage"],
            "generator": {"type": "test", "name": "Blank"},
            "permission_attestation": True,
            "policy_context": {
                "policy_id": "policy_hospital_strict_v1",
                "policy_mode": "REDTEAM_STRICT",
                "access_context": "UNKNOWN",
                "authorization_source": "NONE",
                "target_name": "Fixture Target",
                "target_type": "OpenAIVectorStoreTarget",
            },
        }
    )

    assert result["status"] == "completed"
    assert result["scanner_evidence"][0]["engine_id"] == "garak"
    assert result["scanner_evidence"][0]["scanner_result"]["hit"] is True
    assert result["sprico_final_verdict"]["verdict"] == "FAIL"
    assert result["findings"]
    assert backend.get_record("garak_runs", result["scan_id"]) is not None
    assert backend.list_records("garak_artifacts")[0]["sha256"]
    assert backend.list_records("evidence_items")[0]["source_type"] == "external_scanner"
    assert backend.list_records("findings")[0]["scan_id"] == result["scan_id"]


def test_timeout_scan_result_maps_to_not_evaluated(tmp_path, monkeypatch) -> None:
    from pyrit.backend.sprico.integrations.garak import runner as runner_module

    backend = SqliteStorageBackend(tmp_path / "sprico.sqlite3")

    def fake_run(command, **kwargs):
        raise runner_module.subprocess.TimeoutExpired(cmd=command, timeout=1, output="partial", stderr="timed out")

    monkeypatch.setattr(runner_module, "get_garak_version_info", lambda: {"available": True, "version": "fixture"})
    monkeypatch.setattr(runner_module, "discover_plugins", lambda timeout_seconds=20: {"available": False, "plugins": {}})
    monkeypatch.setattr(runner_module, "_garak_help", lambda: "--model_type --model_name")
    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)

    runner = GarakScanRunner(artifact_root=tmp_path / "garak_scans", backend=backend)
    result = runner.run(
        {
            "target_id": "target-1",
            "generator": {"type": "test", "name": "Blank"},
            "permission_attestation": True,
            "timeout_seconds": 1,
            "policy_context": {"policy_mode": "REDTEAM_STRICT"},
        }
    )

    assert result["status"] == "timeout"
    assert result["evaluation_status"] == "not_evaluated"
    assert result["sprico_final_verdict"]["verdict"] == "NOT_EVALUATED"
    assert result["sprico_final_verdict"]["violation_risk"] == "NOT_AVAILABLE"
    assert result["aggregate"]["final_verdict"] != "PASS"
    assert result["aggregate"]["worst_risk"] != "LOW"
    assert result["evidence_count"] == 0


def test_failed_scan_result_maps_to_not_evaluated(tmp_path, monkeypatch) -> None:
    from pyrit.backend.sprico.integrations.garak import runner as runner_module

    backend = SqliteStorageBackend(tmp_path / "sprico.sqlite3")

    def fake_run(command, **kwargs):
        return SimpleNamespace(returncode=2, stdout="", stderr="garak failed")

    monkeypatch.setattr(runner_module, "get_garak_version_info", lambda: {"available": True, "version": "fixture"})
    monkeypatch.setattr(runner_module, "discover_plugins", lambda timeout_seconds=20: {"available": False, "plugins": {}})
    monkeypatch.setattr(runner_module, "_garak_help", lambda: "--model_type --model_name")
    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)

    runner = GarakScanRunner(artifact_root=tmp_path / "garak_scans", backend=backend)
    result = runner.run(
        {
            "target_id": "target-1",
            "generator": {"type": "test", "name": "Blank"},
            "permission_attestation": True,
            "policy_context": {"policy_mode": "REDTEAM_STRICT"},
        }
    )

    assert result["status"] == "failed"
    assert result["evaluation_status"] == "not_evaluated"
    assert result["sprico_final_verdict"]["verdict"] == "NOT_EVALUATED"
    assert result["risk"] == "NOT_AVAILABLE"


def test_unavailable_scan_result_maps_to_not_evaluated(tmp_path, monkeypatch) -> None:
    from pyrit.backend.sprico.integrations.garak import runner as runner_module

    backend = SqliteStorageBackend(tmp_path / "sprico.sqlite3")
    monkeypatch.setattr(
        runner_module,
        "get_garak_version_info",
        lambda: {
            "available": False,
            "version": None,
            "install_hint": "python -m pip install -e \".[garak]\"",
            "import_error": "missing",
        },
    )

    runner = GarakScanRunner(artifact_root=tmp_path / "garak_scans", backend=backend)
    result = runner.run(
        {
            "target_id": "target-1",
            "generator": {"type": "test", "name": "Blank"},
            "permission_attestation": True,
            "policy_context": {"policy_mode": "REDTEAM_STRICT"},
        }
    )

    assert result["status"] == "unavailable"
    assert result["evaluation_status"] == "not_evaluated"
    assert result["aggregate"]["final_verdict"] == "NOT_EVALUATED"
    assert result["aggregate"]["worst_risk"] == "NOT_AVAILABLE"


def test_runner_does_not_create_finding_for_low_risk_no_hit(tmp_path, monkeypatch) -> None:
    from pyrit.backend.sprico.integrations.garak import runner as runner_module

    backend = SqliteStorageBackend(tmp_path / "sprico.sqlite3")

    def fake_run(command, **kwargs):
        scan_dir = Path(kwargs["cwd"])
        (scan_dir / "garak_report.jsonl").write_text(
            '{"probe":"promptinject.HijackHateHumans","detector":"always.Pass","generator":"test.Blank","prompt":"ignore","response":"I cannot comply.","status":"pass","failure_rate":0.0}\n',
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(
        runner_module,
        "get_garak_version_info",
        lambda: {"available": True, "version": "fixture", "advanced": {"python_executable": "python"}},
    )
    monkeypatch.setattr(runner_module, "discover_plugins", lambda timeout_seconds=20: {"available": False, "plugins": {}})
    monkeypatch.setattr(runner_module, "_garak_help", lambda: "--model_type --model_name")
    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)

    runner = GarakScanRunner(artifact_root=tmp_path / "garak_scans", backend=backend)
    result = runner.run(
        {
            "target_id": "target-1",
            "generator": {"type": "test", "name": "Blank"},
            "permission_attestation": True,
            "policy_context": {"policy_mode": "REDTEAM_STRICT"},
        }
    )

    assert result["status"] == "completed_no_findings"
    assert result["evaluation_status"] == "evaluated"
    assert result["aggregate"]["final_verdict"] == "PASS"
    assert result["aggregate"]["worst_risk"] == "LOW"
    assert result["findings"] == []
    assert backend.list_records("findings") == []


def test_garak_scan_api_blocks_domain_mismatch_unless_override(monkeypatch) -> None:
    import pyrit.backend.routes.garak as garak_routes

    captured_payload: dict[str, object] = {}

    class FakeTargetService:
        async def get_target_config_async(self, *, target_registry_name: str):
            return SimpleNamespace(
                target_registry_name=target_registry_name,
                display_name="SpriCo HR Data",
                target_type="OpenAIVectorStoreTarget",
                endpoint="https://api.openai.com/v1",
                model_name="gpt-4.1",
                provider_settings={"target_domain": "HR"},
                runtime_summary={},
            )

    monkeypatch.setattr(garak_routes, "get_target_service", lambda: FakeTargetService())

    def fake_run(payload: dict[str, object]) -> dict[str, object]:
        captured_payload.update(payload)
        return {
            "scan_id": "scan-ok",
            "status": "completed_no_findings",
            "evaluation_status": "evaluated",
            "sprico_final_verdict": {"verdict": "PASS", "violation_risk": "LOW"},
            "aggregate": {"final_verdict": "PASS", "worst_risk": "LOW"},
        }

    monkeypatch.setattr(
        garak_routes._runner,
        "run",
        fake_run,
    )
    client = TestClient(app)
    request = {
        "target_id": "hr-target",
        "policy_id": "policy_hospital_strict_v1",
        "scan_profile": "quick_baseline",
        "vulnerability_categories": ["Privacy & Data Leakage"],
        "permission_attestation": True,
        "policy_context": {"policy_domain": "hospital", "policy_mode": "REDTEAM_STRICT"},
    }

    blocked = client.post("/api/scans/garak", json=request)
    assert blocked.status_code == 400
    blocked_body = blocked.json()
    assert blocked_body["error"] == "validation_failed"
    assert blocked_body["details"][0]["field"] == "cross_domain_override"
    assert blocked_body["details"][0]["reason"] == "Target domain HR does not match policy domain healthcare."
    assert blocked_body["next_steps"] == [
        "Choose a matching policy pack.",
        "Or confirm cross-domain evaluation if this is intentional.",
    ]

    allowed = client.post("/api/scans/garak", json=request | {"cross_domain_override": True})
    assert allowed.status_code == 201
    assert allowed.json()["evaluation_status"] == "evaluated"
    assert captured_payload["cross_domain_override"] is True
    assert captured_payload["policy_context"]["cross_domain_override"] is True


def test_garak_scan_api_treats_healthcare_and_hospital_domains_as_compatible(monkeypatch) -> None:
    import pyrit.backend.routes.garak as garak_routes

    captured_payload: dict[str, object] = {}

    class FakeTargetService:
        async def get_target_config_async(self, *, target_registry_name: str):
            return SimpleNamespace(
                target_registry_name=target_registry_name,
                display_name="SpriCo Hospital Data",
                target_type="OpenAIVectorStoreTarget",
                endpoint="https://api.openai.com/v1",
                model_name="gpt-4.1",
                provider_settings={"target_domain": "Healthcare"},
                runtime_summary={},
            )

    def fake_run(payload: dict[str, object]) -> dict[str, object]:
        captured_payload.update(payload)
        return {
            "scan_id": "scan-ok",
            "status": "completed_no_findings",
            "evaluation_status": "evaluated",
            "sprico_final_verdict": {"verdict": "PASS", "violation_risk": "LOW"},
            "aggregate": {"final_verdict": "PASS", "worst_risk": "LOW"},
        }

    monkeypatch.setattr(garak_routes, "get_target_service", lambda: FakeTargetService())
    monkeypatch.setattr(garak_routes._runner, "run", fake_run)

    client = TestClient(app)
    response = client.post(
        "/api/scans/garak",
        json={
            "target_id": "healthcare-target",
            "policy_id": "policy_hospital_strict_v1",
            "scan_profile": "quick_baseline",
            "vulnerability_categories": ["Privacy & Data Leakage"],
            "permission_attestation": True,
            "policy_context": {"policy_domain": "hospital", "policy_mode": "REDTEAM_STRICT"},
        },
    )

    assert response.status_code == 201
    assert response.json()["evaluation_status"] == "evaluated"
    assert captured_payload["cross_domain_override"] is False
    assert captured_payload["policy_context"]["selected_target_domain"] == "Healthcare"
    assert captured_payload["policy_context"]["policy_domain"] == "hospital"


def test_garak_incompatible_target_returns_validation_error(monkeypatch) -> None:
    import pyrit.backend.routes.garak as garak_routes

    class FakeTargetService:
        async def get_target_config_async(self, *, target_registry_name: str):
            return SimpleNamespace(
                target_registry_name=target_registry_name,
                display_name="Gemini File Search",
                target_type="GeminiFileSearchTarget",
                endpoint="https://generativelanguage.googleapis.com/v1beta/",
                model_name="gemini-2.5-flash",
                provider_settings={"target_domain": "General AI"},
                runtime_summary={},
            )

    monkeypatch.setattr(garak_routes, "get_target_service", lambda: FakeTargetService())

    client = TestClient(app)
    response = client.post(
        "/api/scans/garak",
        json={
            "target_id": "gemini-target",
            "policy_id": "policy_public_default",
            "scan_profile": "quick_baseline",
            "vulnerability_categories": ["Prompt Injection & Jailbreaks"],
            "permission_attestation": True,
            "policy_context": {"policy_domain": "general", "policy_mode": "REDTEAM_STRICT"},
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "validation_failed"
    assert body["details"][0]["field"] == "target_id"
    assert "GeminiFileSearchTarget requires explicit scanner generator mapping" in body["details"][0]["reason"]


def test_garak_run_report_api_returns_completed_no_findings_and_profile_resolution(monkeypatch) -> None:
    import pyrit.backend.routes.garak as garak_routes

    run = {
        "scan_id": "scan-no-findings",
        "status": "completed_no_findings",
        "evaluation_status": "evaluated",
        "target_id": "target-1",
        "target_name": "No Finding Target",
        "target_type": "OpenAIVectorStoreTarget",
        "policy_id": "policy_hospital_strict_v1",
        "scan_profile": "quick_baseline",
        "vulnerability_categories": ["Privacy & Data Leakage"],
        "started_at": "2026-04-21T07:48:20+00:00",
        "finished_at": "2026-04-21T07:48:25+00:00",
        "profile_resolution": {
            "probes": ["probe.One"],
            "detectors": [],
            "buffs": [],
            "skipped": {"probes": ["probe.Missing"]},
            "default_generations": 1,
            "default_timeout_seconds": 180,
        },
        "scanner_evidence": [],
        "signals": [],
        "findings": [],
        "evidence_count": 0,
        "findings_count": 0,
        "artifacts": [{"artifact_type": "command_metadata", "name": "command.json"}],
        "sprico_final_verdict": {"verdict": "PASS", "violation_risk": "LOW", "data_sensitivity": "LOW"},
        "aggregate": {"final_verdict": "PASS", "worst_risk": "LOW", "data_sensitivity": "LOW"},
        "config": {"profile_resolution": {"default_timeout_seconds": 180}},
    }
    monkeypatch.setattr(garak_routes._runner, "list_scans", lambda: [run])
    monkeypatch.setattr(garak_routes._runner, "get_scan", lambda scan_id: run if scan_id == "scan-no-findings" else None)
    client = TestClient(app)

    response = client.get("/api/scans/garak/reports")

    assert response.status_code == 200
    body = response.json()
    assert body["reports"][0]["scan_id"] == "scan-no-findings"
    assert body["reports"][0]["status"] == "completed_no_findings"
    assert body["reports"][0]["resolved_probes_count"] == 1
    assert body["reports"][0]["skipped_probes_count"] == 1
    assert body["reports"][0]["timeout_seconds"] == 180
    assert body["reports"][0]["duration_seconds"] == 5
    assert body["reports"][0]["artifact_count"] == 1
    assert body["reports"][0]["artifact_summary"][0]["label"] == "command metadata"
    assert body["reports"][0]["artifact_summary"][0]["status"] == "saved"
    assert body["summary"]["scanner_runs_total"] == 1
    assert body["summary"]["scanner_runs_with_no_findings"] == 1


def test_garak_reports_path_is_not_treated_as_scan_id(monkeypatch) -> None:
    import pyrit.backend.routes.garak as garak_routes

    monkeypatch.setattr(garak_routes._runner, "list_scans", lambda: [])
    client = TestClient(app)

    response = client.get("/api/scans/garak/reports")

    assert response.status_code == 200
    assert response.json() == {
        "reports": [],
        "summary": {
            "scanner_runs_total": 0,
            "scanner_runs_by_status": [],
            "scanner_runs_by_target": [],
            "scanner_runs_by_profile": [],
            "scanner_runs_with_findings": 0,
            "scanner_runs_with_no_findings": 0,
            "scanner_runs_timeout": 0,
            "scanner_runs_failed": 0,
            "high_critical_scanner_findings": 0,
            "scanner_findings_by_severity": [],
            "scanner_evidence_count": 0,
            "artifacts_stored": 0,
        },
    }


def test_garak_report_summary_includes_scanner_runs_with_findings(monkeypatch) -> None:
    import pyrit.backend.routes.garak as garak_routes

    run = {
        "scan_id": "scan-with-finding",
        "status": "completed",
        "evaluation_status": "evaluated",
        "target_id": "target-1",
        "target_name": "Finding Target",
        "policy_id": "policy_hospital_strict_v1",
        "scan_profile": "deep_llm_security",
        "profile_resolution": {"probes": ["probe.One", "probe.Two"], "default_timeout_seconds": 600},
        "scanner_evidence": [{"evidence_id": "evidence-1"}],
        "signals": [{"category": "data_leakage"}],
        "findings": [{"finding_id": "finding-1", "scan_id": "scan-with-finding", "severity": "HIGH"}],
        "evidence_count": 1,
        "findings_count": 1,
        "artifacts": [{}, {}],
        "sprico_final_verdict": {"verdict": "FAIL", "violation_risk": "HIGH", "data_sensitivity": "HIGH"},
        "aggregate": {"final_verdict": "FAIL", "worst_risk": "HIGH", "data_sensitivity": "HIGH"},
    }
    monkeypatch.setattr(garak_routes._runner, "list_scans", lambda: [run])
    monkeypatch.setattr(garak_routes._runner, "get_scan", lambda scan_id: run if scan_id == "scan-with-finding" else None)
    client = TestClient(app)

    report_response = client.get("/api/scans/garak/reports/scan-with-finding")
    summary_response = client.get("/api/scans/garak/reports/summary")

    assert report_response.status_code == 200
    report = report_response.json()
    assert report["finding_ids"] == ["finding-1"]
    assert report["findings"][0]["scan_id"] == "scan-with-finding"
    assert report["timeout_seconds"] == 600
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["scanner_runs_total"] == 1
    assert summary["scanner_runs_with_findings"] == 1
    assert summary["high_critical_scanner_findings"] == 1
    assert summary["scanner_findings_by_severity"] == [{"severity": "HIGH", "count": 1}]
    assert summary["scanner_evidence_count"] == 1
    assert summary["artifacts_stored"] == 2


def test_storage_status_endpoint_returns_safe_metadata() -> None:
    client = TestClient(app)

    response = client.get("/api/storage/status")

    assert response.status_code == 200
    body = response.json()
    assert body["storage_backend"] in {"sqlite", "json"}
    assert "sprico_sqlite_path" in body
    assert "garak_artifacts_path" in body
    assert "record_counts" in body
    assert {"scanner_runs", "red_scans", "shield_events", "evidence", "findings", "policies", "projects", "conditions", "pyrit_attacks", "audit_runs"} <= set(body["record_counts"])


def test_real_garak_smoke_path_skips_when_optional_dependency_absent(tmp_path) -> None:
    if os.getenv("GARAK_TEST_ENABLED") != "1":
        pytest.skip("GARAK_TEST_ENABLED=1 is required for real garak smoke execution.")
    status = get_garak_version_info()
    if not status["available"]:
        pytest.skip(f"garak optional extra is unavailable: {status.get('import_error') or status.get('cli_error')}")
    generator_type = os.getenv("GARAK_TEST_GENERATOR_TYPE", "test")
    generator_name = os.getenv("GARAK_TEST_GENERATOR", "Blank")
    probe = os.getenv("GARAK_TEST_PROBE", "encoding.InjectBase64")

    runner = GarakScanRunner(
        artifact_root=tmp_path / "garak_scans",
        backend=SqliteStorageBackend(tmp_path / "sprico_smoke.sqlite3"),
    )
    result = runner.run(
        {
            "target_id": os.getenv("GARAK_TEST_TARGET", "local_garak_test_target"),
            "generator": {"type": generator_type, "name": generator_name},
            "scan_profile": os.getenv("GARAK_TEST_PROFILE", "quick_baseline"),
            "probes": [probe],
            "detectors": [],
            "generations": 1,
            "timeout_seconds": 90,
            "permission_attestation": True,
            "policy_context": {"policy_mode": "REDTEAM_STRICT"},
        }
    )

    assert result["status"] in {"completed", "failed", "timeout"}
    assert "scanner_evidence" in result
    assert "sprico_final_verdict" in result

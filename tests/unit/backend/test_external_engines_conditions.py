from fastapi.testclient import TestClient
import pytest

from pyrit.backend.main import app
from pyrit.backend.sprico.conditions import ConditionLifecycleError, SpriCOConditionStore
from pyrit.backend.sprico.external_engines import external_engine_matrix
from pyrit.backend.sprico.storage import SqliteStorageBackend


def test_legal_metadata_route_uses_whitelisted_components() -> None:
    client = TestClient(app)

    response = client.get("/api/legal/open-source-components")

    assert response.status_code == 200
    component_ids = {item["id"] for item in response.json()}
    assert {"garak", "deepteam", "promptfoo"} <= component_ids
    assert all("third_party/" in item["license_file"] for item in response.json())


def test_license_registry_rejects_unknown_component_id() -> None:
    client = TestClient(app)

    response = client.get("/api/legal/open-source-components/unknown/license")

    assert response.status_code == 404


def test_known_license_file_can_be_read_without_arbitrary_path_parameter() -> None:
    client = TestClient(app)

    response = client.get("/api/legal/open-source-components/garak/license")

    assert response.status_code == 200
    assert "Apache License" in response.text


def test_external_engine_classification_excludes_final_verdict_engines() -> None:
    matrix = external_engine_matrix()

    assert matrix["final_verdict_authority"]["id"] == "sprico_policy_decision_engine"
    assert matrix["final_verdict_authority"]["final_verdict_capable"] is True
    assert matrix["final_verdict_authority"]["can_produce_final_verdict"] is True
    assert matrix["final_verdict_authority"]["locked_for_regulated_domains"] is True
    assert matrix["regulated_domain_lock"]["locked"] is True
    assert {item["id"] for item in matrix["attack_engines"]} == {
        "sprico_manual",
        "pyrit",
        "garak",
        "deepteam",
        "promptfoo_import_or_assertions",
    }
    assert {item["id"] for item in matrix["evidence_engines"]} == {
        "sprico_domain_signals",
        "garak_detector",
        "deepteam_metric",
        "promptfoo_assertion",
        "pyrit_scorer",
        "openai_judge",
    }
    assert not any(item["final_verdict_capable"] for item in matrix["attack_engines"] + matrix["evidence_engines"])
    assert not any(item["can_produce_final_verdict"] for item in matrix["attack_engines"] + matrix["evidence_engines"])
    assert any(item["can_generate_attacks"] for item in matrix["attack_engines"])
    assert any(item["can_generate_evidence"] for item in matrix["evidence_engines"])


def test_custom_condition_lifecycle_requires_simulation_tests_and_approval(tmp_path) -> None:
    backend = SqliteStorageBackend(path=tmp_path / "sprico.sqlite3")
    store = SpriCOConditionStore(backend=backend)
    condition = store.create_condition(
        {
            "condition_id": "cond_test_phi",
            "name": "Patient name keyword",
            "condition_type": "keyword_match",
            "parameters": {"keywords": ["patient"]},
            "author": "policy-author",
            "domain": "hospital",
            "policy_modes": ["REDTEAM_STRICT"],
        }
    )

    with pytest.raises(ConditionLifecycleError):
        store.activate_condition(condition["condition_id"])

    simulation = store.simulate_condition(condition["condition_id"], {"text": "patient record", "actor": "policy-author"})
    assert simulation["matched"] is True
    store.add_test_case(
        condition["condition_id"],
        {"name": "positive", "input_text": "patient record", "expected_match": True, "actor": "policy-author"},
    )
    store.add_test_case(
        condition["condition_id"],
        {"name": "negative", "input_text": "public visiting hours", "expected_match": False, "actor": "policy-author"},
    )
    approved = store.approve_condition(condition["condition_id"], {"approver": "approver-1"})
    assert approved["version_frozen"] is True
    activated = store.activate_condition(condition["condition_id"], {"actor": "approver-1"})

    assert activated["status"] == "monitor"
    assert activated["activation_state"] == "active"
    assert activated["activation_timestamp"]
    assert backend.get_record("custom_conditions", condition["condition_id"])["activation_state"] == "active"
    assert backend.list_records("condition_audit_history")


def test_custom_condition_disallows_unsafe_code_types(tmp_path) -> None:
    backend = SqliteStorageBackend(path=tmp_path / "sprico.sqlite3")
    store = SpriCOConditionStore(backend=backend)

    with pytest.raises(ConditionLifecycleError):
        store.create_condition(
            {
                "condition_id": "cond_unsafe",
                "name": "Unsafe custom code",
                "condition_type": "python_code",
                "parameters": {"code": "open('secret').read()"},
            }
        )


def test_custom_condition_emits_sensitive_signals_not_verdicts(tmp_path) -> None:
    backend = SqliteStorageBackend(path=tmp_path / "sprico.sqlite3")
    store = SpriCOConditionStore(backend=backend)
    condition = store.create_condition(
        {
            "condition_id": "cond_regex",
            "name": "MRN detector",
            "condition_type": "regex_match",
            "parameters": {"pattern": r"MRN[- ]?\d{3,}"},
            "author": "policy-author",
        }
    )

    result = store.simulate_condition(condition["condition_id"], {"text": "MRN-12345"})

    assert result["matched"] is True
    assert result["signals"][0]["signal_id"].startswith("custom_condition:")
    assert "verdict" not in result
    assert result["final_verdict_authority"] == "sprico_policy_decision_engine"

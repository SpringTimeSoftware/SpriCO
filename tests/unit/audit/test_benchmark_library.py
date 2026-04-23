from pathlib import Path

from audit.benchmark_importer import parse_flipattack_artifact
from audit.database import AuditDatabase


def test_benchmark_source_scenario_media_and_replay_are_persisted(tmp_path: Path) -> None:
    db = AuditDatabase(tmp_path / "audit.db")
    db.initialize()

    source = db.create_benchmark_source(
        source={
            "source_name": "Public FlipAttack Reference",
            "source_type": "public_json",
            "source_uri": "https://example.test/flipattack.json",
            "benchmark_family": "FlipAttack",
            "model_name": "public-reference-model",
            "version": "v1",
            "title": "FlipAttack-style public reference pack",
            "description": "Public benchmark reference data; not client evidence.",
            "metadata": {"reference_data_notice": "Public benchmark reference data; not client evidence."},
        },
        scenarios=[
            {
                "scenario_code": "flipattack-001",
                "title": "Reference transformation case",
                "category_name": "Jailbreak",
                "subcategory_name": "Transformation",
                "objective_text": "Replay a public benchmark prompt.",
                "prompt_text": "Prompt 1: Refuse unsafe requests.",
                "expected_behavior_text": "The target should refuse unsafe instructions.",
                "modality": "text",
                "recommended_target_types": ["OpenAIChatTarget", "HTTP_TARGET"],
                "tags": ["public-reference"],
                "severity_hint": "HIGH",
                "replay_supported": True,
            }
        ],
        media=[
            {
                "scenario_id": "flipattack-001",
                "media_type": "gif",
                "media_uri": "https://example.test/case.gif",
                "caption": "Why this matters",
                "sort_order": 1,
            }
        ],
    )

    scenarios = db.list_benchmark_scenarios(source_type="public_json")
    assert source["source_name"] == "Public FlipAttack Reference"
    assert len(scenarios) == 1
    assert scenarios[0]["recommended_target_types"] == ["OpenAIChatTarget", "HTTP_TARGET"]
    assert scenarios[0]["replay_supported"] is True

    media = db.list_benchmark_media(source_type="public_json")
    assert len(media) == 1
    assert media[0]["scenario_title"] == "Reference transformation case"

    run_id = db.create_benchmark_replay_run(
        scenario_id=scenarios[0]["id"],
        target_info={
            "target_registry_name": "OpenAIChatTarget::test",
            "target_type": "OpenAIChatTarget",
            "model_name": "test-model",
            "endpoint": "http://localhost/v1",
            "supports_multi_turn": True,
        },
        execution_profile={"mode_code": "COMPLIANCE", "run_count_requested": 1},
    )

    assert run_id is not None
    run = db.get_run_detail(run_id)
    assert run is not None
    assert run["results"][0]["result_label"] == "Benchmark Scenario"
    assert run["results"][0]["original_result_guidance_snapshot"].startswith("Public benchmark reference scenario")
    assert run["results"][0]["stability_run_id"] is not None

    client_results = db.get_benchmark_client_results(scenarios[0]["id"])
    assert len(client_results) == 1

    group_detail = db.get_stability_dashboard()["groups"][0]
    assert group_detail["prompt_source_type"] == "benchmark"
    assert group_detail["benchmark_scenario_id"] == scenarios[0]["id"]


def test_flipattack_importer_accepts_common_result_shape() -> None:
    normalized = parse_flipattack_artifact(
        {
            "benchmark_family": "FlipAttack",
            "model": "public-model",
            "results": [
                {
                    "id": "flip-001",
                    "attack_name": "Flip case",
                    "category": "Jailbreak",
                    "subcategory": "Transform",
                    "attack_prompt": "Prompt 1: transformed public prompt",
                    "severity": "HIGH",
                }
            ],
            "gifs": [
                {
                    "scenario_id": "flip-001",
                    "url": "https://example.test/flip.gif",
                    "caption": "Case walkthrough",
                }
            ],
        }
    )

    assert normalized["source"]["benchmark_family"] == "FlipAttack"
    assert normalized["source"]["model_name"] == "public-model"
    assert normalized["scenarios"][0]["scenario_code"] == "flip-001"
    assert normalized["scenarios"][0]["prompt_text"] == "Prompt 1: transformed public prompt"
    assert normalized["media"][0]["media_type"] == "gif"

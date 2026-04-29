"""Unified run registry for SpriCO workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from audit.database import AuditDatabase
from pyrit.backend.sprico.evidence_store import SpriCOEvidenceStore
from pyrit.backend.sprico.findings import SpriCOFindingStore
from pyrit.backend.sprico.storage import StorageBackend, get_storage_backend


class SpriCORunRegistry:
    def __init__(
        self,
        backend: StorageBackend | None = None,
        audit_db: AuditDatabase | None = None,
        evidence_store: SpriCOEvidenceStore | None = None,
        finding_store: SpriCOFindingStore | None = None,
    ) -> None:
        self._backend = backend or get_storage_backend()
        if audit_db is not None:
            self._audit_db = audit_db
        else:
            backend_path = getattr(self._backend, "path", None)
            audit_db_path = backend_path.with_name("audit.db") if isinstance(backend_path, Path) else None
            self._audit_db = AuditDatabase(db_path=audit_db_path)
            self._audit_db.initialize()
        self._evidence_store = evidence_store or SpriCOEvidenceStore(backend=self._backend)
        self._finding_store = finding_store or SpriCOFindingStore(backend=self._backend, evidence_store=self._evidence_store)
        self._is_backfilling = False

    def backfill(self) -> None:
        if self._is_backfilling:
            return
        self._is_backfilling = True
        try:
            self._finding_store.sync_existing_records()
            evidence_events = self._backend.list_records("evidence_items")
            finding_items = self._finding_store.list_findings(limit=10_000)
            for run in self._backend.list_records("garak_runs"):
                self.record_garak_run(run)
            for run in self._backend.list_records("red_scans"):
                self.record_red_scan(run)
            for run in self._backend.list_records("promptfoo_runs"):
                self.record_promptfoo_run(run)
            for event in self._backend.list_records("shield_events"):
                self.record_shield_check(event)
            for simulation in self._backend.list_records("condition_simulations"):
                self.record_condition_simulation(simulation)
            for evidence in evidence_events:
                if str(evidence.get("evidence_type") or "").lower() == "interactive_audit_turn":
                    self.record_interactive_audit_session(
                        evidence,
                        evidence_events=evidence_events,
                        finding_items=finding_items,
                    )
            seen_run_ids: set[str] = set()
            for run in self._audit_db.get_recent_runs(limit=500):
                run_id = str(run.get("job_id") or run.get("id") or "")
                if not run_id or run_id in seen_run_ids:
                    continue
                seen_run_ids.add(run_id)
                detail = self._audit_db.get_run_detail(run_id) or run
                self.record_audit_run(
                    detail,
                    evidence_events=evidence_events,
                    finding_items=finding_items,
                )
            for run in self._audit_db.get_recent_interactive_runs(limit=500):
                run_id = str(run.get("job_id") or run.get("id") or "")
                if not run_id or run_id in seen_run_ids:
                    continue
                seen_run_ids.add(run_id)
                detail = self._audit_db.get_run_detail(run_id) or run
                self.record_audit_run(
                    detail,
                    evidence_events=evidence_events,
                    finding_items=finding_items,
                )
            self._backfill_evidence_links(evidence_events=evidence_events)
        finally:
            self._is_backfilling = False

    def list_runs(
        self,
        *,
        limit: int = 250,
        run_type: str | None = None,
        target_id: str | None = None,
        source_page: str | None = None,
        status: str | None = None,
        final_verdict: str | None = None,
    ) -> list[dict[str, Any]]:
        self.backfill()
        runs = [normalize_run_record(record) for record in self._backend.list_records("runs")]
        if run_type:
            runs = [item for item in runs if str(item.get("run_type") or "").lower() == run_type.lower()]
        if target_id:
            runs = [item for item in runs if str(item.get("target_id") or "") == target_id]
        if source_page:
            runs = [item for item in runs if str(item.get("source_page") or "").lower() == source_page.lower()]
        if status:
            runs = [item for item in runs if str(item.get("status") or "").lower() == status.lower()]
        if final_verdict:
            runs = [item for item in runs if str(item.get("final_verdict") or "").upper() == final_verdict.upper()]
        runs.sort(key=lambda item: str(item.get("finished_at") or item.get("started_at") or item.get("updated_at") or ""), reverse=True)
        return runs[:limit]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        self.backfill()
        return self._lookup_run(run_id)

    def _lookup_run(self, run_id: str) -> dict[str, Any] | None:
        direct = self._backend.get_record("runs", run_id)
        if direct is not None:
            return normalize_run_record(direct)
        for run in self._backend.list_records("runs"):
            normalized = normalize_run_record(run)
            if run_id in _run_identifiers(normalized):
                return normalized
        return None

    def summary(self) -> dict[str, Any]:
        runs = self.list_runs(limit=5_000)
        return {
            "generated_at": _utc_now(),
            "total_runs": len(runs),
            "by_run_type": _counter_rows(runs, key="run_type"),
            "by_source_page": _counter_rows(runs, key="source_page"),
            "by_status": _counter_rows(runs, key="status"),
            "by_final_verdict": _counter_rows(runs, key="final_verdict"),
            "coverage": {
                "no_finding_runs": sum(1 for item in runs if _is_no_finding_run(item)),
                "runs_with_findings": sum(1 for item in runs if int(item.get("findings_count") or 0) > 0),
                "not_evaluated_runs": sum(1 for item in runs if str(item.get("evaluation_status") or "").lower() == "not_evaluated"),
                "evidence_total": sum(int(item.get("evidence_count") or 0) for item in runs),
                "findings_total": sum(int(item.get("findings_count") or 0) for item in runs),
                "artifact_total": sum(int(item.get("artifact_count") or 0) for item in runs),
                "targets_covered": len({str(item.get("target_id") or "") for item in runs if str(item.get("target_id") or "").strip()}),
            },
            "recent_runs": runs[:10],
        }

    def evidence_for_run(self, run_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
        run = self.get_run(run_id)
        if run is None:
            return []
        matches = []
        for event in self._evidence_store.list_events(limit=10_000):
            if _event_matches_run(event, run):
                matches.append(self.enrich_evidence_event(event))
        matches.sort(key=lambda item: str(item.get("created_at") or item.get("timestamp") or ""), reverse=True)
        return matches[:limit]

    def findings_for_run(self, run_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
        run = self.get_run(run_id)
        if run is None:
            return []
        matches = []
        for item in self._finding_store.list_findings(limit=10_000):
            if _finding_matches_run(item, run):
                matches.append(self.enrich_finding_record(item))
        matches.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
        return matches[:limit]

    def record_garak_run(self, run: dict[str, Any]) -> dict[str, Any]:
        scan_id = str(run.get("scan_id") or run.get("id") or "")
        run_id = f"garak_scan:{scan_id}"
        config = _as_dict(run.get("config"))
        aggregate = _as_dict(run.get("aggregate"))
        final_verdict = _as_dict(run.get("sprico_final_verdict"))
        record = {
            "id": run_id,
            "run_id": run_id,
            "run_type": "garak_scan",
            "source_page": "garak-scanner",
            "target_id": run.get("target_id"),
            "target_name": run.get("target_name") or config.get("target_name") or run.get("target_id"),
            "target_type": run.get("target_type") or config.get("target_type"),
            "domain": config.get("policy_context", {}).get("policy_domain") if isinstance(config.get("policy_context"), dict) else None,
            "policy_id": run.get("policy_id") or config.get("policy_id"),
            "policy_name": self._policy_name(run.get("policy_id") or config.get("policy_id")),
            "engine_id": "garak",
            "engine_name": "garak LLM Scanner",
            "engine_version": _as_dict(run.get("garak")).get("version"),
            "status": run.get("status"),
            "evaluation_status": run.get("evaluation_status"),
            "started_at": run.get("started_at"),
            "finished_at": run.get("finished_at"),
            "duration_seconds": _duration_seconds(run.get("started_at"), run.get("finished_at")),
            "evidence_count": int(run.get("evidence_count") or 0),
            "findings_count": int(run.get("findings_count") or 0),
            "final_verdict": run.get("final_verdict") or final_verdict.get("verdict"),
            "violation_risk": run.get("risk") or final_verdict.get("violation_risk") or aggregate.get("worst_risk"),
            "coverage_summary": {
                "scan_profile": run.get("scan_profile"),
                "vulnerability_categories": config.get("vulnerability_categories") or run.get("vulnerability_categories") or [],
                "no_findings": str(run.get("status") or "").lower() == "completed_no_findings",
                "evaluation_status": run.get("evaluation_status"),
            },
            "artifact_count": len(run.get("artifacts") or []),
            "created_by": config.get("created_by"),
            "metadata": {
                "scan_profile": run.get("scan_profile"),
                "garak": run.get("garak") or {},
                "profile_resolution": config.get("profile_resolution") or run.get("profile_resolution"),
            },
            "legacy_source_ref": {"collection": "garak_runs", "id": scan_id, "scan_id": scan_id},
        }
        return self._upsert_run(record)

    def record_red_scan(self, scan: dict[str, Any]) -> dict[str, Any]:
        scan_id = str(scan.get("id") or scan.get("scan_id") or "")
        findings = list(scan.get("findings") or [])
        results = list(scan.get("results") or [])
        risk_summary = _as_dict(scan.get("risk"))
        record = {
            "id": f"red_campaign:{scan_id}",
            "run_id": f"red_campaign:{scan_id}",
            "run_type": "red_campaign",
            "source_page": "red",
            "target_id": scan.get("target_id"),
            "target_name": _first_non_empty(*(item.get("target_name") for item in results), scan.get("target_id")),
            "target_type": _first_non_empty(*(item.get("target_type") for item in results)),
            "domain": _as_dict(scan.get("recon_context")).get("domain") or "generic",
            "policy_id": scan.get("policy_id"),
            "policy_name": self._policy_name(scan.get("policy_id")),
            "engine_id": str(scan.get("engine") or "sprico_red_team_campaigns"),
            "engine_name": "SpriCO Red Team Campaigns",
            "engine_version": "v1",
            "status": scan.get("status"),
            "evaluation_status": "evaluated",
            "started_at": scan.get("created_at"),
            "finished_at": scan.get("updated_at"),
            "duration_seconds": _duration_seconds(scan.get("created_at"), scan.get("updated_at")),
            "evidence_count": len(results),
            "findings_count": len(findings),
            "final_verdict": _run_verdict_from_results(results, findings),
            "violation_risk": risk_summary.get("severity") or _worst_risk(*(item.get("violation_risk") for item in findings), *(item.get("violation_risk") for item in results)),
            "coverage_summary": {
                "objective_count": len(scan.get("objective_ids") or []),
                "turn_count": len(results),
                "converters": list(scan.get("converters") or []),
                "scorers": list(scan.get("scorers") or []),
            },
            "artifact_count": 0,
            "created_by": None,
            "metadata": {"risk": risk_summary, "recon_context": scan.get("recon_context") or {}},
            "legacy_source_ref": {"collection": "red_scans", "id": scan_id, "scan_id": scan_id},
        }
        return self._upsert_run(record)

    def record_promptfoo_run(self, run: dict[str, Any]) -> dict[str, Any]:
        scan_id = str(run.get("scan_id") or run.get("id") or "")
        evidence_ids = list(run.get("evidence_ids") or [])
        finding_ids = list(run.get("finding_ids") or [])
        summary = _as_dict(run.get("sprico_summary"))
        promptfoo = _as_dict(run.get("promptfoo"))
        selected_catalog = _as_dict(promptfoo.get("selected_catalog_snapshot"))
        selected_plugins = list(selected_catalog.get("plugins") or [])
        selected_strategies = list(selected_catalog.get("strategies") or [])
        custom_policies = list(run.get("custom_policies") or selected_catalog.get("custom_policies") or [])
        custom_intents = list(run.get("custom_intents") or selected_catalog.get("custom_intents") or [])
        record = {
            "id": f"promptfoo_runtime:{scan_id}",
            "run_id": f"promptfoo_runtime:{scan_id}",
            "run_type": "promptfoo_runtime",
            "source_page": "benchmark-library",
            "target_id": run.get("target_id"),
            "target_name": run.get("target_name") or run.get("target_id"),
            "target_type": run.get("target_type"),
            "domain": run.get("domain") or "generic",
            "policy_id": run.get("policy_id"),
            "policy_name": self._policy_name(run.get("policy_id")) or run.get("policy_name"),
            "engine_id": "promptfoo_import_or_assertions",
            "engine_name": "promptfoo Runtime",
            "engine_version": promptfoo.get("version"),
            "status": run.get("status"),
            "evaluation_status": run.get("evaluation_status"),
            "started_at": run.get("started_at") or run.get("created_at"),
            "finished_at": run.get("finished_at") or run.get("updated_at"),
            "duration_seconds": _duration_seconds(run.get("started_at") or run.get("created_at"), run.get("finished_at") or run.get("updated_at")),
            "evidence_count": int(run.get("evidence_count") or len(evidence_ids)),
            "findings_count": int(run.get("findings_count") or len(finding_ids)),
            "final_verdict": run.get("final_verdict"),
            "violation_risk": run.get("violation_risk"),
            "coverage_summary": {
                "plugin_group_id": run.get("plugin_group_id"),
                "plugin_group_label": run.get("plugin_group_label"),
                "plugin_ids": list(run.get("plugin_ids") or []),
                "plugin_labels": [item.get("label") for item in selected_plugins if item.get("label")],
                "strategy_ids": list(run.get("strategy_ids") or []),
                "strategy_labels": [item.get("label") for item in selected_strategies if item.get("label")],
                "custom_policy_count": len(custom_policies),
                "custom_intent_count": len(custom_intents),
                "suite_id": run.get("suite_id"),
                "suite_name": run.get("suite_name"),
                "comparison_group_id": run.get("comparison_group_id"),
                "comparison_mode": run.get("comparison_mode"),
                "comparison_label": run.get("comparison_label"),
                "catalog_hash": promptfoo.get("catalog_hash"),
                "promptfoo_version": promptfoo.get("version"),
                "rows_total": int(summary.get("rows_total") or 0),
                "pass_count": int(summary.get("pass_count") or 0),
                "warn_count": int(summary.get("warn_count") or 0),
                "fail_count": int(summary.get("fail_count") or 0),
                "no_findings": str(run.get("status") or "").lower() == "completed_no_findings",
            },
            "artifact_count": int(run.get("artifact_count") or len(run.get("artifacts") or [])),
            "created_by": run.get("created_by"),
            "metadata": {
                "scan_id": scan_id,
                "purpose": run.get("purpose"),
                "promptfoo": promptfoo,
                "promptfoo_catalog": selected_catalog,
                "custom_policies": custom_policies,
                "custom_intents": custom_intents,
                "suite_id": run.get("suite_id"),
                "suite_name": run.get("suite_name"),
                "comparison_group_id": run.get("comparison_group_id"),
                "comparison_mode": run.get("comparison_mode"),
                "comparison_label": run.get("comparison_label"),
                "promptfoo_summary": summary,
            },
            "legacy_source_ref": {"collection": "promptfoo_runs", "id": scan_id, "scan_id": scan_id},
        }
        return self._upsert_run(record)

    def record_shield_check(self, event: dict[str, Any]) -> dict[str, Any]:
        evidence_id = str(event.get("evidence_id") or event.get("finding_id") or event.get("id") or "")
        run_id = str(event.get("run_id") or f"shield_check:{evidence_id}")
        final_verdict = _as_dict(event.get("sprico_final_verdict"))
        linked_findings = list(event.get("linked_finding_ids") or [])
        record = {
            "id": run_id,
            "run_id": run_id,
            "run_type": "shield_check",
            "source_page": "shield",
            "target_id": event.get("target_id"),
            "target_name": event.get("target_name") or event.get("target_id"),
            "target_type": event.get("target_type"),
            "domain": _as_dict(event.get("policy_context")).get("target_domain") or "generic",
            "policy_id": event.get("policy_id"),
            "policy_name": self._policy_name(event.get("policy_id")),
            "engine_id": event.get("engine_id") or "sprico.shield",
            "engine_name": event.get("engine_name") or "SpriCO Shield",
            "engine_version": event.get("engine_version") or "v1",
            "status": "completed",
            "evaluation_status": "evaluated",
            "started_at": event.get("created_at") or event.get("timestamp"),
            "finished_at": event.get("created_at") or event.get("timestamp"),
            "duration_seconds": 0,
            "evidence_count": 1,
            "findings_count": len(linked_findings),
            "final_verdict": event.get("final_verdict") or final_verdict.get("verdict"),
            "violation_risk": event.get("violation_risk") or final_verdict.get("violation_risk"),
            "coverage_summary": {"matched_signals": len(event.get("matched_signals") or [])},
            "artifact_count": 0,
            "created_by": _as_dict(event.get("raw_result")).get("request_uuid"),
            "metadata": {"evidence_id": evidence_id},
            "legacy_source_ref": {"collection": "shield_events", "id": evidence_id, "evidence_id": evidence_id},
        }
        return self._upsert_run(record)

    def record_condition_simulation(self, simulation: dict[str, Any]) -> dict[str, Any]:
        simulation_id = str(simulation.get("id") or "")
        result = _as_dict(simulation.get("result"))
        signals = list(result.get("signals") or [])
        details = _as_dict(result.get("details"))
        condition_id = str(simulation.get("condition_id") or "")
        condition = self._backend.get_record("custom_conditions", condition_id) or {}
        run_id = f"custom_condition_simulation:{simulation_id}"
        record = {
            "id": run_id,
            "run_id": run_id,
            "run_type": "custom_condition_simulation",
            "source_page": "conditions",
            "target_id": None,
            "target_name": None,
            "target_type": None,
            "domain": condition.get("domain") or "generic",
            "policy_id": None,
            "policy_name": None,
            "engine_id": f"sprico.condition.{condition.get('condition_type') or 'simulation'}",
            "engine_name": "SpriCO Custom Conditions",
            "engine_version": simulation.get("version") or condition.get("version"),
            "status": "completed",
            "evaluation_status": "evaluated",
            "started_at": simulation.get("created_at"),
            "finished_at": simulation.get("created_at"),
            "duration_seconds": 0,
            "evidence_count": len(signals),
            "findings_count": 0,
            "final_verdict": "NOT_APPLICABLE",
            "violation_risk": "NOT_APPLICABLE",
            "coverage_summary": {"matched": bool(result.get("matched")), "signal_count": len(signals)},
            "artifact_count": 0,
            "created_by": None,
            "metadata": {"condition_id": condition_id, "details": details},
            "legacy_source_ref": {"collection": "condition_simulations", "id": simulation_id, "condition_id": condition_id},
        }
        return self._upsert_run(record)

    def record_interactive_audit_session(
        self,
        evidence: dict[str, Any],
        *,
        evidence_events: list[dict[str, Any]] | None = None,
        finding_items: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        conversation_id = str(evidence.get("conversation_id") or evidence.get("scan_id") or "")
        events = evidence_events if evidence_events is not None else self._backend.list_records("evidence_items")
        run_id = f"interactive_audit:{conversation_id}"
        run_evidence = [
            item
            for item in events
            if str(item.get("conversation_id") or item.get("scan_id") or "") == conversation_id
            and str(item.get("evidence_type") or "").lower() == "interactive_audit_turn"
        ]
        pass_count = sum(1 for item in run_evidence if str(item.get("final_verdict") or "").upper() == "PASS")
        warn_count = sum(1 for item in run_evidence if str(item.get("final_verdict") or "").upper() == "WARN")
        fail_count = sum(1 for item in run_evidence if str(item.get("final_verdict") or "").upper() == "FAIL")
        findings = finding_items if finding_items is not None else self._finding_store.list_findings(limit=10_000)
        linked_findings = [
            item
            for item in findings
            if str(item.get("run_id") or "") == run_id or conversation_id in _run_identifiers(item)
        ]
        first = run_evidence[0] if run_evidence else evidence
        record = {
            "id": run_id,
            "run_id": run_id,
            "run_type": "interactive_audit",
            "source_page": "chat",
            "target_id": first.get("target_id"),
            "target_name": first.get("target_name") or first.get("target_id"),
            "target_type": first.get("target_type"),
            "domain": _as_dict(first.get("policy_context")).get("target_domain") or "hospital",
            "policy_id": first.get("policy_id"),
            "policy_name": self._policy_name(first.get("policy_id")),
            "engine_id": first.get("engine_id") or "sprico_interactive_audit",
            "engine_name": first.get("engine_name") or "SpriCO Interactive Audit",
            "engine_version": first.get("engine_version"),
            "status": "completed",
            "evaluation_status": "evaluated",
            "started_at": run_evidence[-1].get("created_at") if run_evidence else first.get("created_at"),
            "finished_at": run_evidence[0].get("created_at") if run_evidence else first.get("created_at"),
            "duration_seconds": _duration_seconds(run_evidence[-1].get("created_at") if run_evidence else first.get("created_at"), run_evidence[0].get("created_at") if run_evidence else first.get("created_at")),
            "evidence_count": len(run_evidence),
            "findings_count": len(linked_findings),
            "final_verdict": _verdict_from_counts(pass_count, warn_count, fail_count),
            "violation_risk": _worst_risk(*(item.get("violation_risk") for item in run_evidence)),
            "coverage_summary": {"assistant_turns": len(run_evidence), "pass_count": pass_count, "warn_count": warn_count, "fail_count": fail_count},
            "artifact_count": 0,
            "created_by": first.get("session_id"),
            "metadata": {
                "conversation_id": conversation_id,
                "attack_result_id": first.get("session_id"),
                "supports_saved_run": True,
            },
            "legacy_source_ref": {
                "collection": "interactive_audit",
                "id": conversation_id,
                "conversation_id": conversation_id,
                "attack_result_id": first.get("session_id"),
            },
        }
        return self._upsert_run(record)

    def record_audit_run(
        self,
        run: dict[str, Any],
        *,
        evidence_events: list[dict[str, Any]] | None = None,
        finding_items: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        results = list(run.get("results") or [])
        has_interactive = any(str(item.get("prompt_source_type") or "").lower() == "interactive" for item in results)
        has_benchmark = any(
            str(item.get("prompt_source_type") or "").lower() == "benchmark"
            or item.get("benchmark_scenario_id") is not None
            for item in results
        )
        run_source = _audit_run_source(run, results=results)
        conversation_id = _first_non_empty(*(item.get("conversation_id") for item in results))
        if has_interactive:
            run_type = "interactive_audit"
            source_page = "chat"
            unified_run_id = f"interactive_audit:{conversation_id or run.get('job_id') or run.get('id')}"
        elif has_benchmark:
            run_type = "benchmark_replay"
            source_page = "benchmark-library"
            unified_run_id = f"benchmark_replay:{run.get('job_id') or run.get('id')}"
        elif run_source == "sprico_auditspec":
            run_type = "sprico_auditspec"
            source_page = "benchmark-library"
            unified_run_id = f"sprico_auditspec:{run.get('job_id') or run.get('id')}"
        else:
            run_type = "audit_workstation"
            source_page = "audit"
            unified_run_id = f"audit_workstation:{run.get('job_id') or run.get('id')}"
        events = evidence_events if evidence_events is not None else self._backend.list_records("evidence_items")
        findings = finding_items if finding_items is not None else self._finding_store.list_findings(limit=10_000)
        evidence_count = len([item for item in events if _audit_evidence_matches_run(item, run)])
        findings_count = len([item for item in findings if _audit_finding_matches_run(item, run, unified_run_id)])
        policy_id = _audit_policy_id(results, run=run)
        policy_name = _first_non_empty(
            run.get("policy_name"),
            *(item.get("policy_name") for item in results),
            self._policy_name(policy_id),
        )
        final_verdict = _verdict_from_counts(run.get("pass_count"), run.get("warn_count"), run.get("fail_count"))
        completed_status = str(run.get("status") or "").lower() == "completed"
        record = {
            "id": unified_run_id,
            "run_id": unified_run_id,
            "run_type": run_type,
            "source_page": source_page,
            "target_id": run.get("target_registry_name") or run.get("target_id"),
            "target_name": run.get("model_name") or run.get("target_registry_name") or run.get("target_id"),
            "target_type": run.get("target_type"),
            "domain": _audit_domain(results),
            "policy_id": policy_id,
            "policy_name": policy_name,
            "engine_id": (
                "sprico_interactive_audit" if has_interactive
                else "sprico.auditspec" if run_type == "sprico_auditspec"
                else "pyrit.audit"
            ),
            "engine_name": (
                "SpriCO Interactive Audit" if has_interactive
                else "SpriCO AuditSpec" if run_type == "sprico_auditspec"
                else "Audit Workstation"
            ),
            "engine_version": _first_non_empty(*(item.get("scoring_version") for item in results)),
            "status": run.get("status"),
            "evaluation_status": "evaluated" if completed_status else "not_evaluated",
            "started_at": run.get("started_at") or run.get("created_at"),
            "finished_at": run.get("completed_at") or run.get("updated_at"),
            "duration_seconds": _duration_seconds(run.get("started_at") or run.get("created_at"), run.get("completed_at") or run.get("updated_at")),
            "evidence_count": evidence_count,
            "findings_count": findings_count,
            "final_verdict": final_verdict,
            "violation_risk": _worst_risk(*(item.get("risk_level") for item in results)),
            "coverage_summary": {
                "total_tests": int(run.get("total_tests") or 0),
                "completed_tests": int(run.get("completed_tests") or 0),
                "pass_count": int(run.get("pass_count") or 0),
                "warn_count": int(run.get("warn_count") or 0),
                "fail_count": int(run.get("fail_count") or 0),
                "no_findings": completed_status and findings_count == 0 and final_verdict == "PASS",
                "run_source": run_source,
                "suite_id": run.get("suite_id"),
                "suite_name": run.get("suite_name"),
                "comparison_group_id": run.get("comparison_group_id"),
                "comparison_label": run.get("comparison_label"),
                "comparison_mode": run.get("comparison_mode"),
            },
            "artifact_count": 0,
            "created_by": None,
            "metadata": {
                "audit_run_id": run.get("job_id") or run.get("id"),
                "conversation_id": conversation_id,
                "selected_categories": run.get("selected_categories") or [],
                "selected_test_ids": run.get("selected_test_ids") or [],
                "selected_variant_ids": run.get("selected_variant_ids") or [],
                "run_source": run_source,
                "suite_id": run.get("suite_id"),
                "suite_name": run.get("suite_name"),
                "comparison_group_id": run.get("comparison_group_id"),
                "comparison_label": run.get("comparison_label"),
                "comparison_mode": run.get("comparison_mode"),
                "run_metadata": _as_dict(run.get("run_metadata")),
            },
            "legacy_source_ref": {
                "collection": "audit_runs",
                "id": run.get("job_id") or run.get("id"),
                "run_id": run.get("job_id") or run.get("id"),
                "conversation_id": conversation_id,
            },
        }
        return self._upsert_run(record)

    def _policy_name(self, policy_id: Any) -> str | None:
        policy_key = str(policy_id or "").strip()
        if not policy_key:
            return None
        policy = self._backend.get_record("policies", policy_key)
        return str(policy.get("name")) if isinstance(policy, dict) and policy.get("name") else None

    def _upsert_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_run_record(payload)
        self._backend.upsert_record("runs", normalized["run_id"], normalized)
        return normalized

    def enrich_evidence_event(self, event: dict[str, Any]) -> dict[str, Any]:
        promptfoo_like = _is_promptfoo_evidence_event(event)
        needs_run = not event.get("run_id") or not event.get("run_type") or not event.get("source_page") or not event.get("policy_name")
        needs_promptfoo = promptfoo_like and _promptfoo_event_needs_detail(event)
        if not needs_run and not needs_promptfoo:
            return event
        run = self._infer_run_for_event(event)
        if run is None:
            return event
        enriched = dict(event)
        if needs_run:
            enriched.setdefault("run_id", run["run_id"])
            enriched.setdefault("run_type", run["run_type"])
            enriched.setdefault("source_page", run["source_page"])
            enriched.setdefault("policy_name", run.get("policy_name"))
        if needs_promptfoo:
            enriched = _enrich_promptfoo_evidence_event(enriched, run)
        return enriched

    def enrich_finding_record(self, finding: dict[str, Any]) -> dict[str, Any]:
        needs_run = not finding.get("run_id") or not finding.get("run_type")
        needs_target = not finding.get("target_id")
        needs_source = not finding.get("source_page") or str(finding.get("source_page") or "").lower() == "findings"
        needs_policy = not finding.get("policy_name")
        needs_engine = str(finding.get("engine_id") or "").lower() in {"", "sprico"}
        if not any((needs_run, needs_target, needs_source, needs_policy, needs_engine)):
            return finding
        run = self._infer_run_for_finding(finding)
        if run is None:
            return finding
        enriched = dict(finding)
        if needs_run:
            enriched["run_id"] = run["run_id"]
            enriched["run_type"] = run["run_type"]
        if needs_target:
            enriched["target_id"] = run.get("target_id")
            enriched["target_name"] = run.get("target_name")
            enriched["target_type"] = run.get("target_type")
        if needs_source:
            enriched["source_page"] = run["source_page"]
        if needs_policy:
            enriched["policy_name"] = run.get("policy_name")
        if needs_engine:
            enriched["engine_id"] = run.get("engine_id") or enriched.get("engine_id")
            enriched["engine_name"] = run.get("engine_name") or enriched.get("engine_name")
        if str(enriched.get("domain") or "").lower() == "generic" and run.get("domain"):
            enriched["domain"] = run.get("domain")
        return enriched

    def _backfill_evidence_links(self, *, evidence_events: list[dict[str, Any]] | None = None) -> None:
        events = evidence_events if evidence_events is not None else self._backend.list_records("evidence_items")
        for event in events:
            evidence_id = str(event.get("evidence_id") or event.get("finding_id") or event.get("id") or "")
            if not evidence_id:
                continue
            enriched = self.enrich_evidence_event(event)
            updates: dict[str, Any] = {}
            for key in (
                "run_id",
                "run_type",
                "source_page",
                "policy_name",
                "engine_version",
                "source_metadata",
                "promptfoo_version",
                "promptfoo_catalog_hash",
                "promptfoo_catalog_snapshot",
                "promptfoo_plugin_id",
                "promptfoo_plugin_label",
                "promptfoo_strategy_id",
                "promptfoo_strategy_label",
            ):
                if key not in enriched:
                    continue
                before = event.get(key)
                after = enriched.get(key)
                if before == after:
                    continue
                if after is None:
                    continue
                if isinstance(after, dict) and not after:
                    continue
                updates[key] = after
            if not updates:
                continue
            self._evidence_store.update_event(evidence_id, updates)

    def _infer_run_for_event(self, event: dict[str, Any]) -> dict[str, Any] | None:
        run_id = str(event.get("run_id") or "").strip()
        if run_id:
            return self._lookup_run(run_id)
        engine = str(event.get("engine_id") or event.get("engine") or "").lower()
        evidence_type = str(event.get("evidence_type") or "").lower()
        if "garak" in engine and event.get("scan_id"):
            return self._lookup_run(f"garak_scan:{event['scan_id']}")
        if "promptfoo" in engine and event.get("scan_id"):
            return self._lookup_run(f"promptfoo_runtime:{event['scan_id']}")
        if "red" in engine and event.get("scan_id"):
            return self._lookup_run(f"red_campaign:{event['scan_id']}")
        if "shield" in engine:
            evidence_id = str(event.get("evidence_id") or event.get("finding_id") or event.get("id") or "")
            return self._lookup_run(f"shield_check:{evidence_id}")
        if evidence_type == "interactive_audit_turn":
            conversation_id = str(event.get("conversation_id") or event.get("scan_id") or "")
            return self._lookup_run(f"interactive_audit:{conversation_id}")
        return None

    def _infer_run_for_finding(self, finding: dict[str, Any]) -> dict[str, Any] | None:
        run_id = str(finding.get("run_id") or "").strip()
        if run_id:
            return self._lookup_run(run_id)
        candidates = [
            _run_candidate_from_identifier("promptfoo_runtime", finding.get("scan_id")),
            _run_candidate_from_identifier("garak_scan", finding.get("scan_id")),
            _run_candidate_from_identifier("red_campaign", finding.get("scan_id")),
            _run_candidate_from_identifier("interactive_audit", finding.get("conversation_id")),
        ]
        legacy = _as_dict(finding.get("legacy_source_ref"))
        candidates.extend(
            [
                _run_candidate_from_identifier("promptfoo_runtime", legacy.get("scan_id")),
                _run_candidate_from_identifier("garak_scan", legacy.get("scan_id")),
                _run_candidate_from_identifier("red_campaign", legacy.get("scan_id")),
                _run_candidate_from_identifier("interactive_audit", legacy.get("conversation_id")),
                str(legacy.get("run_id") or "").strip() or None,
            ]
        )
        for candidate in candidates:
            if not candidate:
                continue
            run = self._lookup_run(candidate)
            if run is not None:
                return run
        for evidence_id in finding.get("evidence_ids") or []:
            event = self._evidence_store.get_event(str(evidence_id))
            if event is None:
                continue
            run = self._infer_run_for_event(event)
            if run is not None:
                return run
        return None


def _is_promptfoo_evidence_event(event: dict[str, Any]) -> bool:
    engine = str(event.get("engine_id") or event.get("engine") or "").lower()
    evidence_type = str(event.get("evidence_type") or "").lower()
    run_type = str(event.get("run_type") or "").lower()
    run_id = str(event.get("run_id") or "").lower()
    return "promptfoo" in engine or "promptfoo" in evidence_type or run_type == "promptfoo_runtime" or run_id.startswith("promptfoo_runtime:")


def _promptfoo_event_needs_detail(event: dict[str, Any]) -> bool:
    return any(
        not event.get(key)
        for key in (
            "source_metadata",
            "promptfoo_version",
            "promptfoo_catalog_hash",
            "promptfoo_catalog_snapshot",
            "promptfoo_plugin_id",
            "promptfoo_plugin_label",
            "promptfoo_strategy_id",
            "promptfoo_strategy_label",
        )
    )


def _enrich_promptfoo_evidence_event(event: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(event)
    metadata = _as_dict(run.get("metadata"))
    promptfoo = _as_dict(metadata.get("promptfoo"))
    catalog_snapshot = _as_dict(metadata.get("promptfoo_catalog"))
    sprico_final = _as_dict(enriched.get("sprico_final_verdict"))
    raw_metadata = _as_dict(_as_dict(enriched.get("raw_result")).get("metadata"))
    coverage = _as_dict(run.get("coverage_summary"))

    selected_plugins = [item for item in catalog_snapshot.get("plugins") or [] if isinstance(item, dict)]
    selected_strategies = [item for item in catalog_snapshot.get("strategies") or [] if isinstance(item, dict)]
    plugin_map = {str(item.get("id") or "").strip(): item for item in selected_plugins if str(item.get("id") or "").strip()}
    strategy_map = {str(item.get("id") or "").strip(): item for item in selected_strategies if str(item.get("id") or "").strip()}

    promptfoo_version = (
        enriched.get("promptfoo_version")
        or enriched.get("engine_version")
        or promptfoo.get("version")
        or coverage.get("promptfoo_version")
    )
    catalog_hash = (
        enriched.get("promptfoo_catalog_hash")
        or sprico_final.get("promptfoo_catalog_hash")
        or promptfoo.get("catalog_hash")
        or coverage.get("catalog_hash")
    )
    plugin_id = (
        enriched.get("promptfoo_plugin_id")
        or sprico_final.get("promptfoo_plugin_id")
        or raw_metadata.get("pluginId")
        or _first_selected_id(selected_plugins)
    )
    strategy_id = (
        enriched.get("promptfoo_strategy_id")
        or sprico_final.get("promptfoo_strategy_id")
        or raw_metadata.get("strategyId")
        or _first_selected_id(selected_strategies)
    )
    plugin_label = (
        enriched.get("promptfoo_plugin_label")
        or sprico_final.get("promptfoo_plugin_label")
        or _catalog_item_label(plugin_map.get(str(plugin_id or "").strip()))
        or _first_string(coverage.get("plugin_labels"))
        or plugin_id
    )
    strategy_label = (
        enriched.get("promptfoo_strategy_label")
        or sprico_final.get("promptfoo_strategy_label")
        or _catalog_item_label(strategy_map.get(str(strategy_id or "").strip()))
        or _first_string(coverage.get("strategy_labels"))
        or strategy_id
    )

    source_metadata = _as_dict(enriched.get("source_metadata"))
    if promptfoo_version:
        source_metadata.setdefault("promptfoo_version", promptfoo_version)
    if catalog_hash:
        source_metadata.setdefault("promptfoo_catalog_hash", catalog_hash)
    if plugin_id:
        source_metadata.setdefault("promptfoo_plugin_id", plugin_id)
    if plugin_label:
        source_metadata.setdefault("promptfoo_plugin_label", plugin_label)
    if strategy_id:
        source_metadata.setdefault("promptfoo_strategy_id", strategy_id)
    if strategy_label:
        source_metadata.setdefault("promptfoo_strategy_label", strategy_label)

    if promptfoo_version:
        enriched.setdefault("engine_version", promptfoo_version)
        enriched["promptfoo_version"] = promptfoo_version
    if catalog_hash:
        enriched["promptfoo_catalog_hash"] = catalog_hash
    if catalog_snapshot:
        enriched.setdefault("promptfoo_catalog_snapshot", catalog_snapshot)
    if plugin_id:
        enriched["promptfoo_plugin_id"] = plugin_id
    if plugin_label:
        enriched["promptfoo_plugin_label"] = plugin_label
    if strategy_id:
        enriched["promptfoo_strategy_id"] = strategy_id
    if strategy_label:
        enriched["promptfoo_strategy_label"] = strategy_label
    if source_metadata:
        enriched["source_metadata"] = source_metadata
    return enriched


def normalize_run_record(record: dict[str, Any] | None) -> dict[str, Any]:
    now = _utc_now()
    payload = dict(record or {})
    run_id = str(payload.get("run_id") or payload.get("id") or f"run_{now}")
    started_at = payload.get("started_at") or payload.get("created_at")
    finished_at = payload.get("finished_at") or payload.get("updated_at")
    normalized = {
        "id": run_id,
        "run_id": run_id,
        "run_type": payload.get("run_type"),
        "source_page": payload.get("source_page"),
        "target_id": payload.get("target_id"),
        "target_name": payload.get("target_name"),
        "target_type": payload.get("target_type"),
        "domain": payload.get("domain"),
        "policy_id": payload.get("policy_id"),
        "policy_name": payload.get("policy_name"),
        "engine_id": payload.get("engine_id"),
        "engine_name": payload.get("engine_name"),
        "engine_version": payload.get("engine_version"),
        "status": payload.get("status"),
        "evaluation_status": payload.get("evaluation_status"),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": payload.get("duration_seconds") if payload.get("duration_seconds") is not None else _duration_seconds(started_at, finished_at),
        "evidence_count": int(payload.get("evidence_count") or 0),
        "findings_count": int(payload.get("findings_count") or 0),
        "final_verdict": payload.get("final_verdict"),
        "violation_risk": payload.get("violation_risk"),
        "coverage_summary": _as_dict(payload.get("coverage_summary")),
        "artifact_count": int(payload.get("artifact_count") or 0),
        "created_by": payload.get("created_by"),
        "metadata": _as_dict(payload.get("metadata")),
        "legacy_source_ref": _as_dict(payload.get("legacy_source_ref")),
        "created_at": str(payload.get("created_at") or started_at or now),
        "updated_at": str(payload.get("updated_at") or finished_at or now),
    }
    return normalized


def _first_selected_id(items: list[dict[str, Any]]) -> str | None:
    for item in items:
        item_id = str(item.get("id") or "").strip()
        if item_id:
            return item_id
    return None


def _catalog_item_label(item: dict[str, Any] | None) -> str | None:
    if not isinstance(item, dict):
        return None
    label = str(item.get("label") or "").strip()
    return label or None


def _first_string(value: Any) -> str | None:
    if not isinstance(value, list):
        return None
    for item in value:
        text = str(item or "").strip()
        if text:
            return text
    return None


def _counter_rows(items: list[dict[str, Any]], *, key: str) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in items:
        label = str(item.get(key) or "unknown")
        counts[label] = counts.get(label, 0) + 1
    return [{"label": label, "count": counts[label]} for label in sorted(counts)]


def _audit_domain(results: list[dict[str, Any]]) -> str | None:
    for result in results:
        domain = str(result.get("policy_domain") or result.get("domain") or result.get("industry_type") or "").strip()
        if domain:
            return domain
    return None


def _audit_policy_id(results: list[dict[str, Any]], *, run: dict[str, Any] | None = None) -> str | None:
    if run is not None:
        direct = str(run.get("policy_id") or "").strip()
        if direct:
            return direct
    for result in results:
        direct = str(result.get("policy_id") or "").strip()
        if direct:
            return direct
        context = _as_dict(result.get("grounding_assessment")).get("policy_context")
        if isinstance(context, dict):
            policy_id = str(context.get("policy_id") or "").strip()
            if policy_id:
                return policy_id
    return None


def _audit_evidence_matches_run(event: dict[str, Any], run: dict[str, Any]) -> bool:
    audit_run_id = str(run.get("job_id") or run.get("id") or "")
    run_refs = {
        f"audit_workstation:{audit_run_id}",
        f"benchmark_replay:{audit_run_id}",
        f"sprico_auditspec:{audit_run_id}",
    }
    if str(event.get("run_id") or "") in run_refs:
        return True
    conversation_ids = {
        str(item.get("conversation_id") or "")
        for item in (run.get("results") or [])
        if str(item.get("conversation_id") or "").strip()
    }
    return bool(str(event.get("conversation_id") or "") in conversation_ids)


def _audit_finding_matches_run(item: dict[str, Any], run: dict[str, Any], unified_run_id: str) -> bool:
    if str(item.get("run_id") or "") == unified_run_id:
        return True
    legacy = _as_dict(item.get("legacy_source_ref"))
    audit_run_id = str(run.get("job_id") or run.get("id") or "")
    return str(legacy.get("run_id") or legacy.get("id") or "") == audit_run_id


def _event_matches_run(event: dict[str, Any], run: dict[str, Any]) -> bool:
    if str(event.get("run_id") or "") == str(run.get("run_id") or ""):
        return True
    legacy = _as_dict(run.get("legacy_source_ref"))
    values = {
        str(event.get("scan_id") or ""),
        str(event.get("conversation_id") or ""),
        str(event.get("session_id") or ""),
        str(event.get("evidence_id") or event.get("finding_id") or event.get("id") or ""),
    }
    for key in ("scan_id", "conversation_id", "attack_result_id", "evidence_id", "id"):
        ref = str(legacy.get(key) or "").strip()
        if ref and ref in values:
            return True
    return False


def _finding_matches_run(item: dict[str, Any], run: dict[str, Any]) -> bool:
    if str(item.get("run_id") or "") == str(run.get("run_id") or ""):
        return True
    legacy = _as_dict(item.get("legacy_source_ref"))
    for key, value in _as_dict(run.get("legacy_source_ref")).items():
        ref = str(value or "").strip()
        if ref and ref in {str(legacy.get(key) or "").strip(), str(item.get("run_id") or "").strip()}:
            return True
    return False


def _run_identifiers(run: dict[str, Any]) -> set[str]:
    identifiers = {str(run.get("run_id") or "").strip()}
    legacy = _as_dict(run.get("legacy_source_ref"))
    for value in legacy.values():
        text = str(value or "").strip()
        if text:
            identifiers.add(text)
    return {item for item in identifiers if item}


def _audit_run_source(run: dict[str, Any], *, results: list[dict[str, Any]] | None = None) -> str:
    direct = str(run.get("run_source") or "").strip().lower()
    if direct:
        return direct
    for result in results or run.get("results") or []:
        source = str(result.get("run_source") or "").strip().lower()
        if source:
            return source
    return "audit_workstation"


def _is_no_finding_run(run: dict[str, Any]) -> bool:
    if int(run.get("findings_count") or 0) > 0:
        return False
    if str(run.get("status") or "").lower() == "completed_no_findings":
        return True
    return bool(_as_dict(run.get("coverage_summary")).get("no_findings"))


def _run_verdict_from_results(results: list[dict[str, Any]], findings: list[dict[str, Any]]) -> str:
    if any(str(item.get("verdict") or item.get("final_verdict") or "").upper() == "FAIL" for item in findings + results):
        return "FAIL"
    if any(str(item.get("verdict") or item.get("final_verdict") or "").upper() in {"WARN", "NEEDS_REVIEW"} for item in findings + results):
        return "WARN"
    return "PASS"


def _verdict_from_counts(pass_count: Any, warn_count: Any, fail_count: Any) -> str:
    if int(fail_count or 0) > 0:
        return "FAIL"
    if int(warn_count or 0) > 0:
        return "WARN"
    if int(pass_count or 0) > 0:
        return "PASS"
    return "NOT_EVALUATED"


def _worst_risk(*values: Any) -> str | None:
    rank = {"NOT_AVAILABLE": -1, "LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    best_label: str | None = None
    best_rank = -2
    for value in values:
        text = str(value or "").upper()
        if text in rank and rank[text] > best_rank:
            best_rank = rank[text]
            best_label = text
    return best_label


def _duration_seconds(started_at: Any, finished_at: Any) -> int | None:
    start = _parse_datetime(started_at)
    finish = _parse_datetime(finished_at)
    if start is None or finish is None:
        return None
    return max(0, int((finish - start).total_seconds()))


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        text = str(value or "").strip()
        if text:
            return value
    return None


def _run_candidate_from_identifier(prefix: str, value: Any) -> str | None:
    text = str(value or "").strip()
    return f"{prefix}:{text}" if text else None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

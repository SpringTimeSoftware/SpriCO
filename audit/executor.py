# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""Audit execution engine that runs SQLite-backed tests against PyRIT targets."""

from __future__ import annotations

from typing import Any

from audit.auditspec import evaluate_auditspec_assertions, merge_auditspec_evaluation, summarize_assertion_results
from audit.database import AuditDatabase
from audit.scorer import evaluate_response
from pyrit.backend.models.attacks import AddMessageRequest, CreateAttackRequest, MessagePieceRequest
from pyrit.backend.sprico.conditions import SpriCOConditionStore
from pyrit.backend.sprico.policy_store import SpriCOPolicyStore
from pyrit.backend.services.attack_service import get_attack_service
from pyrit.backend.services.target_service import get_target_service


class InvalidTestInputError(ValueError):
    """Raised when a workbook/variant/transient prompt cannot be executed as written."""


class AuditExecutor:
    """Execute structured audit runs stored in SQLite."""

    def __init__(self, repository: AuditDatabase | None = None) -> None:
        self._repository = repository or AuditDatabase()
        self._repository.initialize()
        self._attack_service = get_attack_service()
        self._policy_store = SpriCOPolicyStore()
        self._condition_store = SpriCOConditionStore()

    async def execute_run(self, run_id: str) -> None:
        """Execute all pending tests for a run."""
        run = self._repository.get_run(run_id)
        if run is None:
            raise ValueError(f"Audit run '{run_id}' not found")

        self._repository.mark_run_running(run_id)
        results = self._repository.get_run_results(run_id)

        try:
            for result in results:
                self._repository.mark_result_running(result["id"])
                try:
                    execution = await self._execute_single_test(run=run, result=result)
                    self._repository.complete_result(
                        run_id=run_id,
                        result_id=result["id"],
                        evaluation=execution["evaluation"],
                        prompt_sent=execution["prompt_sent"],
                        response_text=execution["response_text"],
                        interaction_log=execution["interaction_log"],
                        attack_result_id=execution["attack_result_id"],
                        conversation_id=execution["conversation_id"],
                    )
                except InvalidTestInputError as exc:
                    self._repository.invalidate_result(run_id=run_id, result_id=result["id"], reason=str(exc))
                except Exception as exc:
                    self._repository.fail_result(run_id=run_id, result_id=result["id"], reason=str(exc))

            self._repository.finalize_run(run_id)
        except Exception as exc:
            self._repository.fail_run(run_id, str(exc))
            raise

    async def _execute_single_test(self, *, run: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        self._apply_execution_parameters(
            target_registry_name=run["target_registry_name"],
            parameters=self._repository.get_result_execution_parameters(result["id"]),
        )
        labels = {
            "source": "audit",
            "operation": "audit",
            "audit_run_id": run["id"],
            "audit_test_id": str(result["test_id"]),
            "audit_category": result["category_name"],
            "audit_domain": result["domain"] or "unspecified",
            "audit_result_label": result["result_label"],
        }
        attack = await self._attack_service.create_attack_async(
            request=CreateAttackRequest(
                name=f"{result['category_name']}::{result['attack_type']}",
                target_registry_name=run["target_registry_name"],
                labels=labels,
            )
        )

        prompt_steps = self._materialize_prompt_steps(
            prompt_steps=result["actual_prompt_steps"],
            supporting_documents=result.get("supporting_documents") or {},
            supports_multi_turn=run.get("supports_multi_turn", True),
        )

        interaction_log: list[dict[str, Any]] = []
        conversation_history: list[dict[str, Any]] = []
        response_text = ""
        for index, prompt in enumerate(prompt_steps, start=1):
            conversation_history.append(
                {
                    "turn_id": f"user-{index}",
                    "role": "user",
                    "user_prompt": prompt,
                    "content": prompt,
                }
            )
            response = await self._attack_service.add_message_async(
                attack_result_id=attack.attack_result_id,
                request=AddMessageRequest(
                    role="user",
                    pieces=[MessagePieceRequest(data_type="text", original_value=prompt)],
                    send=True,
                    target_registry_name=run["target_registry_name"],
                    target_conversation_id=attack.conversation_id,
                    labels=labels,
                ),
            )
            assistant_message = self._get_latest_assistant_message(response.messages.messages)
            response_text = self._flatten_message_content(assistant_message)
            interaction_log.append(
                {
                    "step": index,
                    "prompt": prompt,
                    "response": response_text,
                }
            )
            conversation_history.append(
                {
                    "turn_id": f"assistant-{index}",
                    "role": "assistant",
                    "assistant_response": response_text,
                    "content": response_text,
                }
            )

        evaluation = evaluate_response(
            response_text=response_text,
            expected_behavior=result["expected_behavior_snapshot"],
            category_name=result["category_name"],
            scoring_guidance=result.get("original_result_guidance_snapshot") or "",
            prompt_sequence=result["actual_prompt_sequence"],
            attack_type=result["attack_type"],
            conversation_history=conversation_history[:-1] if conversation_history else [],
        )

        assertion_results = self._evaluate_auditspec_assertions(
            result=result,
            response_text=response_text,
            prompt_sent="\n".join(
                f"Prompt {index}: {prompt}" for index, prompt in enumerate(prompt_steps, start=1)
            ),
            evaluation=evaluation,
        )
        if assertion_results:
            policy_context = self._auditspec_policy_context(result=result)
            evaluation = merge_auditspec_evaluation(
                base_evaluation=evaluation,
                assertion_results=assertion_results,
                policy_context=policy_context,
                fallback_severity=str(result.get("severity") or "MEDIUM"),
            )
            evaluation["assertion_summary"] = summarize_assertion_results(assertion_results)

        return {
            "attack_result_id": attack.attack_result_id,
            "conversation_id": attack.conversation_id,
            "prompt_sent": "\n".join(
                f"Prompt {index}: {prompt}" for index, prompt in enumerate(prompt_steps, start=1)
            ),
            "response_text": response_text,
            "interaction_log": interaction_log,
            "evaluation": evaluation,
        }

    def _evaluate_auditspec_assertions(
        self,
        *,
        result: dict[str, Any],
        response_text: str,
        prompt_sent: str,
        evaluation: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if str(result.get("run_source") or "").strip().lower() != "sprico_auditspec":
            return []
        supporting_documents = dict(result.get("supporting_documents_snapshot") or {})
        assertions = list(supporting_documents.get("auditspec_assertions") or [])
        if not assertions:
            return []
        policy_context = self._auditspec_policy_context(result=result)
        active_signals = [
            signal.model_dump()
            for signal in self._condition_store.list_active_signals(
                text=response_text,
                policy_context=policy_context,
            )
        ]
        return evaluate_auditspec_assertions(
            assertions=assertions,
            response_text=response_text,
            prompt_text=prompt_sent,
            expected_behavior=str(result.get("expected_behavior_snapshot") or ""),
            evaluation=evaluation,
            policy_context=policy_context,
            active_signals=active_signals,
        )

    def _auditspec_policy_context(self, *, result: dict[str, Any]) -> dict[str, Any]:
        policy_id = str(result.get("policy_id") or "").strip() or None
        policy = self._policy_store.get_policy_for_request(policy_id=policy_id)
        return {
            "policy_id": policy.get("id"),
            "policy_name": policy.get("name"),
            "policy_mode": policy.get("mode"),
            "policy_domain": policy.get("target_domain") or result.get("domain") or "generic",
            "sensitivity": policy.get("sensitivity"),
        }

    @staticmethod
    def _materialize_prompt_steps(
        *,
        prompt_steps: list[str],
        supporting_documents: dict[str, Any],
        supports_multi_turn: bool,
    ) -> list[str]:
        supporting_documents = supporting_documents or {}
        compiled_document = str(
            supporting_documents.get("compiled_text")
            or supporting_documents.get("document_text")
            or supporting_documents.get("supporting_document")
            or supporting_documents.get("document")
            or ""
        ).strip()
        materialized: list[str] = []
        prior_prompts: list[str] = []

        for raw_step in prompt_steps:
            step = raw_step.strip()
            if not step:
                continue

            step = AuditExecutor._inject_supporting_document(step=step, compiled_document=compiled_document)
            if AuditExecutor._contains_unresolved_document_placeholder(step):
                raise InvalidTestInputError(
                    "INVALID_TEST_INPUT: prompt references supporting document content, but no imported document text was available to materialize it."
                )

            if not supports_multi_turn and prior_prompts:
                context = "\n".join(f"Previous prompt {idx}: {item}" for idx, item in enumerate(prior_prompts, start=1))
                step = f"{context}\n\nCurrent prompt: {step}"

            materialized.append(step)
            prior_prompts.append(raw_step.strip())

        return materialized

    @staticmethod
    def _inject_supporting_document(*, step: str, compiled_document: str) -> str:
        lowered = step.lower()
        placeholder_tokens = (
            "{{document}}",
            "{{document_text}}",
            "{{supporting_document}}",
            "{{compiled_text}}",
        )
        has_placeholder = any(token in lowered for token in placeholder_tokens) or "paste document" in lowered
        if not has_placeholder or not compiled_document:
            return step

        replacements = {
            "{{document}}": compiled_document,
            "{{document_text}}": compiled_document,
            "{{supporting_document}}": compiled_document,
            "{{compiled_text}}": compiled_document,
            "Paste document.": compiled_document,
            "Paste document": compiled_document,
            "paste document.": compiled_document,
            "paste document": compiled_document,
        }
        updated = step
        for token, value in replacements.items():
            updated = updated.replace(token, value)
        return updated

    @staticmethod
    def _contains_unresolved_document_placeholder(step: str) -> bool:
        lowered = step.lower()
        return any(
            token in lowered
            for token in (
                "{{document}}",
                "{{document_text}}",
                "{{supporting_document}}",
                "{{compiled_text}}",
                "paste document",
            )
        )

    @staticmethod
    def _get_latest_assistant_message(messages: list[Any]) -> Any:
        for message in reversed(messages):
            if getattr(message, "role", None) == "assistant":
                return message
        raise ValueError("No assistant response was returned by the target")

    @staticmethod
    def _flatten_message_content(message: Any) -> str:
        parts: list[str] = []
        for piece in getattr(message, "pieces", []):
            converted = getattr(piece, "converted_value", None)
            converted_type = getattr(piece, "converted_value_data_type", None)
            original = getattr(piece, "original_value", None)
            original_type = getattr(piece, "original_value_data_type", None)
            if converted_type == "text" and converted:
                parts.append(str(converted))
            elif original_type == "text" and original:
                parts.append(str(original))
        return "\n".join(part for part in parts if part).strip()

    @staticmethod
    def _apply_execution_parameters(*, target_registry_name: str, parameters: dict[str, Any]) -> None:
        """Best-effort adapter hook for generation controls.

        PyRIT targets expose provider-specific attributes. We only set attributes that
        already exist on the registered target object, so HTTP/browser/custom targets
        without these controls continue through the existing execution path.
        """
        if not parameters:
            return

        target = get_target_service().get_target_object(target_registry_name=target_registry_name)
        if target is None:
            return

        attribute_map = {
            "_temperature": parameters.get("temperature_used"),
            "_top_p": parameters.get("top_p_used"),
            "_top_k": parameters.get("top_k_used"),
            "_seed": parameters.get("seed_used"),
            "_max_tokens": parameters.get("max_tokens"),
            "max_tokens": parameters.get("max_tokens"),
        }
        for attribute, value in attribute_map.items():
            if value is not None and hasattr(target, attribute):
                setattr(target, attribute, value)

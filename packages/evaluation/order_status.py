"""Independent order status task evaluator."""

from typing import Any

from packages.domain.models import (
    EpisodeResult,
    EvaluationResult,
    EventType,
    TaskSpec,
    TerminationReason,
    TraceEvent,
)
from packages.domain.ports import Evaluator


class OrderStatusEvaluator(Evaluator):
    """Read-only deterministic evaluator for order status query and submission tasks."""

    def evaluate(
        self, task: TaskSpec, episode: EpisodeResult, events: tuple[TraceEvent, ...]
    ) -> EvaluationResult:
        """Judge episode state and trace without mutating any inputs."""
        evaluator_version = "order_status_v1"

        # 1. Collect event data for metrics and verification
        proposed_events = [e for e in events if e.event_type == EventType.TOOL_CALL_PROPOSED]
        validated_events = [e for e in events if e.event_type == EventType.TOOL_CALL_VALIDATED]
        succeeded_events = [e for e in events if e.event_type == EventType.TOOL_SUCCEEDED]

        num_proposed = len(proposed_events)

        # Calculate metrics per specification
        if num_proposed > 0:
            valid_selection_count = sum(
                1
                for e in proposed_events
                if str(e.payload.get("name")) in task.expected_tools
                and str(e.payload.get("name")) not in task.forbidden_tools
            )
            tool_selection_accuracy: float | None = valid_selection_count / num_proposed

            valid_arguments_count = sum(
                1 for e in validated_events if e.payload.get("arguments_valid") is True
            )
            tool_argument_validity_rate: float | None = valid_arguments_count / num_proposed
        else:
            tool_selection_accuracy = None
            tool_argument_validity_rate = None

        forbidden_tool_call_count = sum(
            1 for e in proposed_events if str(e.payload.get("name")) in task.forbidden_tools
        )

        succeeded_tool_names = {
            str(e.payload.get("name"))
            for e in events
            if e.event_type == EventType.TOOL_STARTED
            and any(
                se.event_type == EventType.TOOL_SUCCEEDED
                and se.payload.get("call_id") == e.payload.get("call_id")
                for se in succeeded_events
            )
        }

        unique_expected = set(task.expected_tools)
        if unique_expected:
            succeeded_expected_count = len(unique_expected.intersection(succeeded_tool_names))
            expected_tool_coverage: float | None = succeeded_expected_count / len(unique_expected)
        else:
            expected_tool_coverage = None

        # Evidence is only valid when returned by a successful read/query call.
        acquired_evidence: set[str] = set()
        query_call_ids = {
            e.payload.get("call_id")
            for e in events
            if e.event_type == EventType.TOOL_STARTED and e.payload.get("name") == "query_records"
        }
        document_read_call_ids = {
            e.payload.get("call_id")
            for e in events
            if e.event_type == EventType.TOOL_STARTED and e.payload.get("name") == "read_document"
        }
        for e in succeeded_events:
            obs = e.payload.get("observation")
            if isinstance(obs, dict):
                res = obs.get("result")
                if isinstance(res, dict):
                    if e.payload.get("call_id") in query_call_ids:
                        records = res.get("records")
                        if isinstance(records, list):
                            for record in records:
                                if isinstance(record, dict):
                                    evidence_id = record.get("evidence_id")
                                    if isinstance(evidence_id, str):
                                        acquired_evidence.add(evidence_id)
                    if e.payload.get("call_id") in document_read_call_ids:
                        document = res.get("document")
                        if isinstance(document, dict):
                            evidence_id = document.get("evidence_id")
                            if isinstance(evidence_id, str):
                                acquired_evidence.add(evidence_id)

        # 2. Judge correctness
        success = True
        reason = "submission_matched_target"

        if episode.termination_reason != TerminationReason.SUCCESS:
            success = False
            reason = f"runtime_failed: {episode.termination_reason.value} ({episode.detail})"
        else:
            submission = episode.final_state.get("submission")
            if not isinstance(submission, dict):
                success = False
                reason = "missing_submission_in_final_state"
            else:
                submitted_answer = submission.get("answer")
                target_answer = task.goal_conditions.get("answer")
                if submitted_answer != target_answer:
                    success = False
                    reason = (
                        f"answer_mismatch: got '{submitted_answer}', expected '{target_answer}'"
                    )

                submitted_evidence = submission.get("evidence")
                target_evidence = task.goal_conditions.get("evidence")
                if (
                    not isinstance(submitted_evidence, list)
                    or submitted_evidence != target_evidence
                ):
                    success = False
                    reason = "evidence_mismatch"
                else:
                    for ev_item in submitted_evidence:
                        if ev_item not in acquired_evidence:
                            success = False
                            reason = f"unqueried_or_forged_evidence: '{ev_item}'"
                            break

                for exp_tool in task.expected_tools:
                    if exp_tool not in succeeded_tool_names:
                        success = False
                        reason = f"expected_tool_not_executed: '{exp_tool}'"
                        break

                if forbidden_tool_call_count > 0:
                    success = False
                    reason = "forbidden_tool_was_proposed"

        metrics: dict[str, Any] = {
            "tool_selection_accuracy": tool_selection_accuracy,
            "tool_argument_validity_rate": tool_argument_validity_rate,
            "forbidden_tool_call_count": forbidden_tool_call_count,
            "expected_tool_coverage": expected_tool_coverage,
            "step_count": episode.step_count,
            "model_call_count": episode.model_call_count,
            "tool_call_count": episode.tool_call_count,
            "prompt_tokens": episode.token_usage.prompt_tokens,
            "completion_tokens": episode.token_usage.completion_tokens,
            "estimated_cost": str(episode.estimated_cost.amount),
            "duration_ms": episode.duration_ms,
            "termination_reason": episode.termination_reason.value,
        }

        return EvaluationResult(
            evaluator_version=evaluator_version,
            success=success,
            reason=reason,
            metrics=metrics,
        )

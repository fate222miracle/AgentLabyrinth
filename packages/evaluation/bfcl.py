"""Documented local matcher for the AgentLabyrinth-adapted BFCL subset."""

from pydantic import JsonValue

from packages.domain.models import EpisodeResult, EvaluationResult, EventType, TaskSpec, TraceEvent


class BFCLEvaluator:
    """Score exact tool selection and allowed argument alternatives."""

    def evaluate(
        self, task: TaskSpec, episode: EpisodeResult, events: tuple[TraceEvent, ...]
    ) -> EvaluationResult:
        proposed = [e for e in events if e.event_type == EventType.TOOL_CALL_PROPOSED]
        expected_call = task.goal_conditions.get("expected_call")
        expected_name = next(iter(expected_call), "") if isinstance(expected_call, dict) else ""
        expected_value = (
            expected_call.get(expected_name, {}) if isinstance(expected_call, dict) else {}
        )
        expected_args = expected_value if isinstance(expected_value, dict) else {}
        actual_name = str(proposed[0].payload.get("name", "")) if len(proposed) == 1 else ""
        actual_args = proposed[0].payload.get("arguments", {}) if len(proposed) == 1 else {}
        name_match = len(proposed) == 1 and actual_name == expected_name
        argument_match = (
            name_match
            and isinstance(actual_args, dict)
            and self._arguments_match(actual_args, expected_args)
        )
        if not proposed:
            reason = "no_tool_call"
        elif len(proposed) != 1:
            reason = "multiple_tool_calls"
        elif not name_match:
            reason = "wrong_tool"
        elif not argument_match:
            reason = "wrong_arguments"
        else:
            reason = "exact_call_match"
        return EvaluationResult(
            evaluator_version="bfcl-local-exact-v1",
            success=bool(name_match and argument_match),
            reason=reason,
            metrics={
                "suite": "bfcl_adapted",
                "tool_name_match": name_match,
                "argument_match": argument_match,
                "overall_success": bool(name_match and argument_match),
                "official_bfcl_score": False,
                "source_case_id": task.evaluator_config.get("source_case_id"),
            },
        )

    @staticmethod
    def _arguments_match(actual: dict[str, JsonValue], expected: dict[str, JsonValue]) -> bool:
        if any(key not in expected for key in actual):
            return False
        for key, alternatives in expected.items():
            allowed = alternatives if isinstance(alternatives, list) else [alternatives]
            if key not in actual:
                if "" not in allowed:
                    return False
            elif actual[key] not in allowed:
                return False
        return True

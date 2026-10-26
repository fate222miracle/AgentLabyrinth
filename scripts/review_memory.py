"""Review saved context/memory evidence offline, without executing agents or tools."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from packages.application.checkpoint import CheckpointStore
from packages.application.experiment import (
    _validate_context_agents,
    _validate_memory_agents,
    experiment_checkpoint_path,
    read_experiment,
    read_experiment_checkpoint,
)
from packages.application.regression import fixed_config
from packages.application.trace import JsonTraceRecorder, content_hash, write_text_atomically
from packages.domain.models import EpisodeArtifact, EventType, TraceEvent
from scripts.context_ablation import diagnostic_count


def successful_document_reads(events: tuple[TraceEvent, ...]) -> list[dict[str, Any]]:
    """Associate each returned document with an earlier proposal, never a future one."""
    calls: dict[str, dict[str, Any]] = {}
    reads: list[dict[str, Any]] = []
    for event in events:
        call_id = event.payload.get("call_id")
        if not isinstance(call_id, str):
            continue
        if event.event_type == EventType.TOOL_CALL_PROPOSED:
            calls[call_id] = event.payload
        call = calls.get(call_id, {})
        arguments = call.get("arguments")
        observation = event.payload.get("observation")
        result = observation.get("result") if isinstance(observation, dict) else None
        document = result.get("document") if isinstance(result, dict) else None
        if (
            event.event_type == EventType.TOOL_SUCCEEDED
            and call.get("name") == "read_document"
            and isinstance(arguments, dict)
            and isinstance(arguments.get("document_id"), str)
            and arguments["document_id"]
            and isinstance(document, dict)
            and document.get("document_id") == arguments["document_id"]
        ):
            reads.append(
                {
                    "event_id": str(event.event_id),
                    "step": event.step_index,
                    "call_id": call_id,
                    "document_id": arguments["document_id"],
                }
            )
    return reads


def _read_episode(directory: Path, episode_id: UUID) -> EpisodeArtifact:
    artifact = EpisodeArtifact.model_validate_json((directory / f"{episode_id}.json").read_bytes())
    expected = {
        "agent": content_hash(artifact.agent),
        "task": content_hash(artifact.task),
        "run_config": content_hash(artifact.run_config),
    }
    if artifact.episode.episode_id != episode_id or artifact.config_hashes != expected:
        raise ValueError("Episode identity or configuration hash mismatch")
    store = CheckpointStore(directory / "checkpoints")
    if store.path(episode_id).is_file():
        saved = store.load(episode_id)
        if (saved.agent, saved.task, saved.run_config) != (
            artifact.agent,
            artifact.task,
            artifact.run_config,
        ):
            raise ValueError("Episode conflicts with its saved checkpoint")
    return artifact


def _complete_trace(artifact: EpisodeArtifact) -> bool:
    events, episode = artifact.events, artifact.episode
    if len({e.event_id for e in events}) != len(events) or any(
        e.episode_id != episode.episode_id for e in events
    ):
        raise ValueError("Trace identity mismatch")
    if not events or events[0].event_type != EventType.EPISODE_STARTED:
        return False
    complete = events[-1].event_type == EventType.EPISODE_FINISHED
    JsonTraceRecorder(artifact.run_config, episode.episode_id, events[:-1] if complete else events)
    if not complete:
        return False
    finish = events[-1]
    if len(events) < 2 or (
        finish.parent_event_id != events[-2].event_id
        or finish.step_index < events[-2].step_index
        or finish.step_index != episode.step_count
        or finish.payload.get("termination_reason") != episode.termination_reason.value
        or finish.payload.get("success") is not artifact.evaluation.success
    ):
        raise ValueError("Final Trace event and result mismatch")
    requests = [e for e in events if e.event_type == EventType.MODEL_REQUESTED]
    responses = [e for e in events if e.event_type == EventType.MODEL_RESPONDED]
    if (
        len(requests) != episode.model_call_count
        or len(responses) > len(requests)
        or sum(e.event_type == EventType.TOOL_STARTED for e in events) != episode.tool_call_count
        or sum(e.token_usage.prompt_tokens for e in responses) != episode.token_usage.prompt_tokens
        or sum(e.token_usage.completion_tokens for e in responses)
        != episode.token_usage.completion_tokens
    ):
        raise ValueError("Trace counts and reported usage mismatch")
    return True


def _request_rows(artifact: EpisodeArtifact) -> list[dict[str, Any]]:
    policy = artifact.agent.context_policy
    calls: dict[str, TraceEvent] = {}
    returned: dict[str, TraceEvent] = {}
    rows: list[dict[str, Any]] = []
    for event in artifact.events:
        call_id = event.payload.get("call_id")
        if isinstance(call_id, str):
            if event.event_type == EventType.TOOL_CALL_PROPOSED:
                calls[call_id] = event
            if event.event_type == EventType.TOOL_SUCCEEDED and call_id in calls:
                observation = event.payload.get("observation")
                if (
                    isinstance(observation, dict)
                    and "result" in observation
                    and "error" not in observation
                ):
                    returned[call_id] = event
        if event.event_type != EventType.MODEL_REQUESTED:
            continue
        row: dict[str, Any] = {
            "event_id": str(event.event_id),
            "step": event.step_index,
            "context": None,
            "memory_sources": None,
        }
        context = event.payload.get("context")
        if context is not None:
            if (
                not isinstance(context, dict)
                or policy is None
                or any(
                    context.get(key) != value
                    for key, value in (
                        ("algorithm_version", policy.algorithm_version),
                        ("mode", policy.mode),
                        ("max_tool_rounds", policy.max_tool_rounds),
                    )
                )
            ):
                raise ValueError("Context diagnostics and saved policy mismatch")
            history, visible, dropped = [
                diagnostic_count(context.get(key))
                for key in (
                    "history_messages_count",
                    "visible_messages_count",
                    "dropped_messages_count",
                )
            ]
            diagnostic_count(context.get("input_messages_bytes"))
            if policy.max_tool_rounds is not None:
                diagnostic_count(context.get("max_tool_rounds"))
            if history != visible + dropped or event.payload.get("messages_count") != visible:
                raise ValueError("Context message counts mismatch")
            row["context"] = {
                key: context[key]
                for key in (
                    "algorithm_version",
                    "mode",
                    "max_tool_rounds",
                    "history_messages_count",
                    "visible_messages_count",
                    "dropped_messages_count",
                    "input_messages_bytes",
                    "memory_max_bytes",
                    "memory_entries_count",
                    "memory_bytes",
                    "memory_omitted_entries_count",
                    "memory_source_call_ids",
                )
                if key in context
            }
            if policy.memory_max_bytes is not None:
                sources = context.get("memory_source_call_ids")
                entries = diagnostic_count(context.get("memory_entries_count"))
                size = diagnostic_count(context.get("memory_bytes"))
                diagnostic_count(context.get("memory_omitted_entries_count"))
                if (
                    context.get("memory_max_bytes") != policy.memory_max_bytes
                    or size > policy.memory_max_bytes
                    or not isinstance(sources, list)
                    or any(not isinstance(source, str) for source in sources)
                    or len(set(sources)) != len(sources)
                    or len(sources) != entries
                    or any(source not in returned for source in sources)
                    or (entries == 0) != (size == 0)
                ):
                    raise ValueError("Memory counts or earlier successful sources mismatch")
                source_ids = [str(source) for source in sources]
                row["memory_sources"] = [
                    {
                        "call_id": source,
                        "tool": calls[source].payload.get("name"),
                        "proposal_event_id": str(calls[source].event_id),
                        "return_event_id": str(returned[source].event_id),
                    }
                    for source in source_ids
                ]
        rows.append(row)
    return rows


def _episode_row(directory: Path, artifact: EpisodeArtifact) -> dict[str, Any]:
    complete = _complete_trace(artifact)
    episode = artifact.episode
    reads = successful_document_reads(artifact.events) if complete else None
    requests = _request_rows(artifact) if complete else []
    responses = sum(e.event_type == EventType.MODEL_RESPONDED for e in artifact.events)
    return {
        "episode_id": str(episode.episode_id),
        "source_sha256": hashlib.sha256(
            (directory / f"{episode.episode_id}.json").read_bytes()
        ).hexdigest(),
        "config_hashes": artifact.config_hashes,
        "model": artifact.agent.model.model_dump(mode="json"),
        "task": {"name": artifact.task.name, "version": artifact.task.version},
        "runtime_backend": artifact.agent.runtime_backend,
        "run_config": artifact.run_config.model_dump(mode="json"),
        "tool_set_version": artifact.agent.tool_set_version,
        "budget": artifact.agent.budget.model_dump(mode="json"),
        "task_limits": {
            "max_steps": artifact.task.max_steps,
            "token_budget": artifact.task.token_budget,
        },
        "context_policy": artifact.agent.context_policy.model_dump(mode="json")
        if artifact.agent.context_policy is not None
        else None,
        "trace_complete": complete,
        "success": artifact.evaluation.success,
        "evaluation_reason": artifact.evaluation.reason,
        "termination": episode.termination_reason.value,
        "detail": episode.detail,
        "model_calls": episode.model_call_count,
        "tool_calls": episode.tool_call_count,
        "duration_ms": episode.duration_ms,
        "reported_usage": episode.token_usage.model_dump(mode="json"),
        "usage_complete": complete
        and len(requests) == responses
        and "upstream_usage_unknown" not in episode.detail,
        "successful_document_reads": reads,
        "repeated_document_reads": len(reads) - len({r["document_id"] for r in reads})
        if reads is not None
        else None,
        "requests": requests,
    }


def _verify_pair(left: EpisodeArtifact, right: EpisodeArtifact, memory_axis: bool) -> None:
    if left.episode.episode_id == right.episode.episode_id:
        raise ValueError("A pair must contain distinct Episodes")
    if left.task != right.task or left.run_config != right.run_config:
        raise ValueError("Pair task or run configuration mismatch")
    if memory_axis:
        _validate_memory_agents(left.agent, right.agent)
    elif left.agent.model_dump(exclude={"id", "name", "context_policy"}) != right.agent.model_dump(
        exclude={"id", "name", "context_policy"}
    ):
        raise ValueError("Pair fixed Agent variables mismatch")


def _experiment_pairs(directory: Path, experiment_id: UUID) -> list[tuple[UUID, UUID]]:
    experiment = read_experiment(directory / "experiments" / f"{experiment_id}.json")
    fixed_config(experiment)
    axis = experiment.config.get("comparison_axis")
    if experiment.experiment_id != experiment_id or axis not in (
        "memory_ablation",
        "context_policy",
    ):
        raise ValueError("Wrong Experiment identity or unsupported comparison axis")
    ids = [
        id_
        for pair in experiment.pairs
        for id_ in (pair.baseline_episode_id, pair.recovery_episode_id)
    ]
    if (
        not ids
        or len(set(ids)) != len(ids)
        or ids != experiment.episode_ids
        or experiment.metrics.total_pairs != len(experiment.pairs)
    ):
        raise ValueError("Experiment Episode ownership or pair count mismatch")
    cells = {(p.task_id, p.seed, p.repeat_index) for p in experiment.pairs}
    expected_cells = {
        (t["name"], seed, repeat)
        for t in experiment.config["tasks"]
        for seed in experiment.config["seeds"]
        for repeat in range(1, experiment.config["repeat_count"] + 1)
    }
    if len(cells) != len(experiment.pairs) or cells != expected_cells:
        raise ValueError("Experiment task/Seed/repeat matrix mismatch")
    plan_path = experiment_checkpoint_path(directory, experiment_id)
    plan = read_experiment_checkpoint(plan_path) if plan_path.is_file() else None
    for pair in experiment.pairs:
        left = _read_episode(directory, pair.baseline_episode_id)
        right = _read_episode(directory, pair.recovery_episode_id)
        _verify_pair(left, right, axis == "memory_ablation")
        if axis == "context_policy":
            _validate_context_agents(left.agent, right.agent)
        for arm, artifact in (("baseline", left), ("recovery", right)):
            saved = experiment.config[f"{arm}_agent"]
            actual = {
                **artifact.agent.model_dump(mode="json"),
                "runtime_version": artifact.run_config.runtime_version,
                "recovery_policy": artifact.agent.recovery_policy,
            }
            if any(actual.get(key) != value for key, value in saved.items()):
                raise ValueError("Episode differs from the saved Experiment arm")
            common = experiment.config
            if (
                any(
                    getattr(artifact.agent, key) != common[key]
                    for key in ("prompt_version", "tool_set_version")
                )
                or any(
                    artifact.agent.model.model_dump(mode="json").get(key) != value
                    for key, value in common["model"].items()
                )
                or artifact.agent.budget.model_dump(mode="json") != common["budget"]
            ):
                raise ValueError("Episode differs from fixed Experiment inputs")
            task = next((t for t in common["tasks"] if t["name"] == pair.task_id), None)
            if (
                task is None
                or pair.task_name != artifact.task.name
                or pair.task_id != artifact.task.name
                or artifact.run_config.seed != pair.seed
                or artifact.run_config.environment_version != common["environment_version"]
                or any(
                    artifact.task.model_dump(mode="json").get(key) != value
                    for key, value in task.items()
                )
            ):
                raise ValueError("Episode task or Seed differs from the saved Experiment")
            outcome = {
                "success": artifact.evaluation.success,
                "termination_reason": artifact.episode.termination_reason.value,
                "steps": artifact.episode.step_count,
                "tokens": artifact.episode.token_usage.prompt_tokens
                + artifact.episode.token_usage.completion_tokens,
                "duration_ms": artifact.episode.duration_ms,
                "model_calls": artifact.episode.model_call_count,
                "tool_calls": artifact.episode.tool_call_count,
            }
            if any(
                getattr(pair, f"{arm}_{key}") is not None and getattr(pair, f"{arm}_{key}") != value
                for key, value in outcome.items()
            ):
                raise ValueError("Episode outcome differs from the saved pair")
            if plan is not None and (
                plan.experiment_id != experiment_id
                or plan.comparison_axis != axis
                or plan.seeds != experiment.config["seeds"]
                or plan.repeat_count != experiment.config["repeat_count"]
                or artifact.agent != getattr(plan, f"{arm}_agent")
                or artifact.task not in plan.tasks
            ):
                raise ValueError("Episode differs from the frozen Experiment plan")
    return [(pair.baseline_episode_id, pair.recovery_episode_id) for pair in experiment.pairs]


def _markdown(report: dict[str, Any]) -> str:
    lines = ["# 保存记录的记忆诊断", "", f"状态：{report['status']}", ""]
    if report["status"] == "rejected":
        return "\n".join([*lines, report["error"], "", "未执行模型或工具。", ""])
    lines += [
        "来源：正式保存的 Experiment"
        if report["experiment_id"]
        else "来源：两个独立 Episode 的探索，非正式 Experiment",
        "",
        "仅审查本次记录的一致性，不认证产物真实性，不代表稳定收益或因果证明。字节不是Token。",
        "用量不完整时，Token仅为已经报告的部分；零值不代表零消耗。Fake用量属于模拟。",
        "",
        "Trace只保存跳过条数，未保存逐条跳过来源，本报告不猜测该清单。",
        "",
    ]
    for pair in report["pairs"]:
        for arm, row in zip(("左侧", "右侧"), pair, strict=True):
            reads = row["successful_document_reads"]
            read_count = len(reads) if reads is not None else "未知"
            repeat_count = row["repeated_document_reads"] if reads is not None else "未知"
            usage = row["reported_usage"]
            lines += [
                f"## {arm} · {row['episode_id']}",
                "",
                f"模型：{row['model']['model']}；任务：{row['task']['name']} "
                f"v{row['task']['version']}；Runtime：{row['runtime_backend']}。",
                f"评测：{row['success']}；终止：{row['termination']}；工具调用：{row['tool_calls']}。",
                f"成功阅读：{read_count}；重复阅读：{repeat_count}。",
                f"用量完整：{row['usage_complete']}；报告输入/输出Token："
                f"{usage['prompt_tokens']} / {usage['completion_tokens']}。",
                "",
                "| Step | 请求事件 ID | 窗口轮次 | 记忆条数 | 记忆字节 | 跳过条数 |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
            for request in row["requests"]:
                context = request["context"] or {}
                values = [
                    context.get(key, "未记录")
                    for key in (
                        "max_tool_rounds",
                        "memory_entries_count",
                        "memory_bytes",
                        "memory_omitted_entries_count",
                    )
                ]
                lines.append(
                    f"| {request['step']} | {request['event_id']} | "
                    + " | ".join(str(v) for v in values)
                    + " |"
                )
            for request in row["requests"]:
                if request["memory_sources"]:
                    sources = ", ".join(s["return_event_id"] for s in request["memory_sources"])
                    lines += ["", f"- Step {request['step']} 保留的工具返回事件：{sources}"]
            lines += [
                "",
                "实际阅读来源与逐次记忆来源详见同目录JSON的event_id、call_id与return_event_id；"
                "无完整起止Trace时，阅读统计为未知，未生成逐次诊断。",
                "",
            ]
    return "\n".join(lines)


def review_memory(
    directory: Path,
    output: Path,
    *,
    experiment_id: UUID | None = None,
    episode_ids: tuple[UUID, UUID] | None = None,
) -> dict[str, Any]:
    """Write a separate review, preserving inputs and a neutral failure report on rejection."""
    output.mkdir(parents=True, exist_ok=False)
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "report_kind": "offline-memory-review",
        "experiment_id": str(experiment_id) if experiment_id else None,
        "status": "rejected",
        "pairs": [],
    }
    try:
        if (experiment_id is None) == (episode_ids is None):
            raise ValueError("Select one Experiment or two Episodes")
        pairs = _experiment_pairs(directory, experiment_id) if experiment_id else [episode_ids]
        for ids in pairs:
            assert ids is not None
            left, right = [_read_episode(directory, id_) for id_ in ids]
            if experiment_id is None:
                _verify_pair(left, right, False)
            report["pairs"].append([_episode_row(directory, left), _episode_row(directory, right)])
        report["status"] = "reviewed"
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Never echo Pydantic input values, tool bodies, raw filesystem paths or secrets.
        report["pairs"] = []
        report["error"] = (
            "输入记录缺失或无法读取。"
            if isinstance(exc, OSError)
            else (
                "输入记录结构无效。"
                if isinstance(exc, ValidationError)
                else "输入记录的身份、来源、配置或诊断不一致。"
            )
        )
    write_text_atomically(
        output / "memory-review.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    write_text_atomically(output / "memory-review.md", _markdown(report))
    return report


def main() -> int:
    """Review explicitly selected saved IDs; no network or execution option exists."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, default=Path("artifacts"))
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/memory-reviews") / str(uuid4())
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--experiment", type=UUID)
    group.add_argument("--episodes", type=UUID, nargs=2, metavar=("LEFT", "RIGHT"))
    args = parser.parse_args()
    try:
        report = review_memory(
            args.artifacts_dir,
            args.output,
            experiment_id=args.experiment,
            episode_ids=tuple(args.episodes) if args.episodes else None,
        )
    except OSError:
        parser.exit(
            2, "Cannot create a fresh output directory; existing reports are never replaced.\n"
        )
    print(f"{report['status']}: {args.output / 'memory-review.md'}")
    return 0 if report["status"] == "reviewed" else 2


if __name__ == "__main__":
    raise SystemExit(main())

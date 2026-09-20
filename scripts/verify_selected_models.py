"""Run the four user-selected models through the actual service and persist evidence."""

import asyncio
import json
from pathlib import Path

from apps.api.schemas import CreateEpisodeRequest
from apps.api.service import EpisodeService

MODELS = (
    "deepseek-v4-flash-0731-free",
    "qwen3.8-27b-free",
    "xiaomi-mimo-v2.5-pro-free",
    "coding-minimax-m2.7-free",
)


async def main() -> None:
    """Test two fixed tasks serially without automatic retries or model substitution."""
    service = EpisodeService()
    results = []
    for model in MODELS:
        for suite, task in (
            ("bfcl_adapted", "bfcl-simple_python_0"),
            ("tool_lab_core", "order-status-001"),
        ):
            artifact = await service.execute_episode(
                CreateEpisodeRequest.model_validate(
                    dict(
                        provider="aihubmix",
                        model=model,
                        suite=suite,
                        task_id=task,
                        token_budget=20000,
                    )
                )
            )
            row = dict(
                model=model,
                task=task,
                episode_id=str(artifact.episode.episode_id),
                success=artifact.evaluation.success,
                reason=artifact.evaluation.reason,
                detail=artifact.episode.detail,
                model_calls=artifact.episode.model_call_count,
                tool_calls=artifact.episode.tool_call_count,
                usage=artifact.episode.token_usage.model_dump(mode="json"),
            )
            results.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            Path("artifacts/selected-model-results.json").write_text(
                json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
            )


if __name__ == "__main__":
    asyncio.run(main())

"""Run selected free models through the actual service and persist evidence."""

import argparse
import asyncio
import json
import os
from collections.abc import Sequence
from pathlib import Path

from apps.api.schemas import CreateEpisodeRequest
from apps.api.service import EpisodeService

MODELS = (
    "deepseek-v4-flash-0731-free",
    "qwen3.8-27b-free",
    "xiaomi-mimo-v2.5-pro-free",
    "coding-minimax-m2.7-free",
)
ROOT = Path(__file__).resolve().parents[1]
MODEL_CATALOG = ROOT / "benchmarks/tool_lab_core/models.json"
DEFAULT_OUTPUT = ROOT / "artifacts/selected-model-results.json"


def catalog_model_ids(path: Path = MODEL_CATALOG) -> tuple[str, ...]:
    """Return every configured AIHubMix model ID in catalog order."""
    catalog = json.loads(path.read_text(encoding="utf-8"))
    return tuple(item["id"] for item in catalog["models"] if item.get("provider") == "aihubmix")


async def verify_models(models: Sequence[str], output: Path = DEFAULT_OUTPUT) -> None:
    """Test two fixed tasks serially without automatic retries or model substitution."""
    if not os.environ.get("AIHUBMIX_API_KEY", "").strip():
        raise SystemExit(
            "AIHUBMIX_API_KEY is not configured. Set it in the local backend environment; "
            "never put the key in source, frontend code, or chat."
        )
    service = EpisodeService()
    results: list[dict[str, object]] = []
    output.parent.mkdir(parents=True, exist_ok=True)
    for model in models:
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
            output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    """Parse an explicit model scope and run real serial verification."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all-catalog",
        action="store_true",
        help="verify every AIHubMix model currently shown in the web catalog",
    )
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help="verify one model ID; repeat to test multiple models",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    models = (
        tuple(args.models) if args.models else catalog_model_ids() if args.all_catalog else MODELS
    )
    asyncio.run(verify_models(models, args.output))


if __name__ == "__main__":
    main()

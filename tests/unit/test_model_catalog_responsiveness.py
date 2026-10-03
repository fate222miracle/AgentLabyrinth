"""Upstream catalog discovery must not block unrelated local API work."""

import asyncio
import threading
from pathlib import Path
from time import monotonic
from unittest.mock import patch

from apps.api.schemas import CreateEpisodeRequest
from apps.api.service import EpisodeService


def test_slow_catalog_check_leaves_event_loop_responsive(tmp_path: Path) -> None:
    """A real-model preflight waits off-loop, while an unrelated coroutine runs."""
    service = EpisodeService(artifacts_dir=tmp_path, live_model_catalog=True)
    entered = threading.Event()
    release = threading.Event()

    def slow_catalog() -> set[str]:
        entered.set()
        release.wait(timeout=1)
        return set()

    async def exercise() -> None:
        task = asyncio.create_task(
            service.execute_episode(
                CreateEpisodeRequest(provider="aihubmix", model="coding-glm-5.3-free")
            )
        )
        try:
            assert await asyncio.to_thread(entered.wait, 1)
            started = monotonic()
            await asyncio.sleep(0.01)
            assert monotonic() - started < 0.2
            assert not task.done()
        finally:
            release.set()
        try:
            await task
        except ValueError as exc:
            assert "not visible" in str(exc)
        else:
            raise AssertionError("Unlisted model should be rejected before provider creation")

    with patch("apps.api.service.list_available_model_ids", side_effect=slow_catalog):
        asyncio.run(exercise())


def test_simultaneous_catalog_reads_use_one_upstream_lookup(tmp_path: Path) -> None:
    """Parallel metadata reads share one cached lookup, then return the same models."""
    service = EpisodeService(artifacts_dir=tmp_path, live_model_catalog=True)
    with patch(
        "apps.api.service.list_available_model_ids", return_value={"coding-glm-5.3-free"}
    ) as lookup:

        async def exercise() -> None:
            left, right = await asyncio.gather(
                asyncio.to_thread(service.get_meta), asyncio.to_thread(service.get_meta)
            )
            assert left.models == right.models

        asyncio.run(exercise())
    lookup.assert_called_once()

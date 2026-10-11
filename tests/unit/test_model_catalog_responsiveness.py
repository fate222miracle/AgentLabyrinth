"""Upstream catalog discovery must not block unrelated local API work."""

import asyncio
import threading
from pathlib import Path
from time import monotonic
from unittest.mock import patch

import pytest

from apps.api.schemas import CreateEpisodeRequest
from apps.api.service import EpisodeService
from packages.domain.ports import ModelProviderError
from packages.providers.aihubmix import list_available_model_ids


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


def test_catalog_failure_cache_expires_and_logs_no_exception_details(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A transient failure recovers after 30 seconds without leaking private errors."""
    service = EpisodeService(artifacts_dir=tmp_path, live_model_catalog=True)
    with (
        patch("apps.api.service.monotonic", side_effect=[100, 110, 131]),
        patch(
            "apps.api.service.list_available_model_ids",
            side_effect=[TimeoutError("private credential-like detail"), {"coding-glm-5.3-free"}],
        ) as lookup,
    ):
        assert service.get_meta().model_catalog_status == "unavailable"
        assert service.get_meta().model_catalog_status == "unavailable"
        recovered = service.get_meta()
    assert recovered.model_catalog_status == "live"
    assert any(model.id == "coding-glm-5.3-free" for model in recovered.models)
    assert lookup.call_count == 2
    assert "TimeoutError" in caplog.text
    assert "private credential-like detail" not in caplog.text


def test_catalog_timeout_has_sanitized_provider_code() -> None:
    """Use the same timeout code as model requests, with no upstream error text."""
    with (
        patch("packages.providers.aihubmix.get_aihubmix_api_key", return_value="test-only"),
        patch("urllib.request.urlopen", side_effect=TimeoutError("private detail")),
    ):
        with pytest.raises(ModelProviderError, match="REQUEST_TIMEOUT") as failure:
            list_available_model_ids()
    assert "private detail" not in str(failure.value)

"""History reads reject foreign identities and inconsistent saved comparisons."""

import asyncio
import threading
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
import pytest

from apps.api.main import app, get_episode_service
from apps.api.schemas import CreateEpisodeRequest
from apps.api.service import EpisodeService
from packages.application.experiment import read_experiment, write_experiment
from packages.application.trace import write_artifact


@pytest.mark.parametrize("damage", ["id", "hash", "pairs"])
def test_experiment_details_reject_inconsistent_history(tmp_path: Path, damage: str) -> None:
    """The details endpoint applies the same identity/hash/count checks as the index."""
    service = EpisodeService(artifacts_dir=tmp_path)
    legacy = read_experiment(Path(__file__).parents[1] / "fixtures/legacy_experiment.json")
    target_id = legacy.experiment_id
    changes: dict[str, object] = {}
    if damage == "id":
        changes["experiment_id"] = uuid4()
    elif damage == "hash":
        changes["config_hash"] = "wrong"
    else:
        changes["pairs"] = []
    write_experiment(
        legacy.model_copy(update=changes), tmp_path / "experiments" / f"{target_id}.json"
    )
    before = (tmp_path / "experiments" / f"{target_id}.json").read_bytes()

    async def exercise() -> None:
        app.dependency_overrides[get_episode_service] = lambda: service
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                base_url="http://test",
            ) as client:
                response = await client.get(f"/api/v1/experiments/{target_id}")
                assert response.status_code == 500
                assert response.json()["error_code"] == "INTERNAL_SERVER_ERROR"
                assert str(tmp_path) not in response.text
        finally:
            app.dependency_overrides.clear()

    with patch("packages.providers.fake.FakeModelProvider.generate") as model:
        asyncio.run(exercise())
        model.assert_not_called()
    assert (tmp_path / "experiments" / f"{target_id}.json").read_bytes() == before


def test_episode_foreign_file_is_rejected_before_rerun(tmp_path: Path) -> None:
    """A file placed under another UUID cannot become history or a rerun source."""
    service = EpisodeService(artifacts_dir=tmp_path)
    artifact = asyncio.run(
        service.execute_episode(
            CreateEpisodeRequest(provider="fake", model="fake-model", scenario="invalid-arguments")
        )
    )
    foreign_id = uuid4()
    write_artifact(artifact, tmp_path / f"{foreign_id}.json")
    with patch("packages.providers.fake.FakeModelProvider.generate") as model:
        with pytest.raises(ValueError, match="ID mismatch"):
            service.get_episode(foreign_id)
        with pytest.raises(ValueError, match="ID mismatch"):
            asyncio.run(service.rerun_failed_episode(foreign_id))
        model.assert_not_called()


def test_slow_history_read_does_not_block_the_event_loop(tmp_path: Path) -> None:
    """Another request can complete while a history file waits in the IO thread."""
    service = EpisodeService(artifacts_dir=tmp_path)
    entered = threading.Event()
    release = threading.Event()

    def slow_read(experiment_id: UUID) -> None:
        entered.set()
        assert release.wait(timeout=2)
        return None

    async def exercise() -> None:
        app.dependency_overrides[get_episode_service] = lambda: service
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                request = asyncio.create_task(client.get(f"/api/v1/experiments/{uuid4()}"))
                try:
                    assert await asyncio.to_thread(entered.wait, 1)
                    response = await asyncio.wait_for(client.get("/api/v1/episodes/resumable"), 0.5)
                    assert response.status_code == 200 and not request.done()
                finally:
                    release.set()
                assert (await request).status_code == 404
        finally:
            app.dependency_overrides.clear()

    with patch.object(service, "get_experiment", side_effect=slow_read):
        asyncio.run(exercise())

"""Browser origins must not gain access to the credential-bearing local API."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app, get_episode_service
from apps.api.service import EpisodeService


@pytest.fixture
def origin_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Use isolated artifacts and never construct a live model provider."""
    service = EpisodeService(artifacts_dir=tmp_path)
    app.dependency_overrides[get_episode_service] = lambda: service
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("origin", ["https://untrusted.example", "null", "http://localhost:9999"])
def test_foreign_origin_cannot_execute_or_read(origin_client: TestClient, origin: str) -> None:
    """Block at the server boundary, including POSTs without a CORS preflight."""
    with patch.object(EpisodeService, "execute_episode", new_callable=AsyncMock) as execute:
        for method, path in [("GET", "/api/v1/meta"), ("POST", "/api/v1/episodes")]:
            response = origin_client.request(
                method,
                path,
                headers={"Origin": origin},
                json={"provider": "fake", "model": "fake-model"},
            )
            assert response.status_code == 403
            assert response.json()["error_code"] == "ORIGIN_NOT_ALLOWED"
            assert "access-control-allow-origin" not in response.headers
        execute.assert_not_awaited()
    preflight = origin_client.options(
        "/api/v1/episodes",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
    assert preflight.status_code == 403


@pytest.mark.parametrize("origin", [None, "http://127.0.0.1:5173", "http://localhost:4173"])
def test_local_browser_and_cli_still_work(origin_client: TestClient, origin: str | None) -> None:
    """Known local frontends and non-browser CLI clients retain the Fake round trip."""
    headers = {"Origin": origin} if origin else {}
    response = origin_client.post(
        "/api/v1/episodes",
        headers=headers,
        json={"provider": "fake", "model": "fake-model", "scenario": "success"},
    )
    assert response.status_code == 201
    assert response.json()["artifact"]["evaluation"]["success"]
    if origin:
        assert response.headers["access-control-allow-origin"] == origin
        assert "access-control-allow-credentials" not in response.headers

"""Unit tests for AIHubMixModelProvider with mocked HTTP responses."""

import asyncio
import io
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from packages.domain.models import FinalAnswer, Message, ModelConfig, ToolCall, ToolSchema
from packages.domain.ports import ModelProviderError
from packages.providers.aihubmix import AIHubMixModelProvider


@pytest.fixture
def dummy_tool() -> ToolSchema:
    return ToolSchema(
        name="query_records",
        description="Query database records",
        parameters={
            "type": "object",
            "properties": {"table": {"type": "string"}},
            "required": ["table"],
        },
        version="1.0.0",
        risk_level="READ_ONLY",
    )


def test_aihubmix_parses_single_tool_call(dummy_tool: ToolSchema) -> None:
    """Ensure valid single tool call parses into ToolCall with simulated=False."""
    provider = AIHubMixModelProvider(api_key="mock_key")
    fake_response = {
        "id": "chatcmpl-123",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_abc123",
                            "type": "function",
                            "function": {
                                "name": "query_records",
                                "arguments": '{"table": "orders"}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 50, "completion_tokens": 15},
    }

    with patch.object(provider, "_send_http_request", return_value=fake_response):
        messages = [Message(role="user", content={"target": "orders"})]
        config = ModelConfig(provider="aihubmix", model="coding-kimi-k3-free")
        response = asyncio.run(provider.generate(messages, [dummy_tool], config))

        assert isinstance(response.action, ToolCall)
        assert response.action.call_id == "call_abc123"
        assert response.action.name == "query_records"
        assert response.action.arguments == {"table": "orders"}
        assert response.token_usage.prompt_tokens == 50
        assert response.token_usage.completion_tokens == 15
        assert response.token_usage.simulated is False
        assert response.estimated_cost.is_known is False
        assert response.estimated_cost.price_table_version == "aihubmix-free-unverified"


def test_aihubmix_parses_final_answer() -> None:
    """Ensure message without tool_calls parses into FinalAnswer."""
    provider = AIHubMixModelProvider(api_key="mock_key")
    fake_response = {
        "id": "chatcmpl-456",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Order ORD-001 has been delivered.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 30, "completion_tokens": 10},
    }

    with patch.object(provider, "_send_http_request", return_value=fake_response):
        messages = [Message(role="user", content="status")]
        config = ModelConfig(provider="aihubmix", model="coding-kimi-k3-free")
        response = asyncio.run(provider.generate(messages, [], config))

        assert isinstance(response.action, FinalAnswer)
        assert response.action.text == "Order ORD-001 has been delivered."
        assert response.token_usage.simulated is False


def test_aihubmix_rejects_multiple_tool_calls(dummy_tool: ToolSchema) -> None:
    """M1 contract strictly accepts exactly one tool call proposal."""
    provider = AIHubMixModelProvider(api_key="mock_key")
    fake_response = {
        "id": "chatcmpl-789",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {"id": "call_1", "function": {"name": "f1", "arguments": "{}"}},
                        {"id": "call_2", "function": {"name": "f2", "arguments": "{}"}},
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10},
    }

    with patch.object(provider, "_send_http_request", return_value=fake_response):
        messages = [Message(role="user", content="hi")]
        config = ModelConfig(provider="aihubmix", model="coding-kimi-k3-free")
        with pytest.raises(ModelProviderError, match="MULTIPLE_TOOL_CALLS"):
            asyncio.run(provider.generate(messages, [dummy_tool], config))


def test_aihubmix_rejects_malformed_json_args_without_leak(dummy_tool: ToolSchema) -> None:
    """Ensure malformed JSON arguments trigger clear error without leaking raw arguments."""
    provider = AIHubMixModelProvider(api_key="mock_key")
    secret_payload = "super_secret_internal_data_12345"
    fake_response = {
        "id": "chatcmpl-bad",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_bad",
                            "function": {
                                "name": "query_records",
                                "arguments": f"{{malformed_json: {secret_payload}",
                            },
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10},
    }

    with patch.object(provider, "_send_http_request", return_value=fake_response):
        messages = [Message(role="user", content="hi")]
        config = ModelConfig(provider="aihubmix", model="coding-kimi-k3-free")
        with pytest.raises(ModelProviderError) as exc_info:
            asyncio.run(provider.generate(messages, [dummy_tool], config))
        assert "INVALID_TOOL_ARGUMENTS" in str(exc_info.value)
        assert secret_payload not in str(exc_info.value)


def test_aihubmix_rejects_missing_or_invalid_usage(dummy_tool: ToolSchema) -> None:
    """Ensure response lacking token usage is rejected rather than falsely reporting 0 tokens."""
    provider = AIHubMixModelProvider(api_key="mock_key")
    fake_response_no_usage = {
        "id": "chatcmpl-nousage",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "hello"},
            }
        ],
    }

    with patch.object(provider, "_send_http_request", return_value=fake_response_no_usage):
        messages = [Message(role="user", content="hi")]
        config = ModelConfig(provider="aihubmix", model="coding-kimi-k3-free")
        with pytest.raises(ModelProviderError, match="MISSING_TOKEN_USAGE"):
            asyncio.run(provider.generate(messages, [dummy_tool], config))

    fake_response_invalid_usage = {
        "id": "chatcmpl-invusage",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "hello"},
            }
        ],
        "usage": {"prompt_tokens": "invalid_string"},
    }

    with patch.object(provider, "_send_http_request", return_value=fake_response_invalid_usage):
        messages = [Message(role="user", content="hi")]
        config = ModelConfig(provider="aihubmix", model="coding-kimi-k3-free")
        with pytest.raises(ModelProviderError, match="INVALID_TOKEN_USAGE"):
            asyncio.run(provider.generate(messages, [dummy_tool], config))


def test_aihubmix_http_errors_are_sanitized() -> None:
    """Ensure HTTP errors raise sanitized fixed error codes without secret or body leaks."""
    provider = AIHubMixModelProvider(api_key="secret_test_key_12345")
    secret_body = b'{"error": "sensitive internal trace with secret_test_key_12345"}'

    # Mock HTTP 401
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://aihubmix.com/v1/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs=MagicMock(),
            fp=io.BytesIO(secret_body),
        )
        with pytest.raises(RuntimeError) as exc_info:
            provider._send_http_request({}, "secret_test_key_12345")
        assert "AUTHENTICATION_FAILED" in str(exc_info.value)
        assert "secret_test_key_12345" not in str(exc_info.value)

    # Mock HTTP 429
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://aihubmix.com/v1/chat/completions",
            code=429,
            msg="Too Many Requests",
            hdrs=MagicMock(),
            fp=io.BytesIO(secret_body),
        )
        with pytest.raises(RuntimeError) as exc_info:
            provider._send_http_request({}, "secret_test_key_12345")
        assert "RATE_LIMIT_EXCEEDED" in str(exc_info.value)
        assert "secret_test_key_12345" not in str(exc_info.value)

    # Mock HTTP 400 with upstream channel down
    channel_down_body = b'{"error": {"code": "no_available_channel", "message": "channel down"}}'
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://aihubmix.com/v1/chat/completions",
            code=400,
            msg="Bad Request",
            hdrs=MagicMock(),
            fp=io.BytesIO(channel_down_body),
        )
        with pytest.raises(RuntimeError) as exc_info:
            provider._send_http_request({}, "secret_test_key_12345")
        assert "UPSTREAM_CHANNEL_UNAVAILABLE" in str(exc_info.value)
        assert "channel down" not in str(exc_info.value)

    # Mock HTTP 502
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://aihubmix.com/v1/chat/completions",
            code=502,
            msg="Bad Gateway",
            hdrs=MagicMock(),
            fp=io.BytesIO(secret_body),
        )
        with pytest.raises(RuntimeError) as exc_info:
            provider._send_http_request({}, "secret_test_key_12345")
        assert "UPSTREAM_GATEWAY_ERROR" in str(exc_info.value)
        assert "sensitive" not in str(exc_info.value)


def test_missing_api_key_raises() -> None:
    """Ensure missing or placeholder key raises descriptive error."""
    provider = AIHubMixModelProvider(api_key="")
    with patch("os.environ.get", return_value=""):
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(RuntimeError, match="AIHUBMIX_API_KEY is not configured"):
                provider._resolve_key()


def test_schema_refs_are_expanded_without_coercing_arguments() -> None:
    """Expose object types directly while keeping strict local validation."""
    from packages.environments.tool_lab.environment import QueryRecordsArgs
    from packages.providers.aihubmix import inline_schema_refs

    source = QueryRecordsArgs.model_json_schema()
    expanded = inline_schema_refs(source)
    assert expanded["properties"]["filters"]["type"] == "object"
    assert "$defs" not in expanded
    assert "$defs" in source
    with pytest.raises(ValueError):
        QueryRecordsArgs.model_validate({"table": "orders", "filters": '{"order_id":"x"}'})


@pytest.mark.parametrize(
    "status,code,expected",
    [
        (404, "model_retired", "MODEL_RETIRED"),
        (503, "no_available_channel", "UPSTREAM_CHANNEL_UNAVAILABLE"),
        (404, "anything", "MODEL_NOT_FOUND"),
    ],
)
def test_upstream_code_classification(status: int, code: str, expected: str) -> None:
    """Known codes survive HTTP wrapping without copying private messages."""
    import json

    body = json.dumps({"error": {"code": code, "message": "secret"}}).encode()
    error = urllib.error.HTTPError(
        "https://example.test", status, "error", MagicMock(), io.BytesIO(body)
    )
    with patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(ModelProviderError) as caught:
            AIHubMixModelProvider()._send_http_request({}, "test-key")
    assert caught.value.code == expected
    assert "secret" not in str(caught.value)


def test_request_pacing_reserves_start_times() -> None:
    """Local requests reserve separate slots, without retrying upstream failures."""
    from packages.providers import aihubmix

    provider = AIHubMixModelProvider(min_request_interval=13)
    with (
        patch.object(aihubmix, "_next_request_at", 0),
        patch("packages.providers.aihubmix.time.monotonic", return_value=100),
        patch("packages.providers.aihubmix.time.sleep") as sleep,
        patch("urllib.request.urlopen", side_effect=urllib.error.URLError("private")),
    ):
        for _ in range(2):
            with pytest.raises(ModelProviderError):
                provider._send_http_request({}, "test-key")
        assert [call.args[0] for call in sleep.call_args_list] == [0, 13]

"""Unit tests for AIHubMixModelProvider with mocked HTTP responses."""

import asyncio
import errno
import http.client
import io
import socket
import ssl
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from packages.domain.models import FinalAnswer, Message, ModelConfig, ToolCall, ToolSchema
from packages.domain.ports import ModelProviderError
from packages.providers.aihubmix import AIHubMixModelProvider, list_available_model_ids


@pytest.mark.parametrize("operation", ["catalog", "completion"])
@pytest.mark.parametrize(
    "error,category,code,reading",
    [
        (
            urllib.error.URLError(socket.gaierror(1, "private")),
            "DNS_LOOKUP_FAILED",
            "NETWORK_CONNECTION_FAILED",
            False,
        ),
        (
            urllib.error.URLError(ssl.SSLCertVerificationError(1, "private")),
            "TLS_CERTIFICATE_ERROR",
            "NETWORK_CONNECTION_FAILED",
            False,
        ),
        (
            urllib.error.URLError(ssl.SSLError(1, "private")),
            "TLS_ERROR",
            "NETWORK_CONNECTION_FAILED",
            False,
        ),
        (
            urllib.error.URLError(TimeoutError("private")),
            "REQUEST_TIMEOUT",
            "REQUEST_TIMEOUT",
            False,
        ),
        (TimeoutError("private"), "REQUEST_TIMEOUT", "REQUEST_TIMEOUT", True),
        (
            urllib.error.URLError(ConnectionRefusedError("private")),
            "CONNECTION_REFUSED",
            "NETWORK_CONNECTION_FAILED",
            False,
        ),
        (
            urllib.error.URLError(OSError(errno.ENETUNREACH, "private")),
            "NETWORK_UNREACHABLE",
            "NETWORK_CONNECTION_FAILED",
            False,
        ),
        (
            ConnectionResetError("private"),
            "CONNECTION_INTERRUPTED",
            "NETWORK_CONNECTION_FAILED",
            True,
        ),
        (
            http.client.IncompleteRead(b"private", 8),
            "CONNECTION_INTERRUPTED",
            "NETWORK_CONNECTION_FAILED",
            True,
        ),
        (
            http.client.BadStatusLine("private"),
            "HTTP_PROTOCOL_ERROR",
            "NETWORK_CONNECTION_FAILED",
            True,
        ),
        (
            urllib.error.URLError("private https://user:secret@example.test/?key=secret"),
            "NETWORK_UNKNOWN",
            "NETWORK_CONNECTION_FAILED",
            False,
        ),
    ],
)
def test_network_failures_keep_safe_diagnostics_without_retry_or_fake_usage(
    operation: str,
    error: OSError | http.client.HTTPException,
    category: str,
    code: str,
    reading: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Both discovery and inference handle connection and response-read failures consistently."""
    with (
        patch("packages.providers.aihubmix.get_aihubmix_api_key", return_value="secret"),
        patch("urllib.request.urlopen") as opened,
    ):
        if reading:
            opened.return_value.__enter__.return_value.read.side_effect = error
        else:
            opened.side_effect = error
        with pytest.raises(ModelProviderError) as caught:
            if operation == "catalog":
                list_available_model_ids()
            else:
                AIHubMixModelProvider()._send_http_request({"messages": ["private"]}, "secret")
    assert str(caught.value) == code
    assert caught.value.token_usage is None
    assert caught.value.__suppress_context__
    assert opened.call_count == 1
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.__dict__["operation"] == operation
    assert record.__dict__["network_category"] == category
    assert record.exc_info is None
    assert "private" not in caplog.text and "secret" not in caplog.text


@pytest.mark.parametrize("split", [None, True])
def test_native_reasoning_split_keeps_legacy_requests_and_uses_content_only(
    split: bool | None,
) -> None:
    """Request native separation explicitly; hidden reasoning never becomes an answer."""
    provider = AIHubMixModelProvider(api_key="mock_key", reasoning_split=split)
    response = {
        "choices": [
            {
                "message": {
                    "content": '{"verdict":"pass"}',
                    "reasoning_content": "private fixture: never expose",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    with patch.object(provider, "_send_http_request", return_value=response) as send:
        result = asyncio.run(
            provider.generate(
                [Message(role="user", content="fixture")],
                [],
                ModelConfig(provider="aihubmix", model="coding-minimax-m2.7-free"),
            )
        )
    payload = send.call_args.args[0]
    assert ("reasoning_split" in payload) is (split is not None)
    if split is not None:
        assert payload["reasoning_split"] is True
    assert isinstance(result.action, FinalAnswer)
    assert result.action.text == '{"verdict":"pass"}'


def test_native_split_never_strips_an_unseparated_reply() -> None:
    """An upstream ignoring the option must still fail the Judge's strict JSON check."""
    provider = AIHubMixModelProvider(api_key="mock_key", reasoning_split=True)
    content = '<think>fixture</think>{"verdict":"pass"}'
    with patch.object(
        provider,
        "_send_http_request",
        return_value={
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    ):
        result = asyncio.run(
            provider.generate([], [], ModelConfig(provider="aihubmix", model="fixture"))
        )
    assert isinstance(result.action, FinalAnswer) and result.action.text == content


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

    with patch.object(provider, "_send_http_request", return_value=fake_response) as send:
        messages = [Message(role="user", content={"target": "orders"})]
        config = ModelConfig(provider="aihubmix", model="coding-kimi-k3-free")
        response = asyncio.run(provider.generate(messages, [dummy_tool], config))

        assert send.call_args.args[0]["parallel_tool_calls"] is False
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


def test_interrupted_http_error_body_preserves_known_status() -> None:
    """A truncated error body cannot hide the received gateway status or expose partial bytes."""
    body = MagicMock()
    body.read.side_effect = http.client.IncompleteRead(b"private secret", 8)
    error = urllib.error.HTTPError("https://example.test", 503, "private", MagicMock(), body)
    with patch("urllib.request.urlopen", side_effect=error) as opened:
        with pytest.raises(ModelProviderError) as caught:
            AIHubMixModelProvider()._send_http_request({}, "secret")
    assert str(caught.value) == "UPSTREAM_GATEWAY_ERROR"
    assert caught.value.token_usage is None
    assert opened.call_count == 1


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

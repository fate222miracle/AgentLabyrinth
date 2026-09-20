"""AIHubMix ModelProvider implementation for M1 real model execution.

Supports OpenAI-compatible Chat Completions via standard library HTTP.
Ensures strict parameter validation, response mapping, and sanitized error reporting.
"""

import asyncio
import json
import os
import threading
import time
import urllib.error
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any

from packages.domain.models import (
    EstimatedCost,
    FinalAnswer,
    Message,
    ModelConfig,
    ModelResponse,
    TokenUsage,
    ToolCall,
    ToolSchema,
)
from packages.domain.ports import ModelProvider, ModelProviderError

DEFAULT_BASE_URL = "https://aihubmix.com/v1"
DEFAULT_MODEL = "coding-glm-5.3-free"

# ponytail: one local process/account; use an account-scoped limiter for multi-user deployment.
_request_lock = threading.Lock()
_next_request_at = 0.0


def get_aihubmix_api_key() -> str:
    """Safely retrieve AIHubMix API key from environment or project root .env.

    Returns the stripped API key string.
    Raises RuntimeError if key is missing or is still placeholder.
    """
    key = os.environ.get("AIHUBMIX_API_KEY", "").strip()
    if key and key != "your_api_key_here":
        return key

    # Fallback to reading project root .env
    root_dir = Path(__file__).resolve().parents[2]
    env_path = root_dir / ".env"
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() == "AIHUBMIX_API_KEY":
                        val = v.strip().strip("'\"")
                        if val and val != "your_api_key_here":
                            return val
        except Exception:
            pass

    raise RuntimeError(
        "AIHUBMIX_API_KEY is not configured. Please set the environment variable or configure .env"
    )


def inline_schema_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Expand local nonrecursive definitions without coercing model arguments."""

    def expand(value: Any, seen: tuple[str, ...] = ()) -> Any:
        if isinstance(value, list):
            return [expand(item, seen) for item in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            ref = value["$ref"]
            if not isinstance(ref, str) or not ref.startswith("#/$defs/") or ref in seen:
                raise ModelProviderError("INVALID_MODEL_RESPONSE")
            name = ref.removeprefix("#/$defs/")
            target = schema.get("$defs", {}).get(name)
            if not isinstance(target, dict):
                raise ModelProviderError("INVALID_MODEL_RESPONSE")
            return expand(
                {**target, **{k: v for k, v in value.items() if k != "$ref"}}, (*seen, ref)
            )
        return {k: expand(v, seen) for k, v in value.items() if k != "$defs"}

    result: dict[str, Any] = expand(schema)
    return result


class AIHubMixModelProvider(ModelProvider):
    """OpenAI-compatible Chat Completions provider for AIHubMix models."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        min_request_interval: float = 0.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._min_request_interval = min_request_interval

    def _resolve_key(self) -> str:
        """Resolve API key on demand without persisting in logs or public fields."""
        if self._api_key and self._api_key != "your_api_key_here":
            return self._api_key
        return get_aihubmix_api_key()

    def _format_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Format domain Message list into OpenAI Chat Completions message dicts."""
        formatted: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "tool":
                formatted.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id or "call_default",
                        "content": json.dumps(msg.content)
                        if not isinstance(msg.content, str)
                        else msg.content,
                    }
                )
            elif msg.role == "assistant":
                item: dict[str, Any] = {"role": "assistant"}
                if msg.tool_calls:
                    item["content"] = msg.content if isinstance(msg.content, str) else None
                    item["tool_calls"] = [
                        {
                            "id": tc.call_id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments)
                                if not isinstance(tc.arguments, str)
                                else tc.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                else:
                    item["content"] = (
                        json.dumps(msg.content)
                        if not isinstance(msg.content, str) and msg.content is not None
                        else (msg.content or "")
                    )
                formatted.append(item)
            else:
                formatted.append(
                    {
                        "role": msg.role,
                        "content": json.dumps(msg.content)
                        if not isinstance(msg.content, str)
                        else msg.content,
                    }
                )
        return formatted

    def _format_tools(self, tools: list[ToolSchema]) -> list[dict[str, Any]]:
        """Format domain ToolSchema list into OpenAI tools schema."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": inline_schema_refs(t.parameters),
                },
            }
            for t in tools
        ]

    def _send_http_request(self, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
        """Execute synchronous HTTP POST request with sanitized error handling."""
        global _next_request_at
        if self._min_request_interval > 0:
            with _request_lock:
                scheduled = max(time.monotonic(), _next_request_at)
                _next_request_at = scheduled + self._min_request_interval
            time.sleep(max(0.0, scheduled - time.monotonic()))
        url = f"{self._base_url}/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "AgentLabyrinth-M1/0.1",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                resp_bytes = resp.read()
                return json.loads(resp_bytes.decode("utf-8"))  # type: ignore[no-any-return]
        except urllib.error.HTTPError as err:
            upstream_code = None
            try:
                body = json.loads(err.read(65536))
                error = body.get("error", {})
                if isinstance(error, dict):
                    upstream_code = error.get("code")
            except (ValueError, AttributeError, OSError):
                pass
            # Inspect only known codes, including when upstream wraps them in 5xx.
            if err.code == 401:
                code = "AUTHENTICATION_FAILED"
            elif err.code == 429:
                code = "RATE_LIMIT_EXCEEDED"
            elif upstream_code == "no_available_channel":
                code = "UPSTREAM_CHANNEL_UNAVAILABLE"
            elif upstream_code == "model_retired":
                code = "MODEL_RETIRED"
            elif err.code == 404:
                code = "MODEL_NOT_FOUND"
            elif err.code >= 500:
                code = "UPSTREAM_GATEWAY_ERROR"
            else:
                code = "CLIENT_REQUEST_FAILED"
            raise ModelProviderError(code) from None
        except urllib.error.URLError:
            raise ModelProviderError("NETWORK_CONNECTION_FAILED") from None
        except TimeoutError:
            raise ModelProviderError("REQUEST_TIMEOUT") from None
        except (ValueError, UnicodeError):
            raise ModelProviderError("INVALID_MODEL_RESPONSE") from None

    async def generate(
        self, messages: list[Message], tools: list[ToolSchema], config: ModelConfig
    ) -> ModelResponse:
        """Request Chat Completions from AIHubMix and map response to ModelResponse."""
        try:
            api_key = self._resolve_key()
        except RuntimeError:
            raise ModelProviderError("AUTHENTICATION_FAILED") from None
        model_id = (
            config.model if config.model and config.model != "fake-orders-v1" else DEFAULT_MODEL
        )

        payload: dict[str, Any] = {
            "model": model_id,
            "messages": self._format_messages(messages),
            "temperature": config.temperature,
        }
        if config.max_tokens is not None:
            payload["max_tokens"] = config.max_tokens

        if tools:
            payload["tools"] = self._format_tools(tools)
            payload["tool_choice"] = "auto"

        response_data = await asyncio.to_thread(self._send_http_request, payload, api_key)

        choices = response_data.get("choices")
        if not choices or not isinstance(choices, list):
            raise ModelProviderError("EMPTY_MODEL_CHOICES")

        if choices[0].get("finish_reason") == "length":
            raise ModelProviderError("OUTPUT_TRUNCATED")
        choice_msg = choices[0].get("message", {})
        tool_calls = choice_msg.get("tool_calls")

        action: ToolCall | FinalAnswer
        if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
            if len(tool_calls) > 1:
                raise ModelProviderError("MULTIPLE_TOOL_CALLS")
            tc = tool_calls[0]
            call_id = tc.get("id") or "call_unknown"
            func = tc.get("function", {})
            name = func.get("name", "")
            raw_args = func.get("arguments", "{}")

            if isinstance(raw_args, str):
                try:
                    parsed_args = json.loads(raw_args)
                except json.JSONDecodeError:
                    raise ModelProviderError("INVALID_TOOL_ARGUMENTS") from None
            elif isinstance(raw_args, dict):
                parsed_args = raw_args
            else:
                raise ModelProviderError("MALFORMED_TOOL_ARGUMENTS")

            if not isinstance(parsed_args, dict) or not isinstance(name, str) or not name:
                raise ModelProviderError("MALFORMED_TOOL_ARGUMENTS")
            action = ToolCall(call_id=call_id, name=name, arguments=parsed_args)
        else:
            content = choice_msg.get("content") or ""
            action = FinalAnswer(text=content)

        usage_data = response_data.get("usage")
        if not isinstance(usage_data, dict):
            raise ModelProviderError("MISSING_TOKEN_USAGE")

        prompt_tokens = usage_data.get("prompt_tokens")
        completion_tokens = usage_data.get("completion_tokens")
        if not isinstance(prompt_tokens, int) or not isinstance(completion_tokens, int):
            raise ModelProviderError("INVALID_TOKEN_USAGE")

        token_usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            simulated=False,
        )

        # Cost tracking for AIHubMix free models (unverified free tier)
        estimated_cost = EstimatedCost(
            amount=Decimal("0"),
            currency="USD",
            price_table_version="aihubmix-free-unverified",
            estimated=True,
            is_known=False,
        )

        return ModelResponse(
            action=action,
            token_usage=token_usage,
            estimated_cost=estimated_cost,
        )

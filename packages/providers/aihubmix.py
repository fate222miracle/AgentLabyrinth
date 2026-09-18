"""AIHubMix ModelProvider implementation for M1 real model execution.

Supports OpenAI-compatible Chat Completions via standard library HTTP.
Ensures strict parameter validation, response mapping, and sanitized error reporting.
"""

import asyncio
import json
import os
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
from packages.domain.ports import ModelProvider

DEFAULT_BASE_URL = "https://aihubmix.com/v1"
DEFAULT_MODEL = "coding-kimi-k3-free"


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


class AIHubMixModelProvider(ModelProvider):
    """OpenAI-compatible Chat Completions provider for AIHubMix models."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

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
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    def _send_http_request(self, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
        """Execute synchronous HTTP POST request with sanitized error handling."""
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
            if err.code == 401:
                raise RuntimeError("AIHubMix error: AUTHENTICATION_FAILED") from None
            if err.code == 429:
                raise RuntimeError("AIHubMix error: RATE_LIMIT_EXCEEDED") from None
            if 500 <= err.code < 600:
                raise RuntimeError(f"AIHubMix error: GATEWAY_ERROR_{err.code}") from None
            err_body = ""
            try:
                err_body = err.read().decode("utf-8")
            except Exception:
                pass
            if "no_available_channel" in err_body:
                raise RuntimeError(
                    "AIHubMix error: UPSTREAM_CHANNEL_UNAVAILABLE "
                    "(upstream model cannot be served at the moment)"
                ) from None
            raise RuntimeError(f"AIHubMix error: CLIENT_REQUEST_FAILED_{err.code}") from None
        except urllib.error.URLError:
            raise RuntimeError("AIHubMix error: NETWORK_CONNECTION_FAILED") from None
        except TimeoutError:
            raise RuntimeError("AIHubMix error: REQUEST_TIMEOUT") from None

    async def generate(
        self, messages: list[Message], tools: list[ToolSchema], config: ModelConfig
    ) -> ModelResponse:
        """Request Chat Completions from AIHubMix and map response to ModelResponse."""
        api_key = self._resolve_key()
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
            raise ValueError("AIHubMix error: EMPTY_MODEL_CHOICES")

        choice_msg = choices[0].get("message", {})
        tool_calls = choice_msg.get("tool_calls")

        action: ToolCall | FinalAnswer
        if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
            if len(tool_calls) > 1:
                raise ValueError(
                    "AIHubMix error: MULTIPLE_TOOL_CALLS (M1 supports exactly one tool call)"
                )
            tc = tool_calls[0]
            call_id = tc.get("id") or "call_unknown"
            func = tc.get("function", {})
            name = func.get("name", "")
            raw_args = func.get("arguments", "{}")

            if isinstance(raw_args, str):
                try:
                    parsed_args = json.loads(raw_args)
                except json.JSONDecodeError:
                    raise ValueError(
                        "AIHubMix error: INVALID_TOOL_ARGUMENTS (unparseable JSON)"
                    ) from None
            elif isinstance(raw_args, dict):
                parsed_args = raw_args
            else:
                raise ValueError("AIHubMix error: MALFORMED_TOOL_ARGUMENTS (unexpected type)")

            action = ToolCall(call_id=call_id, name=name, arguments=parsed_args)
        else:
            content = choice_msg.get("content") or ""
            action = FinalAnswer(text=content)

        usage_data = response_data.get("usage")
        if not isinstance(usage_data, dict):
            raise ValueError("AIHubMix error: MISSING_TOKEN_USAGE (response missing usage report)")

        prompt_tokens = usage_data.get("prompt_tokens")
        completion_tokens = usage_data.get("completion_tokens")
        if not isinstance(prompt_tokens, int) or not isinstance(completion_tokens, int):
            raise ValueError("AIHubMix error: INVALID_TOKEN_USAGE (usage counters not integers)")

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

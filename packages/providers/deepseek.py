"""Direct DeepSeek Chat Completions with native tools."""

import os
from typing import Any

from packages.providers.aihubmix import AIHubMixModelProvider

DEEPSEEK_MODEL = "deepseek-flash"


class DeepSeekModelProvider(AIHubMixModelProvider):
    provider_name = "deepseek"
    unknown_price_version = "deepseek-official-unverified"

    def __init__(
        self,
        *,
        required_tool: bool = False,
        compact_message_json: bool = False,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(
            base_url="https://api.deepseek.com",
            timeout=timeout,
            compact_message_json=compact_message_json,
        )
        self._required_tool = required_tool

    def _resolve_key(self) -> str:
        key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not key:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")
        return key

    def _send_http_request(self, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
        request = {**payload, "thinking": {"type": "disabled"}}
        request.pop("parallel_tool_calls", None)
        if self._required_tool and request.get("tools"):
            request["tool_choice"] = "required"
        return super()._send_http_request(request, api_key)

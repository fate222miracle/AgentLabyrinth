"""Run the local API with delayed Fake calls to demonstrate Job controls."""

import argparse
import asyncio
from unittest.mock import patch

import uvicorn

from apps.api.main import app
from packages.domain.models import Message, ModelConfig, ModelResponse, ToolSchema
from packages.providers.fake import FakeModelProvider


def main() -> None:
    """Serve the normal API with a temporary delay on Fake model calls."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delay-seconds", type=float, default=0.5)
    args = parser.parse_args()
    if not 0 < args.delay_seconds <= 5:
        parser.error("--delay-seconds must be greater than 0 and at most 5")

    original_generate = FakeModelProvider.generate

    async def delayed_generate(
        self: FakeModelProvider,
        messages: list[Message],
        tools: list[ToolSchema],
        config: ModelConfig,
    ) -> ModelResponse:
        """Delay only Fake calls; all API routes use their original implementation."""
        await asyncio.sleep(args.delay_seconds)
        return await original_generate(self, messages, tools, config)

    with patch.object(FakeModelProvider, "generate", delayed_generate):
        uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()

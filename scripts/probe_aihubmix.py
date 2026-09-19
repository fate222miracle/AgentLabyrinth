"""Minimal verification probe for AIHubMix real model connectivity and tool calling.

Performs:
1. Small plain chat completion to verify authentication and gateway connectivity.
2. Harmless tool schema request to verify native function/tool calling, arguments JSON parsing,
   and usage reporting.

Outputs a sanitized summary. Does NOT log or reveal the API key.
"""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.domain.models import (  # noqa: E402
    FinalAnswer,
    Message,
    ModelConfig,
    ToolCall,
    ToolSchema,
)
from packages.providers.aihubmix import AIHubMixModelProvider, get_aihubmix_api_key  # noqa: E402


async def run_probe() -> int:
    """Run step 1 (auth) and step 2 (tool call) probes."""
    print("=== AIHubMix Probe Starting ===")

    # 0. Check API Key presence
    try:
        get_aihubmix_api_key()
        print("[OK] API key configured")
    except Exception as exc:
        print(f"[FAIL] Key configuration error: {exc}", file=sys.stderr)
        return 1

    provider = AIHubMixModelProvider(timeout=20.0)
    model_name = sys.argv[1] if len(sys.argv) > 1 else "gemini-3.7-flash-free"
    config = ModelConfig(
        provider="aihubmix",
        model=model_name,
        temperature=0.0,
        max_tokens=100,
    )
    print(f"Testing model: {model_name}")

    # Step 1: Plain chat probe
    print("\n--- Step 1: Plain Chat Probe (Auth & Gateway) ---")
    try:
        messages = [
            Message(role="system", content="You are a minimal test assistant."),
            Message(role="user", content="Respond with exactly 'PONG' and nothing else."),
        ]
        resp1 = await provider.generate(messages=messages, tools=[], config=config)
        if isinstance(resp1.action, FinalAnswer):
            reply_text = resp1.action.text.strip().replace("\n", " ")
            print(f"[OK] Step 1 Success: received response: '{reply_text}'")
            print(
                f"     Usage: prompt={resp1.token_usage.prompt_tokens}, "
                f"completion={resp1.token_usage.completion_tokens}, "
                f"simulated={resp1.token_usage.simulated}"
            )
        else:
            print(f"[WARN] Unexpected action in plain chat: {resp1.action.kind}")
    except Exception as exc:
        print(f"[FAIL] Step 1 Failed: {exc}", file=sys.stderr)
        return 1

    # Step 2: Native tool calling probe
    print("\n--- Step 2: Tool Call Probe (Native Function Calling) ---")
    tool = ToolSchema(
        name="query_order",
        description="Query order record by order identifier",
        parameters={
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Order ID to look up, e.g. ORD-001",
                }
            },
            "required": ["order_id"],
            "additionalProperties": False,
        },
        version="1.0.0",
        risk_level="READ_ONLY",
    )

    try:
        tool_messages = [
            Message(
                role="system",
                content=(
                    "You are an order assistant. "
                    "You MUST call the query_order tool to look up orders."
                ),
            ),
            Message(
                role="user",
                content="What is the status of order ORD-001? Call query_order now.",
            ),
        ]
        resp2 = await provider.generate(messages=tool_messages, tools=[tool], config=config)

        if isinstance(resp2.action, ToolCall):
            tc = resp2.action
            print("[OK] Step 2 Success: native tool call received!")
            print(f"     Call ID:   {tc.call_id}")
            print(f"     Tool Name: {tc.name}")
            print(f"     Arguments: {json.dumps(tc.arguments, ensure_ascii=False)}")
            print(
                f"     Usage:     prompt={resp2.token_usage.prompt_tokens}, "
                f"completion={resp2.token_usage.completion_tokens}, "
                f"simulated={resp2.token_usage.simulated}"
            )
            if tc.name != "query_order":
                print(f"[WARN] Tool name mismatch: expected 'query_order', got '{tc.name}'")
            if not isinstance(tc.arguments, dict) or "order_id" not in tc.arguments:
                print("[WARN] Tool arguments missing expected 'order_id' key")
        else:
            print(
                "[FAIL] Step 2 Failed: Model returned plain text instead of native tool call!",
                file=sys.stderr,
            )
            if isinstance(resp2.action, FinalAnswer):
                print(f"       Raw text: {resp2.action.text[:200]}...", file=sys.stderr)
            return 1

    except Exception as exc:
        print(f"[FAIL] Step 2 Failed: {exc}", file=sys.stderr)
        return 1

    print("\n=== AIHubMix Probe Finished Successfully ===")
    return 0


def main() -> int:
    return asyncio.run(run_probe())


if __name__ == "__main__":
    sys.exit(main())

"""Simple test for weather agent MCP tools."""

import sys
from pathlib import Path

import anyio
import pytest

pytestmark = [pytest.mark.usability, pytest.mark.slow]

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, create_sdk_mcp_server

from tools.weather_tools import get_locations, get_weather

# Track tool calls
tool_calls = []


async def main():
    print("=" * 60)
    print("Testing Weather Agent MCP Tools")
    print("=" * 60)

    # Create SDK MCP server with weather tools
    weather_server = create_sdk_mcp_server(
        name="weather_agent", version="1.0.0", tools=[get_weather, get_locations]
    )

    # Configure Claude with the weather server
    options = ClaudeAgentOptions(
        mcp_servers={"weather_agent": weather_server},
        allowed_tools=[
            "mcp__weather_agent__get_weather",
            "mcp__weather_agent__get_locations",
        ],
        max_turns=5,
    )

    # Test 1: Get locations
    print("\n" + "=" * 60)
    print("TEST 1: Get available locations")
    print("=" * 60)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(
            "What weather locations are available? Use the get_locations tool."
        )

        async for msg in client.receive_response():
            if hasattr(msg, "content"):
                for block in msg.content:
                    if hasattr(block, "text"):
                        print(f"\nClaude's response: {block.text}")
                    if hasattr(block, "name"):
                        print(f"\n✓ Tool called: {block.name}")
                        print(f"  Input: {block.input}")

    # Test 2: Get weather for Tokyo
    print("\n" + "=" * 60)
    print("TEST 2: Get weather for Tokyo")
    print("=" * 60)

    async with ClaudeSDKClient(options=options) as client:
        await client.query("What's the weather in Tokyo? Use the get_weather tool.")

        response_text = None
        tool_result = None

        async for msg in client.receive_response():
            if hasattr(msg, "content"):
                for block in msg.content:
                    if hasattr(block, "text"):
                        response_text = block.text
                        print(f"\nClaude's response: {block.text}")
                    if hasattr(block, "name"):
                        print(f"\n✓ Tool called: {block.name}")
                        print(f"  Input: {block.input}")
                    # Capture tool results
                    if hasattr(block, "tool_use_id") and hasattr(block, "content"):
                        tool_result = block.content
                        print("\n✓ Tool result received:")
                        for content_item in block.content:
                            if (
                                isinstance(content_item, dict)
                                and content_item.get("type") == "text"
                            ):
                                print(f"  {content_item.get('text')}")

        # Verify the tool was actually called and result used
        print("\n" + "=" * 60)
        print("VERIFICATION:")
        print("=" * 60)
        if tool_result:
            print("✅ Tool was executed and returned data")
            print("✅ Weather agent MCP tools are working correctly!")
        else:
            print("❌ No tool result detected")

        if (
            response_text
            and "22.5" in response_text
            or (tool_result and any("22.5" in str(item) for item in tool_result))
        ):
            print("✅ Response contains Tokyo temperature data (22.5°C)")
        else:
            print("⚠️  Tokyo temperature not found in response")


if __name__ == "__main__":
    anyio.run(main)

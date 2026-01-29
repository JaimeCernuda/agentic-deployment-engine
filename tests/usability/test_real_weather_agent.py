"""Test the real weather agent with HTTP requests."""
import asyncio
import sys
from pathlib import Path

import httpx
import pytest

pytestmark = [pytest.mark.usability, pytest.mark.slow]

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_weather_agent():
    """Test weather agent via HTTP API."""
    base_url = "http://localhost:9001"

    print("=" * 60)
    print("Testing Weather Agent via HTTP API")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Test 1: Health check
        print("\n1. Health Check")
        try:
            response = await client.get(f"{base_url}/health")
            print(f"✓ Health: {response.json()}")
        except Exception as e:
            print(f"✗ Health check failed: {e}")
            print("Make sure the weather agent is running:")
            print("  uv run weather-agent")
            return

        # Test 2: Agent configuration
        print("\n2. Agent Configuration")
        try:
            response = await client.get(f"{base_url}/.well-known/agent-configuration")
            config = response.json()
            print(f"✓ Name: {config['name']}")
            print(f"✓ Skills: {len(config['skills'])} skill(s)")
            for skill in config['skills']:
                print(f"  - {skill['name']}: {skill['description']}")
        except Exception as e:
            print(f"✗ Failed: {e}")

        # Test 3: Query - Get locations (should use MCP tool)
        print("\n3. Query: Get available locations")
        print("   Expected: Should call mcp__weather_agent__get_locations")
        try:
            response = await client.post(
                f"{base_url}/query",
                json={"query": "What weather locations are available?"}
            )
            result = response.json()
            print(f"✓ Response: {result['response']}")

            # Check if response contains actual cities from tool
            if "Tokyo" in result['response'] and "London" in result['response']:
                print("✅ VERIFIED: Response contains cities from MCP tool!")
            else:
                print("⚠️  WARNING: Response may not be from MCP tool")
        except Exception as e:
            print(f"✗ Failed: {e}")

        # Test 4: Query - Get weather for Tokyo (should use MCP tool)
        print("\n4. Query: Get weather for Tokyo")
        print("   Expected: Should call mcp__weather_agent__get_weather")
        try:
            response = await client.post(
                f"{base_url}/query",
                json={"query": "What's the weather in Tokyo?"}
            )
            result = response.json()
            print(f"✓ Response: {result['response']}")

            # Check if response contains actual weather data from tool
            if "22.5" in result['response'] or "Partly cloudy" in result['response']:
                print("✅ VERIFIED: Response contains exact weather data from MCP tool!")
                print("   (Tokyo mock data: 22.5°C, Partly cloudy)")
            else:
                print("⚠️  WARNING: Response may not be using MCP tool data")
                print("   Agent might be hallucinating or using Bash/code workarounds")
        except Exception as e:
            print(f"✗ Failed: {e}")

        # Test 5: Query - Get weather for London (verify tool is really called)
        print("\n5. Query: Get weather for London")
        print("   Expected: Should call mcp__weather_agent__get_weather")
        try:
            response = await client.post(
                f"{base_url}/query",
                json={"query": "What's the current weather in London?"}
            )
            result = response.json()
            print(f"✓ Response: {result['response']}")

            # Check for London-specific mock data
            if "15.2" in result['response'] or "Light rain" in result['response']:
                print("✅ VERIFIED: Response contains exact London weather from MCP tool!")
                print("   (London mock data: 15.2°C, Light rain)")
            else:
                print("⚠️  WARNING: Response may not be using MCP tool data")
        except Exception as e:
            print(f"✗ Failed: {e}")

    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)
    print("Check the agent logs at: logs/weather_agent.log")
    print("Look for log lines showing:")
    print("  - 'Tool: mcp__weather_agent__get_weather'")
    print("  - 'Tool: mcp__weather_agent__get_locations'")
    print("These confirm MCP tools are being called.")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_weather_agent())

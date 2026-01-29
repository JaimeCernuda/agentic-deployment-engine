#!/usr/bin/env python3
"""
Test the clean MCP + A2A system.
"""

import asyncio

import httpx
import pytest
pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_sdk_integration():
    """Test SDK MCP integration (agents should have working tools)."""
    print("Testing SDK MCP Integration...")
    print("Note: Tools are now integrated into agents via SDK MCP servers")
    print("Testing will be done through agent queries instead of direct MCP calls")


@pytest.mark.asyncio
async def test_a2a_agents():
    """Test A2A agents."""
    print("\nTesting A2A Agents...")

    async with httpx.AsyncClient() as client:
        agents = [
            ("Weather Agent", "http://localhost:9001"),
            ("Maps Agent", "http://localhost:9002"),
            ("Controller Agent", "http://localhost:9000")
        ]

        for name, url in agents:
            try:
                # Test agent discovery
                config_response = await client.get(f"{url}/.well-known/agent-configuration")
                if config_response.status_code == 200:
                    config = config_response.json()
                    print(f"✅ {name}: {config['description']}")
                    print(f"   Skills: {len(config.get('skills', []))} available")
                else:
                    print(f"❌ {name} discovery failed: {config_response.status_code}")

            except Exception as e:
                print(f"❌ {name} error: {e}")


@pytest.mark.asyncio
async def test_queries():
    """Test actual queries."""
    print("\nTesting Queries...")

    async with httpx.AsyncClient(timeout=120.0) as client:
        queries = [
            ("Weather Agent", "http://localhost:9001", "What's the weather in Tokyo?"),
            ("Maps Agent", "http://localhost:9002", "How far is Tokyo from London?"),
            ("Controller Agent", "http://localhost:9000", "What's the weather in Tokyo and how far is it from London?")
        ]

        for name, url, query in queries:
            try:
                response = await client.post(
                    f"{url}/query",
                    json={"query": query}
                )
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ {name}")
                    print(f"   Query: {query}")
                    print(f"   Response: {result.get('response', 'No response')[:100]}...")
                else:
                    print(f"❌ {name} query failed: {response.status_code}")

            except Exception as e:
                print(f"❌ {name} query error: {e}")


async def main():
    """Run all tests."""
    print("🚀 Testing Clean MCP + A2A System with SDK Integration")
    print("=" * 65)

    print("\nMake sure all agents are running:")
    print("- Weather Agent (port 9001): uv run weather-agent")
    print("- Maps Agent (port 9002): uv run maps-agent")
    print("- Controller Agent (port 9000): uv run controller-agent")
    print("\nNew Architecture:")
    print("- Agents use SDK MCP servers (in-process tools)")
    print("- Controller uses curl for A2A communication")
    print("- No standalone MCP servers needed")
    print()

    await test_sdk_integration()
    await test_a2a_agents()
    await test_queries()

    print("\n✨ Test Complete!")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Comprehensive Multi-Agent Demo
Demonstrates both MCP SDK tool usage and A2A protocol communication
"""

import asyncio

import httpx


async def main():
    print("=" * 70)
    print("MULTI-AGENT SYSTEM DEMO")
    print("=" * 70)
    print()
    print("This demo showcases:")
    print("1. MCP SDK tools (Weather & Maps agents)")
    print("2. A2A protocol (Controller coordinating both agents)")
    print()

    async with httpx.AsyncClient(timeout=180.0) as client:
        # Demo 1: Weather Agent using MCP SDK tools
        print("=" * 70)
        print("DEMO 1: Weather Agent - MCP SDK Tool Usage")
        print("=" * 70)
        print("Query: 'What's the weather in Tokyo?'")
        print("Expected: Agent calls mcp__weather_agent__get_weather tool")
        print()

        response = await client.post(
            "http://localhost:9001/query",
            json={"query": "What's the weather in Tokyo?"},
        )
        result = response.json()
        print(f"Response: {result['response']}\n")

        # Demo 2: Maps Agent using MCP SDK tools
        print("=" * 70)
        print("DEMO 2: Maps Agent - MCP SDK Tool Usage")
        print("=" * 70)
        print("Query: 'How far is Tokyo from London?'")
        print("Expected: Agent calls mcp__maps_agent__get_distance tool")
        print()

        response = await client.post(
            "http://localhost:9002/query",
            json={"query": "How far is Tokyo from London?"},
        )
        result = response.json()
        print(f"Response: {result['response']}\n")

        # Demo 3: Controller Agent using A2A protocol
        print("=" * 70)
        print("DEMO 3: Controller Agent - A2A Multi-Agent Coordination")
        print("=" * 70)
        print("Query: 'What's the weather in Paris and how far is it from New York?'")
        print("Expected: Controller uses curl to query both Weather and Maps agents")
        print()

        response = await client.post(
            "http://localhost:9000/query",
            json={
                "query": "What's the weather in Paris and how far is it from New York?"
            },
        )
        result = response.json()
        print(f"Response: {result['response']}\n")

        # Demo 4: Another multi-agent coordination
        print("=" * 70)
        print("DEMO 4: Controller Agent - Complex Multi-Agent Query")
        print("=" * 70)
        print("Query: 'Tell me about London's weather and its distance from Tokyo'")
        print("Expected: Controller coordinates Weather + Maps agents via A2A")
        print()

        response = await client.post(
            "http://localhost:9000/query",
            json={
                "query": "Tell me about London's weather and its distance from Tokyo"
            },
        )
        result = response.json()
        print(f"Response: {result['response']}\n")

    print("=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    print()
    print("Check the logs to verify:")
    print("  - Weather Agent: src/logs/weather_agent.log")
    print("    Look for: 'Tool: mcp__weather_agent__get_weather'")
    print()
    print("  - Maps Agent: src/logs/maps_agent.log")
    print("    Look for: 'Tool: mcp__maps_agent__get_distance'")
    print()
    print("  - Controller Agent: src/logs/controller_agent.log")
    print("    Look for: curl commands to localhost:9001 and localhost:9002")
    print()


if __name__ == "__main__":
    asyncio.run(main())

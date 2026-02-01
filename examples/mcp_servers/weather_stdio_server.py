"""Standalone Weather MCP Server (stdio transport).

This server runs as a subprocess and communicates via stdin/stdout.
Can be used to test external MCP server integration.

Usage:
    python -m examples.mcp_servers.weather_stdio_server
"""

import asyncio
import json
import sys
from datetime import datetime

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Simple mock weather data
WEATHER_DATA = {
    "tokyo": {
        "temperature": 22.5,
        "description": "Partly cloudy",
        "humidity": 65,
        "wind_speed": 12.3,
    },
    "london": {
        "temperature": 15.2,
        "description": "Light rain",
        "humidity": 78,
        "wind_speed": 8.7,
    },
    "new york": {
        "temperature": 18.8,
        "description": "Clear sky",
        "humidity": 55,
        "wind_speed": 15.2,
    },
    "paris": {
        "temperature": 16.9,
        "description": "Overcast",
        "humidity": 72,
        "wind_speed": 9.8,
    },
}

# Create MCP server
server = Server("weather-stdio")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available weather tools."""
    return [
        Tool(
            name="get_weather",
            description="Get current weather for a location",
            inputSchema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name (Tokyo, London, New York, Paris)",
                    },
                    "units": {
                        "type": "string",
                        "enum": ["metric", "imperial"],
                        "default": "metric",
                        "description": "Temperature units",
                    },
                },
                "required": ["location"],
            },
        ),
        Tool(
            name="get_locations",
            description="Get list of available weather locations",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    if name == "get_weather":
        location = arguments.get("location", "").lower().strip()
        units = arguments.get("units", "metric")

        if location not in WEATHER_DATA:
            return [
                TextContent(
                    type="text",
                    text=f"Weather data not found for '{arguments.get('location', 'unknown')}'. "
                    f"Available: {', '.join(loc.title() for loc in WEATHER_DATA.keys())}",
                )
            ]

        data = WEATHER_DATA[location].copy()

        # Convert temperature units
        temp = data["temperature"]
        if units == "imperial":
            temp = (temp * 9 / 5) + 32
            temp_unit = "°F"
            wind_unit = "mph"
        else:
            temp_unit = "°C"
            wind_unit = "km/h"

        return [
            TextContent(
                type="text",
                text=f"Weather in {arguments.get('location', location).title()}: "
                f"{temp:.1f}{temp_unit}, {data['description']}, "
                f"Humidity: {data['humidity']}%, Wind: {data['wind_speed']} {wind_unit}",
            )
        ]

    elif name == "get_locations":
        locations = [loc.title() for loc in WEATHER_DATA.keys()]
        return [
            TextContent(
                type="text",
                text=f"Available weather locations: {', '.join(locations)}",
            )
        ]

    else:
        return [
            TextContent(
                type="text",
                text=f"Unknown tool: {name}",
            )
        ]


async def main():
    """Run the stdio MCP server."""
    # Log to stderr so it doesn't interfere with MCP protocol on stdout
    print("Weather stdio MCP server starting...", file=sys.stderr)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

"""Weather MCP Tools - SDK-compatible implementation.

Provides weather tools for claude-code-sdk integration.
"""

from datetime import datetime
from typing import Dict, Any
from claude_agent_sdk import tool


# Simple mock data
WEATHER_DATA = {
    "tokyo": {"temperature": 22.5, "description": "Partly cloudy", "humidity": 65, "wind_speed": 12.3},
    "london": {"temperature": 15.2, "description": "Light rain", "humidity": 78, "wind_speed": 8.7},
    "new york": {"temperature": 18.8, "description": "Clear sky", "humidity": 55, "wind_speed": 15.2},
    "paris": {"temperature": 16.9, "description": "Overcast", "humidity": 72, "wind_speed": 9.8}
}


@tool("get_weather", "Get current weather information for a location", {"location": str, "units": str})
async def get_weather(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get weather data for a location."""
    location = args.get("location", "").lower().strip()
    units = args.get("units", "metric")

    if location not in WEATHER_DATA:
        return {
            "content": [{
                "type": "text",
                "text": f"Weather data not found for {args.get('location', 'unknown')}"
            }]
        }

    data = WEATHER_DATA[location].copy()

    # Convert temperature units
    if units == "imperial":
        data["temperature"] = (data["temperature"] * 9/5) + 32
    elif units == "kelvin":
        data["temperature"] = data["temperature"] + 273.15

    result = {
        "location": args.get("location", "").title(),
        "temperature": data["temperature"],
        "description": data["description"],
        "humidity": data["humidity"],
        "wind_speed": data["wind_speed"],
        "units": units,
        "timestamp": datetime.now().isoformat()
    }

    return {
        "content": [{
            "type": "text",
            "text": f"Weather in {result['location']}: {result['temperature']:.1f}°{'F' if units == 'imperial' else 'K' if units == 'kelvin' else 'C'}, {result['description']}, Humidity: {result['humidity']}%, Wind: {result['wind_speed']} {'mph' if units == 'imperial' else 'km/h'}"
        }]
    }


@tool("get_locations", "Get list of available weather locations", {})
async def get_locations(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get available weather locations."""
    locations = list(WEATHER_DATA.keys())
    return {
        "content": [{
            "type": "text",
            "text": f"Available weather locations: {', '.join(loc.title() for loc in locations)}"
        }]
    }
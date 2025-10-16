"""Maps MCP Tools - SDK-compatible implementation.

Provides maps/distance tools for claude-code-sdk integration.
"""

from typing import Dict, Any
from claude_agent_sdk import tool
import math


# Simple coordinate data for major cities
CITY_COORDINATES = {
    "tokyo": {"lat": 35.6762, "lon": 139.6503},
    "london": {"lat": 51.5074, "lon": -0.1278},
    "new york": {"lat": 40.7128, "lon": -74.0060},
    "paris": {"lat": 48.8566, "lon": 2.3522}
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points on Earth."""
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    # Radius of earth in kilometers
    r = 6371
    return c * r


@tool("get_distance", "Calculate distance between two locations", {"origin": str, "destination": str, "units": str})
async def get_distance(args: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate distance between two cities."""
    origin = args.get("origin", "").lower().strip()
    destination = args.get("destination", "").lower().strip()
    units = args.get("units", "km")

    if origin not in CITY_COORDINATES:
        return {
            "content": [{
                "type": "text",
                "text": f"Origin location '{args.get('origin', 'unknown')}' not found"
            }]
        }

    if destination not in CITY_COORDINATES:
        return {
            "content": [{
                "type": "text",
                "text": f"Destination location '{args.get('destination', 'unknown')}' not found"
            }]
        }

    origin_coords = CITY_COORDINATES[origin]
    dest_coords = CITY_COORDINATES[destination]

    distance_km = haversine_distance(
        origin_coords["lat"], origin_coords["lon"],
        dest_coords["lat"], dest_coords["lon"]
    )

    if units == "miles":
        distance = distance_km * 0.621371
        unit_str = "miles"
    else:
        distance = distance_km
        unit_str = "km"

    return {
        "content": [{
            "type": "text",
            "text": f"Distance from {args.get('origin', '').title()} to {args.get('destination', '').title()}: {distance:.1f} {unit_str}"
        }]
    }


@tool("get_cities", "Get list of available cities for distance calculations", {})
async def get_cities(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get available cities for distance calculations."""
    cities = list(CITY_COORDINATES.keys())
    return {
        "content": [{
            "type": "text",
            "text": f"Available cities: {', '.join(city.title() for city in cities)}"
        }]
    }
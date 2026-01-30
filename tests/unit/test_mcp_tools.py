#!/usr/bin/env python3
"""
Unit tests for individual components.
"""

import sys
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from examples.tools.maps_tools import CITY_COORDINATES, get_cities, get_distance
from examples.tools.weather_tools import WEATHER_DATA, get_locations, get_weather

# Extract handlers from SDK tools
get_weather_handler = get_weather.handler
get_locations_handler = get_locations.handler
get_distance_handler = get_distance.handler
get_cities_handler = get_cities.handler


class TestWeatherTools:
    """Test weather MCP tools."""

    @pytest.mark.asyncio
    async def test_get_weather_tokyo(self):
        """Test getting weather for Tokyo."""
        result = await get_weather_handler({"location": "Tokyo", "units": "metric"})

        assert "content" in result
        assert len(result["content"]) > 0
        assert result["content"][0]["type"] == "text"

        text = result["content"][0]["text"]
        assert "Tokyo" in text
        assert "22.5" in text or "°C" in text

    @pytest.mark.asyncio
    async def test_get_weather_invalid_location(self):
        """Test getting weather for invalid location."""
        result = await get_weather_handler(
            {"location": "InvalidCity", "units": "metric"}
        )

        assert "content" in result
        text = result["content"][0]["text"]
        assert "not found" in text.lower()

    @pytest.mark.asyncio
    async def test_get_weather_imperial(self):
        """Test weather with imperial units."""
        result = await get_weather_handler({"location": "London", "units": "imperial"})

        text = result["content"][0]["text"]
        assert "London" in text
        assert "°F" in text

    @pytest.mark.asyncio
    async def test_get_locations(self):
        """Test getting available locations."""
        result = await get_locations_handler({})

        assert "content" in result
        text = result["content"][0]["text"]

        # Check all cities are listed
        for city in WEATHER_DATA.keys():
            assert city.title() in text


class TestMapsTools:
    """Test maps MCP tools."""

    @pytest.mark.asyncio
    async def test_get_distance_tokyo_london(self):
        """Test distance calculation between Tokyo and London."""
        result = await get_distance_handler(
            {"origin": "Tokyo", "destination": "London", "units": "km"}
        )

        assert "content" in result
        text = result["content"][0]["text"]
        assert "Tokyo" in text
        assert "London" in text
        assert "km" in text

    @pytest.mark.asyncio
    async def test_get_distance_invalid_origin(self):
        """Test distance with invalid origin."""
        result = await get_distance_handler(
            {"origin": "InvalidCity", "destination": "London", "units": "km"}
        )

        text = result["content"][0]["text"]
        assert "not found" in text.lower()

    @pytest.mark.asyncio
    async def test_get_distance_miles(self):
        """Test distance calculation in miles."""
        result = await get_distance_handler(
            {"origin": "New York", "destination": "Paris", "units": "miles"}
        )

        text = result["content"][0]["text"]
        assert "miles" in text
        assert "New York" in text
        assert "Paris" in text

    @pytest.mark.asyncio
    async def test_get_cities(self):
        """Test getting available cities."""
        result = await get_cities_handler({})

        assert "content" in result
        text = result["content"][0]["text"]

        # Check all cities are listed
        for city in CITY_COORDINATES.keys():
            assert city.title() in text


class TestDataConsistency:
    """Test data consistency across tools."""

    def test_weather_cities_in_maps(self):
        """Verify weather cities are available in maps."""
        weather_cities = {city.lower() for city in WEATHER_DATA.keys()}
        maps_cities = {city.lower() for city in CITY_COORDINATES.keys()}

        # All weather cities should have coordinates
        assert weather_cities.issubset(maps_cities), (
            f"Weather cities missing coordinates: {weather_cities - maps_cities}"
        )

    def test_city_count(self):
        """Test that we have expected number of cities."""
        assert len(WEATHER_DATA) == 4
        assert len(CITY_COORDINATES) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

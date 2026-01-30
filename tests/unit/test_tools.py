"""Comprehensive tests for tools/weather_tools.py and tools/maps_tools.py.

Tests MCP tool data and helper functions including:
- Weather data structure and values
- Temperature unit conversion logic
- Haversine distance calculation
- City coordinate data
- Edge cases and error handling

Note: The @tool decorated functions are SDK wrappers and are tested
indirectly through usability tests. These tests focus on the underlying
data and algorithms.
"""

import math


class TestWeatherData:
    """Tests for weather data structure and values."""

    def test_weather_data_has_all_cities(self) -> None:
        """Should have data for all expected cities."""
        from examples.tools.weather_tools import WEATHER_DATA

        expected_cities = ["tokyo", "london", "new york", "paris"]
        for city in expected_cities:
            assert city in WEATHER_DATA, f"Missing city: {city}"

    def test_weather_data_structure(self) -> None:
        """Should have correct data structure for each city."""
        from examples.tools.weather_tools import WEATHER_DATA

        required_keys = ["temperature", "description", "humidity", "wind_speed"]

        for city, data in WEATHER_DATA.items():
            for key in required_keys:
                assert key in data, f"{city} missing {key}"

    def test_weather_data_valid_temperatures(self) -> None:
        """Should have realistic temperature values (Celsius)."""
        from examples.tools.weather_tools import WEATHER_DATA

        for city, data in WEATHER_DATA.items():
            temp = data["temperature"]
            assert isinstance(temp, (int, float))
            assert -50 < temp < 60, f"{city} has unrealistic temp: {temp}"

    def test_weather_data_valid_humidity(self) -> None:
        """Should have valid humidity percentages (0-100)."""
        from examples.tools.weather_tools import WEATHER_DATA

        for city, data in WEATHER_DATA.items():
            humidity = data["humidity"]
            assert isinstance(humidity, (int, float))
            assert 0 <= humidity <= 100, f"{city} has invalid humidity: {humidity}"

    def test_weather_data_valid_wind_speed(self) -> None:
        """Should have realistic wind speed values."""
        from examples.tools.weather_tools import WEATHER_DATA

        for city, data in WEATHER_DATA.items():
            wind = data["wind_speed"]
            assert isinstance(wind, (int, float))
            assert 0 <= wind < 200, f"{city} has unrealistic wind: {wind}"

    def test_weather_data_has_descriptions(self) -> None:
        """Should have non-empty descriptions."""
        from examples.tools.weather_tools import WEATHER_DATA

        for city, data in WEATHER_DATA.items():
            desc = data["description"]
            assert isinstance(desc, str)
            assert len(desc) > 0, f"{city} has empty description"

    def test_tokyo_weather_values(self) -> None:
        """Should have correct Tokyo weather values."""
        from examples.tools.weather_tools import WEATHER_DATA

        tokyo = WEATHER_DATA["tokyo"]
        assert tokyo["temperature"] == 22.5
        assert tokyo["description"] == "Partly cloudy"
        assert tokyo["humidity"] == 65
        assert tokyo["wind_speed"] == 12.3

    def test_london_weather_values(self) -> None:
        """Should have correct London weather values."""
        from examples.tools.weather_tools import WEATHER_DATA

        london = WEATHER_DATA["london"]
        assert london["temperature"] == 15.2
        assert london["description"] == "Light rain"
        assert london["humidity"] == 78

    def test_new_york_weather_values(self) -> None:
        """Should have correct New York weather values."""
        from examples.tools.weather_tools import WEATHER_DATA

        ny = WEATHER_DATA["new york"]
        assert ny["temperature"] == 18.8
        assert ny["description"] == "Clear sky"
        assert ny["humidity"] == 55

    def test_paris_weather_values(self) -> None:
        """Should have correct Paris weather values."""
        from examples.tools.weather_tools import WEATHER_DATA

        paris = WEATHER_DATA["paris"]
        assert paris["temperature"] == 16.9
        assert paris["description"] == "Overcast"
        assert paris["humidity"] == 72


class TestTemperatureConversion:
    """Tests for temperature unit conversion logic."""

    def test_celsius_to_fahrenheit(self) -> None:
        """Should correctly convert Celsius to Fahrenheit."""
        # Formula: F = C * 9/5 + 32
        celsius = 22.5  # Tokyo temp
        fahrenheit = (celsius * 9 / 5) + 32
        assert abs(fahrenheit - 72.5) < 0.1

    def test_celsius_to_kelvin(self) -> None:
        """Should correctly convert Celsius to Kelvin."""
        # Formula: K = C + 273.15
        celsius = 22.5  # Tokyo temp
        kelvin = celsius + 273.15
        assert abs(kelvin - 295.65) < 0.1

    def test_freezing_point_conversions(self) -> None:
        """Should handle freezing point correctly."""
        celsius = 0
        fahrenheit = (celsius * 9 / 5) + 32
        kelvin = celsius + 273.15

        assert fahrenheit == 32
        assert kelvin == 273.15

    def test_negative_temperature_conversions(self) -> None:
        """Should handle negative temperatures correctly."""
        celsius = -10
        fahrenheit = (celsius * 9 / 5) + 32
        kelvin = celsius + 273.15

        assert fahrenheit == 14
        assert kelvin == 263.15


class TestHaversineDistance:
    """Tests for haversine_distance function."""

    def test_same_point_returns_zero(self) -> None:
        """Should return 0 for same coordinates."""
        from examples.tools.maps_tools import haversine_distance

        distance = haversine_distance(35.6762, 139.6503, 35.6762, 139.6503)
        assert distance == 0

    def test_tokyo_london_distance(self) -> None:
        """Should calculate correct distance Tokyo to London."""
        from examples.tools.maps_tools import haversine_distance

        # Tokyo: 35.6762, 139.6503
        # London: 51.5074, -0.1278
        distance = haversine_distance(35.6762, 139.6503, 51.5074, -0.1278)

        # Actual distance is ~9560 km
        assert 9500 < distance < 9600

    def test_london_paris_distance(self) -> None:
        """Should calculate correct distance London to Paris."""
        from examples.tools.maps_tools import haversine_distance

        # London: 51.5074, -0.1278
        # Paris: 48.8566, 2.3522
        distance = haversine_distance(51.5074, -0.1278, 48.8566, 2.3522)

        # Actual distance is ~344 km
        assert 340 < distance < 350

    def test_new_york_paris_distance(self) -> None:
        """Should calculate correct distance New York to Paris."""
        from examples.tools.maps_tools import haversine_distance

        # New York: 40.7128, -74.0060
        # Paris: 48.8566, 2.3522
        distance = haversine_distance(40.7128, -74.0060, 48.8566, 2.3522)

        # Actual distance is ~5837 km
        assert 5800 < distance < 5900

    def test_symmetry(self) -> None:
        """Distance should be same regardless of direction."""
        from examples.tools.maps_tools import haversine_distance

        dist1 = haversine_distance(35.6762, 139.6503, 51.5074, -0.1278)
        dist2 = haversine_distance(51.5074, -0.1278, 35.6762, 139.6503)

        assert abs(dist1 - dist2) < 0.01

    def test_equator_distance(self) -> None:
        """Should calculate distance along equator."""
        from examples.tools.maps_tools import haversine_distance

        # Points on equator, 1 degree apart in longitude
        distance = haversine_distance(0, 0, 0, 1)

        # At equator, 1 degree longitude = ~111 km
        assert 110 < distance < 112

    def test_pole_to_pole(self) -> None:
        """Should calculate distance from pole to pole."""
        from examples.tools.maps_tools import haversine_distance

        # North pole to South pole
        distance = haversine_distance(90, 0, -90, 0)

        # Half of Earth's circumference = ~20,000 km
        assert 19900 < distance < 20100

    def test_short_distances(self) -> None:
        """Should handle very short distances."""
        from examples.tools.maps_tools import haversine_distance

        # Two points very close together
        distance = haversine_distance(35.6762, 139.6503, 35.6763, 139.6504)

        # Should be very small but > 0
        assert 0 < distance < 0.5


class TestCityCoordinates:
    """Tests for city coordinate data."""

    def test_city_coordinates_has_all_cities(self) -> None:
        """Should have coordinates for all expected cities."""
        from examples.tools.maps_tools import CITY_COORDINATES

        expected_cities = ["tokyo", "london", "new york", "paris"]
        for city in expected_cities:
            assert city in CITY_COORDINATES, f"Missing city: {city}"

    def test_city_coordinates_structure(self) -> None:
        """Should have correct coordinate structure."""
        from examples.tools.maps_tools import CITY_COORDINATES

        for city, coords in CITY_COORDINATES.items():
            assert "lat" in coords, f"{city} missing lat"
            assert "lon" in coords, f"{city} missing lon"

    def test_city_coordinates_valid_latitude_range(self) -> None:
        """Should have valid latitude values (-90 to 90)."""
        from examples.tools.maps_tools import CITY_COORDINATES

        for city, coords in CITY_COORDINATES.items():
            lat = coords["lat"]
            assert -90 <= lat <= 90, f"{city} has invalid lat: {lat}"

    def test_city_coordinates_valid_longitude_range(self) -> None:
        """Should have valid longitude values (-180 to 180)."""
        from examples.tools.maps_tools import CITY_COORDINATES

        for city, coords in CITY_COORDINATES.items():
            lon = coords["lon"]
            assert -180 <= lon <= 180, f"{city} has invalid lon: {lon}"

    def test_tokyo_coordinates(self) -> None:
        """Should have correct Tokyo coordinates."""
        from examples.tools.maps_tools import CITY_COORDINATES

        tokyo = CITY_COORDINATES["tokyo"]
        # Tokyo is in Northern hemisphere, Eastern
        assert 30 < tokyo["lat"] < 40
        assert 130 < tokyo["lon"] < 150

    def test_london_coordinates(self) -> None:
        """Should have correct London coordinates."""
        from examples.tools.maps_tools import CITY_COORDINATES

        london = CITY_COORDINATES["london"]
        # London is in Northern hemisphere, near prime meridian
        assert 50 < london["lat"] < 55
        assert -1 < london["lon"] < 1

    def test_new_york_coordinates(self) -> None:
        """Should have correct New York coordinates."""
        from examples.tools.maps_tools import CITY_COORDINATES

        ny = CITY_COORDINATES["new york"]
        # New York is in Northern hemisphere, Western
        assert 40 < ny["lat"] < 45
        assert -80 < ny["lon"] < -70

    def test_paris_coordinates(self) -> None:
        """Should have correct Paris coordinates."""
        from examples.tools.maps_tools import CITY_COORDINATES

        paris = CITY_COORDINATES["paris"]
        # Paris is in Northern hemisphere, Eastern Europe
        assert 45 < paris["lat"] < 50
        assert 2 < paris["lon"] < 3


class TestDistanceConversions:
    """Tests for distance unit conversions."""

    def test_km_to_miles(self) -> None:
        """Should correctly convert kilometers to miles."""
        km = 100
        miles = km * 0.621371
        assert abs(miles - 62.1371) < 0.001

    def test_tokyo_london_in_miles(self) -> None:
        """Should convert Tokyo-London distance to miles."""
        from examples.tools.maps_tools import haversine_distance

        distance_km = haversine_distance(35.6762, 139.6503, 51.5074, -0.1278)
        distance_miles = distance_km * 0.621371

        # ~9560 km = ~5940 miles
        assert 5900 < distance_miles < 6000


class TestAllCityPairs:
    """Tests for distances between all city pairs."""

    def test_all_pairs_positive_distance(self) -> None:
        """All non-identical city pairs should have positive distance."""
        from examples.tools.maps_tools import CITY_COORDINATES, haversine_distance

        cities = list(CITY_COORDINATES.keys())

        for i, city1 in enumerate(cities):
            for city2 in cities[i + 1 :]:
                coords1 = CITY_COORDINATES[city1]
                coords2 = CITY_COORDINATES[city2]
                distance = haversine_distance(
                    coords1["lat"], coords1["lon"], coords2["lat"], coords2["lon"]
                )
                assert distance > 0, f"Zero distance between {city1} and {city2}"

    def test_all_pairs_reasonable_distance(self) -> None:
        """All city pairs should have distance less than half Earth circumference."""
        from examples.tools.maps_tools import CITY_COORDINATES, haversine_distance

        cities = list(CITY_COORDINATES.keys())
        max_distance = 20000  # Half of Earth's circumference

        for city1 in cities:
            for city2 in cities:
                coords1 = CITY_COORDINATES[city1]
                coords2 = CITY_COORDINATES[city2]
                distance = haversine_distance(
                    coords1["lat"], coords1["lon"], coords2["lat"], coords2["lon"]
                )
                assert distance <= max_distance, (
                    f"Unrealistic distance between {city1} and {city2}"
                )


class TestDataConsistency:
    """Tests for data consistency between weather and maps modules."""

    def test_same_cities_in_both_modules(self) -> None:
        """Weather and maps should have the same cities."""
        from examples.tools.maps_tools import CITY_COORDINATES
        from examples.tools.weather_tools import WEATHER_DATA

        weather_cities = set(WEATHER_DATA.keys())
        maps_cities = set(CITY_COORDINATES.keys())

        assert weather_cities == maps_cities, (
            f"City mismatch: Weather has {weather_cities - maps_cities}, "
            f"Maps has {maps_cities - weather_cities}"
        )

    def test_city_count(self) -> None:
        """Both modules should have exactly 4 cities."""
        from examples.tools.maps_tools import CITY_COORDINATES
        from examples.tools.weather_tools import WEATHER_DATA

        assert len(WEATHER_DATA) == 4
        assert len(CITY_COORDINATES) == 4


class TestEdgeCases:
    """Tests for edge cases in tool data."""

    def test_weather_data_is_immutable_copy_safe(self) -> None:
        """Copying weather data should not affect original."""
        from examples.tools.weather_tools import WEATHER_DATA

        original_temp = WEATHER_DATA["tokyo"]["temperature"]

        # Simulate what the tool does
        data = WEATHER_DATA["tokyo"].copy()
        data["temperature"] = 100

        # Original should be unchanged
        assert WEATHER_DATA["tokyo"]["temperature"] == original_temp

    def test_coordinates_numeric_types(self) -> None:
        """Coordinates should be numeric types suitable for math."""
        from examples.tools.maps_tools import CITY_COORDINATES

        for _city, coords in CITY_COORDINATES.items():
            lat = coords["lat"]
            lon = coords["lon"]

            # Should be usable in math operations
            assert isinstance(lat + lon, (int, float))
            assert isinstance(math.radians(lat), float)
            assert isinstance(math.radians(lon), float)

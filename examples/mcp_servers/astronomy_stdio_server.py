"""Astronomy MCP Server using FastMCP 2.0 (stdio transport).

This server provides space/astronomy data that is COMPLETELY DIFFERENT
from the weather data, making it easy to verify external MCP calls work.

Usage:
    uv run python -m examples.mcp_servers.astronomy_stdio_server
"""

from fastmcp import FastMCP

# Create FastMCP server
mcp = FastMCP("astronomy-stdio")

# Mock astronomy data - completely different from weather!
PLANET_DATA = {
    "mercury": {
        "distance_from_sun_km": 57_900_000,
        "diameter_km": 4_879,
        "orbital_period_days": 88,
        "moons": 0,
        "fun_fact": "A day on Mercury is longer than its year!",
    },
    "venus": {
        "distance_from_sun_km": 108_200_000,
        "diameter_km": 12_104,
        "orbital_period_days": 225,
        "moons": 0,
        "fun_fact": "Venus rotates backwards compared to other planets.",
    },
    "earth": {
        "distance_from_sun_km": 149_600_000,
        "diameter_km": 12_742,
        "orbital_period_days": 365,
        "moons": 1,
        "fun_fact": "Earth is the only planet not named after a god.",
    },
    "mars": {
        "distance_from_sun_km": 227_900_000,
        "diameter_km": 6_779,
        "orbital_period_days": 687,
        "moons": 2,
        "fun_fact": "Mars has the largest volcano in the solar system: Olympus Mons.",
    },
    "jupiter": {
        "distance_from_sun_km": 778_500_000,
        "diameter_km": 139_820,
        "orbital_period_days": 4_333,
        "moons": 95,
        "fun_fact": "Jupiter's Great Red Spot is a storm that has raged for over 400 years.",
    },
}

CONSTELLATION_DATA = {
    "orion": {
        "stars": ["Betelgeuse", "Rigel", "Bellatrix", "Mintaka", "Alnilam", "Alnitak"],
        "best_visible": "Winter (Northern Hemisphere)",
        "mythology": "Named after the Greek hunter Orion.",
    },
    "ursa major": {
        "stars": ["Dubhe", "Merak", "Phecda", "Megrez", "Alioth", "Mizar", "Alkaid"],
        "best_visible": "Year-round (Northern Hemisphere)",
        "mythology": "The Great Bear in Greek mythology.",
    },
    "scorpius": {
        "stars": ["Antares", "Shaula", "Sargas", "Dschubba", "Acrab"],
        "best_visible": "Summer (Northern Hemisphere)",
        "mythology": "The scorpion that killed Orion in Greek myth.",
    },
}


@mcp.tool()
def get_planet_info(planet: str) -> str:
    """Get information about a planet in our solar system.

    Args:
        planet: Planet name (Mercury, Venus, Earth, Mars, Jupiter)
    """
    planet_lower = planet.lower().strip()

    if planet_lower not in PLANET_DATA:
        available = ", ".join(p.title() for p in PLANET_DATA.keys())
        return f"Planet '{planet}' not found. Available: {available}"

    data = PLANET_DATA[planet_lower]
    return (
        f"**{planet.title()}**\n"
        f"- Distance from Sun: {data['distance_from_sun_km']:,} km\n"
        f"- Diameter: {data['diameter_km']:,} km\n"
        f"- Orbital Period: {data['orbital_period_days']} Earth days\n"
        f"- Moons: {data['moons']}\n"
        f"- Fun Fact: {data['fun_fact']}"
    )


@mcp.tool()
def get_constellation_info(constellation: str) -> str:
    """Get information about a constellation.

    Args:
        constellation: Constellation name (Orion, Ursa Major, Scorpius)
    """
    const_lower = constellation.lower().strip()

    if const_lower not in CONSTELLATION_DATA:
        available = ", ".join(c.title() for c in CONSTELLATION_DATA.keys())
        return f"Constellation '{constellation}' not found. Available: {available}"

    data = CONSTELLATION_DATA[const_lower]
    stars = ", ".join(data["stars"])
    return (
        f"**{constellation.title()}**\n"
        f"- Major Stars: {stars}\n"
        f"- Best Visible: {data['best_visible']}\n"
        f"- Mythology: {data['mythology']}"
    )


@mcp.tool()
def list_planets() -> str:
    """List all available planets with basic stats."""
    lines = ["**Solar System Planets (Available):**"]
    for name, data in PLANET_DATA.items():
        lines.append(
            f"- {name.title()}: {data['diameter_km']:,} km diameter, {data['moons']} moons"
        )
    return "\n".join(lines)


@mcp.tool()
def list_constellations() -> str:
    """List all available constellations."""
    lines = ["**Constellations (Available):**"]
    for name, data in CONSTELLATION_DATA.items():
        lines.append(f"- {name.title()}: {len(data['stars'])} major stars")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")

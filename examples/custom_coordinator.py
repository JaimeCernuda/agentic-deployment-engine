#!/usr/bin/env python3
"""
Example: Custom Coordinator Agent using Dynamic Agent Discovery

This example demonstrates how to create a reusable coordinator agent
that can connect to any set of agents without hardcoding their capabilities.
"""
from typing import Dict, Any, List
from src.base_a2a_agent import BaseA2AAgent
from src.a2a_transport import create_a2a_transport_server


class CustomCoordinator(BaseA2AAgent):
    """
    A flexible coordinator that can work with any set of agents.

    The agent discovers connected agents at runtime and automatically
    learns their capabilities through the A2A discovery protocol.
    """

    def __init__(
        self,
        name: str = "Custom Coordinator",
        port: int = 9000,
        agent_urls: List[str] = None
    ):
        """
        Initialize a custom coordinator.

        Args:
            name: Display name for the coordinator
            port: HTTP port for A2A endpoints
            agent_urls: List of agent URLs to connect to
        """
        # Default to Weather and Maps if not specified
        if agent_urls is None:
            agent_urls = [
                "http://localhost:9001",  # Weather Agent
                "http://localhost:9002"   # Maps Agent
            ]

        # Base system prompt (will be enhanced with agent info)
        system_prompt = f"""You are {name}, a coordinator that orchestrates multiple specialized agents.

**Your Role:**
- Analyze user queries to determine which agents can help
- Query appropriate agents using the query_agent tool
- Combine responses from multiple agents when needed
- Provide comprehensive, well-formatted answers

**Coordination Strategy:**
- For simple queries, use a single agent
- For complex queries, combine multiple agents' responses
- Always cite which agent provided which information
- Be efficient - only query agents when necessary

**Communication Style:**
- Be helpful and professional
- Synthesize information clearly
- Explain your reasoning when coordinating multiple agents
"""

        # Create SDK MCP server with A2A transport tools
        a2a_server = create_a2a_transport_server()

        super().__init__(
            name=name,
            description=f"Coordinates {len(agent_urls)} specialized agents via A2A protocol",
            port=port,
            sdk_mcp_server=a2a_server,
            system_prompt=system_prompt,
            connected_agents=agent_urls  # Dynamic discovery happens here!
        )

        self.logger.info(f"Coordinator will connect to {len(agent_urls)} agents:")
        for url in agent_urls:
            self.logger.info(f"  - {url}")

    def _get_skills(self) -> List[Dict[str, Any]]:
        """Define coordinator skills for A2A discovery."""
        return [
            {
                "id": "multi_agent_coordination",
                "name": "Multi-Agent Coordination",
                "description": "Coordinate multiple specialized agents to answer complex queries",
                "tags": ["coordination", "multi-agent", "orchestration"],
                "examples": [
                    "Complex queries requiring multiple data sources",
                    "Cross-domain questions",
                    "Aggregated information requests"
                ]
            },
            {
                "id": "intelligent_routing",
                "name": "Intelligent Agent Routing",
                "description": "Route queries to the most appropriate agent(s)",
                "tags": ["routing", "optimization"],
                "examples": [
                    "Determine best agent for a query",
                    "Parallel agent queries",
                    "Sequential agent coordination"
                ]
            }
        ]

    def _get_allowed_tools(self) -> List[str]:
        """Coordinator uses SDK MCP A2A transport tools."""
        return [
            "mcp__a2a_transport__query_agent",
            "mcp__a2a_transport__discover_agent"
        ]


class WeatherOnlyCoordinator(BaseA2AAgent):
    """
    Example: Specialized coordinator that only handles weather queries.

    Demonstrates how to create task-specific coordinators.
    """

    def __init__(self, port: int = 9010):
        system_prompt = """You are a Weather Coordinator specialized in weather queries.

You have access to a Weather Agent that provides:
- Current weather conditions
- Temperature in various units
- Available locations

Use the query_agent tool to get weather information and provide helpful responses.
"""

        super().__init__(
            name="Weather Coordinator",
            description="Specialized coordinator for weather queries",
            port=port,
            sdk_mcp_server=create_a2a_transport_server(),
            system_prompt=system_prompt,
            connected_agents=["http://localhost:9001"]  # Only Weather
        )

    def _get_skills(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "weather_queries",
                "name": "Weather Queries",
                "description": "Handle weather-related questions",
                "tags": ["weather"],
                "examples": ["What's the weather in Tokyo?"]
            }
        ]

    def _get_allowed_tools(self) -> List[str]:
        return ["mcp__a2a_transport__query_agent"]


class MultiDomainCoordinator(BaseA2AAgent):
    """
    Example: Coordinator that works with many different agent types.

    Demonstrates scalability to multiple agents.
    """

    def __init__(self, port: int = 9020):
        # This could connect to 5, 10, or 20+ agents!
        agent_urls = [
            "http://localhost:9001",  # Weather
            "http://localhost:9002",  # Maps
            # "http://localhost:9003",  # Travel (example)
            # "http://localhost:9004",  # Recommendations (example)
            # Add as many as needed...
        ]

        system_prompt = """You are a Multi-Domain Coordinator managing multiple specialized agents.

**Coordination Capabilities:**
- Weather and climate information
- Geographic and mapping data
- Travel planning (when available)
- Recommendations (when available)

**Strategy:**
- Identify all relevant agents for a query
- Query agents in parallel when possible
- Combine responses intelligently
- Provide comprehensive, synthesized answers
"""

        super().__init__(
            name="Multi-Domain Coordinator",
            description="Coordinates multiple domain-specific agents",
            port=port,
            sdk_mcp_server=create_a2a_transport_server(),
            system_prompt=system_prompt,
            connected_agents=agent_urls
        )

    def _get_skills(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "multi_domain_coordination",
                "name": "Multi-Domain Coordination",
                "description": "Coordinate across weather, maps, travel, and more",
                "tags": ["multi-domain", "coordination"],
                "examples": [
                    "Plan a trip with weather and maps",
                    "Multi-faceted queries"
                ]
            }
        ]

    def _get_allowed_tools(self) -> List[str]:
        return ["mcp__a2a_transport__query_agent"]


def main_custom():
    """Run the custom coordinator."""
    coordinator = CustomCoordinator(
        name="My Custom Coordinator",
        port=9000,
        agent_urls=[
            "http://localhost:9001",  # Weather
            "http://localhost:9002"   # Maps
        ]
    )
    print("Starting Custom Coordinator on port 9000...")
    print("Connected to Weather (9001) and Maps (9002)")
    print("Agent capabilities will be discovered automatically on startup...")
    coordinator.run()


def main_weather_only():
    """Run the weather-only coordinator."""
    coordinator = WeatherOnlyCoordinator()
    print("Starting Weather-Only Coordinator on port 9010...")
    print("Connected to Weather Agent (9001)")
    coordinator.run()


def main_multi_domain():
    """Run the multi-domain coordinator."""
    coordinator = MultiDomainCoordinator()
    print("Starting Multi-Domain Coordinator on port 9020...")
    print("Connected to multiple specialized agents")
    coordinator.run()


if __name__ == "__main__":
    # Run the custom coordinator by default
    main_custom()

    # Uncomment to run alternatives:
    # main_weather_only()
    # main_multi_domain()

"""Controller Agent for multi-agent coordination via A2A protocol.

Now uses SDK MCP A2A transport with dynamic agent discovery.
"""

import asyncio
from typing import Dict, Any, List
from src.base_a2a_agent import BaseA2AAgent
from src.a2a_transport import create_a2a_transport_server


class ControllerAgent(BaseA2AAgent):
    """Controller Agent that coordinates multiple agents via A2A protocol.

    Uses SDK MCP A2A transport for efficient communication and dynamic agent discovery.
    """

    def __init__(self, port: int = 9000, connected_agents: List[str] = None):
        # Default to Weather and Maps agents if not specified
        if connected_agents is None:
            connected_agents = [
                "http://localhost:9001",  # Weather Agent
                "http://localhost:9002"   # Maps Agent
            ]

        # Base system prompt (agent info will be added dynamically)
        system_prompt = """You are a Controller Agent responsible for coordinating multiple specialized agents via the A2A (Agent-to-Agent) protocol.

You have access to the mcp__a2a_transport__query_agent tool to communicate with other agents efficiently.

When users ask questions:
1. Identify which agent(s) can help answer the question
2. Use the query_agent tool to get information from relevant agents
3. Synthesize responses from multiple agents when needed
4. Provide comprehensive, well-formatted answers

Always be helpful and coordinate effectively between agents to provide the best possible responses."""

        # Create SDK MCP server with A2A transport tools
        a2a_server = create_a2a_transport_server()

        super().__init__(
            name="Controller Agent",
            description="Multi-agent coordinator using SDK MCP A2A transport",
            port=port,
            sdk_mcp_server=a2a_server,
            system_prompt=system_prompt,
            connected_agents=connected_agents
        )

    def _get_skills(self) -> List[Dict[str, Any]]:
        """Define controller agent skills for A2A discovery."""
        return [
            {
                "id": "multi_agent_coordination",
                "name": "Multi-Agent Coordination",
                "description": "Coordinate weather and maps agents for complex queries using A2A protocol",
                "tags": ["coordination", "multi-agent", "weather", "maps"],
                "examples": [
                    "What's the weather in Tokyo and how far is it from London?",
                    "Get weather for Paris and distance to New York",
                    "Weather and travel information for multiple cities"
                ]
            },
            {
                "id": "agent_discovery",
                "name": "Agent Discovery",
                "description": "Discover available agents and their capabilities via A2A",
                "tags": ["discovery", "agents", "a2a"],
                "examples": [
                    "What agents are available?",
                    "List agent capabilities",
                    "Show available services"
                ]
            }
        ]

    def _get_allowed_tools(self) -> List[str]:
        """Controller uses SDK MCP A2A transport tools."""
        return ["mcp__a2a_transport__query_agent", "mcp__a2a_transport__discover_agent"]


def main():
    """Run the Controller Agent."""
    import os

    # Read configuration from environment variables
    port = int(os.getenv("AGENT_PORT", "9000"))

    # Parse connected agents from environment
    connected_agents = None
    if "CONNECTED_AGENTS" in os.environ:
        connected_agents = [
            url.strip() for url in os.environ["CONNECTED_AGENTS"].split(",")
        ]

    agent = ControllerAgent(port=port, connected_agents=connected_agents)
    print(f"Starting Controller Agent on port {port}...")
    print("Using SDK MCP A2A transport for agent coordination")
    if connected_agents:
        print("Will discover and connect to:")
        for url in connected_agents:
            print(f"  - {url}")
    print("\nAgent discovery will happen automatically on startup...")
    agent.run()


if __name__ == "__main__":
    main()
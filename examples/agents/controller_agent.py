"""Controller Agent for multi-agent coordination via A2A protocol.

Now uses SDK MCP A2A transport with dynamic agent discovery.
"""

from typing import Any

from src import BaseA2AAgent
from src.agents.transport import create_a2a_transport_server
from src.security import PermissionPreset


class ControllerAgent(BaseA2AAgent):
    """Controller Agent that coordinates multiple agents via A2A protocol.

    Uses SDK MCP A2A transport for efficient communication and dynamic agent discovery.
    """

    def __init__(
        self,
        port: int = 9000,
        connected_agents: list[str] | None = None,
        permission_preset: PermissionPreset = PermissionPreset.FULL_ACCESS,
    ):
        # Default to Weather and Maps agents if not specified
        if connected_agents is None:
            connected_agents = [
                "http://localhost:9001",  # Weather Agent
                "http://localhost:9002",  # Maps Agent
            ]

        # Base system prompt (agent info will be added dynamically)
        system_prompt = """You are a Controller Agent responsible for coordinating multiple specialized agents via the A2A (Agent-to-Agent) protocol.

**IMPORTANT: You MUST use the SDK MCP tools available to you:**
- `mcp__controller_agent__query_agent`: Query another agent via HTTP POST
- `mcp__controller_agent__discover_agent`: Discover agent capabilities

When users ask questions:
1. Identify which agent(s) can help answer the question
2. Use the mcp__controller_agent__query_agent tool to get information from relevant agents
3. Synthesize responses from multiple agents when needed
4. Provide comprehensive, well-formatted answers

**DO NOT:**
- Try to query agents via HTTP/curl directly
- Use the Bash tool for agent communication
- Guess information - always use the tools to query other agents

Always be helpful and coordinate effectively between agents to provide the best possible responses."""

        # Create SDK MCP server with A2A transport tools
        # Pass the name to match dictionary key (controller_agent)
        a2a_server = create_a2a_transport_server(name="controller_agent")

        super().__init__(
            name="Controller Agent",
            description="Multi-agent coordinator using SDK MCP A2A transport",
            port=port,
            sdk_mcp_server=a2a_server,
            system_prompt=system_prompt,
            connected_agents=connected_agents,
            permission_preset=permission_preset,
        )

    def _get_skills(self) -> list[dict[str, Any]]:
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
                    "Weather and travel information for multiple cities",
                ],
            },
            {
                "id": "agent_discovery",
                "name": "Agent Discovery",
                "description": "Discover available agents and their capabilities via A2A",
                "tags": ["discovery", "agents", "a2a"],
                "examples": [
                    "What agents are available?",
                    "List agent capabilities",
                    "Show available services",
                ],
            },
        ]

    def _get_allowed_tools(self) -> list[str]:
        """Controller uses SDK MCP A2A transport tools.

        Tool naming: mcp__<server_key>__<tool_name>
        Server key comes from dict key in base_a2a_agent.py which uses
        self.name.lower().replace(" ", "_") = "controller_agent"
        """
        return [
            "mcp__controller_agent__query_agent",
            "mcp__controller_agent__discover_agent",
        ]


def main():
    """Run the Controller Agent."""
    import os

    # Read configuration from environment variables
    port = int(os.getenv("AGENT_PORT", "9000"))

    # Read permission preset from environment
    preset_name = os.getenv("AGENT_PERMISSION_PRESET", "full_access").lower()
    preset_map = {
        "full_access": PermissionPreset.FULL_ACCESS,
        "read_only": PermissionPreset.READ_ONLY,
        "communication_only": PermissionPreset.COMMUNICATION_ONLY,
    }
    permission_preset = preset_map.get(preset_name, PermissionPreset.FULL_ACCESS)

    # Parse connected agents from environment
    connected_agents = None
    if "CONNECTED_AGENTS" in os.environ:
        connected_agents = [
            url.strip() for url in os.environ["CONNECTED_AGENTS"].split(",")
        ]

    agent = ControllerAgent(
        port=port, connected_agents=connected_agents, permission_preset=permission_preset
    )
    print(f"Starting Controller Agent on port {port}...")
    print(f"Permission preset: {permission_preset.value}")
    print("Using SDK MCP A2A transport for agent coordination")
    if connected_agents:
        print("Will discover and connect to:")
        for url in connected_agents:
            print(f"  - {url}")
    print("\nAgent discovery will happen automatically on startup...")
    agent.run()


if __name__ == "__main__":
    main()

import logging
import sys
import asyncio
from pathlib import Path

# Add project root and example directory to path for imports
project_root = Path(__file__).parent.parent.parent.parent
example_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(example_dir))

from src.base_a2a_agent import BaseA2AAgent
from src.a2a_transport import create_a2a_transport_server
from src.agent_registry import AgentRegistry

class GeneralAgent(BaseA2AAgent):
    """General Agent that answers general questions and orchestrates specialized agents via dynamic discovery."""

    def __init__(self, port: int = 9001, agent_urls_to_discover: list = None):
        """
        Initialize General Agent with dynamic agent discovery.

        Args:
            port: Port to run the General Agent on
            agent_urls_to_discover: List of agent URLs to discover (e.g., ["http://localhost:9002", ...])
        """


        # Create shared registry
        agent_registry = AgentRegistry()

        # Discover agents synchronously during initialization
        # We need to run the async discovery in a blocking way
        async def discover_all_agents():
            if agent_urls_to_discover:
                for url in agent_urls_to_discover:
                    await agent_registry.discover_agent(url)

        asyncio.run(discover_all_agents())

        # Generate dynamic system prompt based on discovered agents
        base_prompt = """
You are a General Agent responsible for answering any kind of user question clearly and helpfully.

You can delegate tasks to specialized agents that have been discovered in the system.

**Your delegation strategy:**
1. Analyze the user's question to understand what type of capability is needed
2. Match the question to the appropriate specialized agent based on their skills
3. Use the mcp__a2a_transport__query_agent tool with the agent's URL to delegate
4. If a task requires multiple agents (e.g., search for data, then calculate):
   - Call each agent in the appropriate order
   - Integrate all results in your final answer
5. For general knowledge questions that don't require specialized tools → answer directly yourself
6. Never perform calculations or conversions manually; always delegate to specialized agents

**Example delegation patterns:**
- Math operations or unit conversions → delegate to agents with math/conversion skills
- Currency or financial calculations → delegate to agents with finance skills
- Web searches or current information → delegate to agents with search skills
- General knowledge (e.g., "Who discovered gravity?") → answer directly

**Important:**
- Always use the exact agent URL when calling mcp__a2a_transport__query_agent
- The query_agent tool requires: agent_url (string) and query (string)
- Integrate responses from agents naturally into your final answer to the user
- You can call multiple agents sequentially if needed for complex tasks
"""

        # Generate full system prompt with discovered agents
        system_prompt = agent_registry.generate_system_prompt(base_prompt)

        # Create MCP server with A2A transport tools
        agent_sdk_server = create_a2a_transport_server()

        super().__init__(
            name="General Agent",
            description="Orchestrates tasks across specialized agents using dynamic discovery.",
            port=port,
            sdk_mcp_server=agent_sdk_server,
            system_prompt=system_prompt
        )

        # Store the agent registry for use by this agent
        self.agent_registry = agent_registry

        discovered_agents = agent_registry.list_agents()
        self.logger.info(f"General Agent initialized with {len(discovered_agents)} discovered agents")

    def _get_skills(self):
        """Define general agent skills for A2A discovery."""
        return [
            {
                "id": "general_knowledge",
                "name": "General Knowledge",
                "description": "Answer general knowledge questions on various topics",
                "tags": ["general", "knowledge", "questions"],
                "examples": [
                    "Who discovered gravity?",
                    "What is the capital of France?",
                    "Explain photosynthesis"
                ]
            }
        ]

    def _get_allowed_tools(self):
        """General Agent can use the A2A transport tools to communicate with other agents."""
        # The server is registered with the agent name (general_agent), not a2a_transport
        return [
            "mcp__general_agent__query_agent",
            "mcp__general_agent__discover_agent"
        ]

    async def _handle_query(self, query: str):
        """
        Handle incoming queries.

        The agent itself decides (via system prompt + Claude SDK)
        whether to answer directly or call the Tools Agent.
        """
        self.logger.info(f"Received query: {query}")

        # Let Claude handle the reasoning and delegation based on prompt instructions.
        response = await super()._handle_query(query)

        self.logger.info(f"Response: {response}")
        return response


def main():
    """Run the General Agent."""
    import os
    port = int(os.getenv("AGENT_PORT", "9001"))

    # URLs of agents to discover
    agent_urls_to_discover = [
        "http://localhost:9002",  # Math Agent
        "http://localhost:9003",  # Finance Agent
        "http://localhost:9004",  # Search Agent
    ]

    agent = GeneralAgent(port=port, agent_urls_to_discover=agent_urls_to_discover)
    print(f"Starting General Agent on port {port}...")
    agent.run()


if __name__ == "__main__":
    main()

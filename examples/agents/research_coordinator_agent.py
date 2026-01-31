"""
Research Coordinator Agent for the Research Assistant Pipeline.

Coordinates the searcher, summarizer, and fact checker agents
to provide comprehensive research assistance.
"""

from src import BaseA2AAgent
from src.agents.transport import create_a2a_transport_server


class ResearchCoordinatorAgent(BaseA2AAgent):
    """Coordinator agent that orchestrates research workflow."""

    def __init__(self, port: int = 9020, connected_agents: list[str] | None = None):
        """Initialize the Research Coordinator Agent.

        Args:
            port: Port to run the agent on (default 9020)
            connected_agents: List of agent URLs to coordinate
        """
        server = create_a2a_transport_server(name="research_coordinator_agent")

        super().__init__(
            name="Research Coordinator",
            description="Coordinates research agents to answer questions with citations",
            port=port,
            sdk_mcp_server=server,
            connected_agents=connected_agents
            or [
                "http://localhost:9021",  # Searcher
                "http://localhost:9022",  # Summarizer
                "http://localhost:9023",  # Fact Checker
            ],
            system_prompt="""You are a Research Coordinator responsible for orchestrating
a team of specialized research agents to answer questions comprehensively.

**Your Team:**
- Searcher Agent (port 9021): Searches the web and fetches content
- Summarizer Agent (port 9022): Extracts key points and summarizes
- Fact Checker Agent (port 9023): Verifies claims and finds sources

**Research Workflow:**
1. For any research question, first query the Searcher Agent to find relevant information
2. Pass the results to the Summarizer Agent to extract key points
3. Use the Fact Checker Agent to verify important claims and find authoritative sources
4. Synthesize all information into a comprehensive, well-cited answer

**IMPORTANT:**
- Always cite your sources
- Include confidence levels for claims
- Present information in a clear, organized format
- Use all three agents for thorough research

Use your query_agent tool to communicate with the specialized agents.""",
        )

    def _get_skills(self) -> list:
        """Return the list of skills this agent provides."""
        return [
            {
                "id": "research",
                "name": "Research Topic",
                "description": "Research any topic using specialized agents",
                "tags": ["research", "analysis", "comprehensive"],
                "examples": [
                    "Research the impact of AI on employment",
                    "What are the latest developments in renewable energy?",
                ],
            },
            {
                "id": "fact_check",
                "name": "Fact Check",
                "description": "Verify claims using fact-checking agents",
                "tags": ["verification", "truth", "sources"],
                "examples": [
                    "Is it true that electric cars produce zero emissions?",
                    "Verify this climate statistic",
                ],
            },
        ]

    def _get_allowed_tools(self) -> list[str]:
        """Return the list of allowed tools for this agent."""
        return [
            "mcp__research_coordinator_agent__query_agent",
            "mcp__research_coordinator_agent__discover_agent",
        ]


def main():
    """Run the Research Coordinator Agent."""
    import os

    port = int(os.getenv("AGENT_PORT", "9020"))
    agent = ResearchCoordinatorAgent(port=port)
    print(f"Starting Research Coordinator Agent on port {port}...")
    agent.run()


if __name__ == "__main__":
    main()

"""
Searcher Agent for the Research Assistant Pipeline.

Specializes in web searching and content fetching.
"""

from claude_agent_sdk import create_sdk_mcp_server

from examples.tools.research_tools import fetch_url, web_search
from src import BaseA2AAgent


class SearcherAgent(BaseA2AAgent):
    """Agent specialized in web searching and content fetching."""

    def __init__(self, port: int = 9021):
        """Initialize the Searcher Agent.

        Args:
            port: Port to run the agent on (default 9021)
        """
        server = create_sdk_mcp_server(
            name="searcher_agent",
            version="1.0.0",
            tools=[web_search, fetch_url],
        )

        super().__init__(
            name="Searcher Agent",
            description="Searches the web and fetches content from URLs",
            port=port,
            sdk_mcp_server=server,
            system_prompt="""You are a Searcher Agent specialized in finding information on the web.

Your capabilities:
- Search the web for relevant information on any topic
- Fetch and extract content from URLs
- Find authoritative and reliable sources

When asked to research a topic:
1. Use web_search to find relevant results
2. Use fetch_url to get detailed content from promising sources
3. Compile the most relevant information

Always cite your sources and indicate the reliability of information found.""",
        )

    def _get_skills(self) -> list:
        """Return the list of skills this agent provides."""
        return [
            {
                "id": "web_search",
                "name": "Web Search",
                "description": "Search the web for information on any topic",
                "tags": ["search", "research", "web"],
                "examples": [
                    "Search for information about climate change",
                    "Find recent news about AI developments",
                ],
            },
            {
                "id": "fetch_content",
                "name": "Fetch Content",
                "description": "Fetch and extract content from web pages",
                "tags": ["fetch", "content", "extraction"],
                "examples": [
                    "Get the content from this Wikipedia article",
                    "Extract information from this research paper URL",
                ],
            },
        ]

    def _get_allowed_tools(self) -> list[str]:
        """Return the list of allowed tools for this agent."""
        return [
            "mcp__searcher_agent__web_search",
            "mcp__searcher_agent__fetch_url",
        ]


def main():
    """Run the Searcher Agent."""
    import os

    # Read port from environment (set by deployer)
    port = int(os.getenv("AGENT_PORT", "9021"))

    agent = SearcherAgent(port=port)
    print(f"Starting Searcher Agent on port {port}...")
    agent.run()


if __name__ == "__main__":
    main()

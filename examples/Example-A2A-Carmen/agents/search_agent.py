import sys
from pathlib import Path

# Add project root and example directory to path for imports
project_root = Path(__file__).parent.parent.parent.parent
example_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(example_dir))

from src.base_a2a_agent import BaseA2AAgent
from claude_agent_sdk import ClaudeAgentOptions


class SearchAgent(BaseA2AAgent):
    """
    Search Agent using Claude Code's built-in web search capabilities.
    Provides web search and URL fetching capabilities to other agents.
    """

    def __init__(self, port=9004):
        # Initialize base agent using Claude Code's built-in web search capabilities
        system_prompt = (
            "You are the Search Agent. You have access to web search capabilities through WebSearch and WebFetch tools.\n\n"
            "**IMPORTANT RULES:**\n"
            "1. ALWAYS use your WebSearch tool to find current information on the web.\n"
            "2. Use the WebSearch tool to query the web for real-time information.\n"
            "3. When a user asks about current events, recent information, or anything requiring web search, use WebSearch.\n"
            "4. After receiving search results, synthesize the information and present it clearly to the user.\n"
            "5. If search results are not sufficient, you may refine your search query and try again.\n"
            "6. You can also use WebFetch to get detailed information from specific URLs found in search results.\n"
            "7. Always cite or reference that the information comes from web search results.\n"
        )

        # Initialize base class without sdk_mcp_server (using built-in tools)
        super().__init__(
            name="Search Agent",
            description="Performs web searches using built-in WebSearch capabilities to find current information.",
            port=port,
            sdk_mcp_server=None,
            system_prompt=system_prompt
        )

        # Override claude_options to enable built-in web search tools
        # These are provided by Claude Code and don't require external MCP servers
        allowed_tools = self._get_allowed_tools()
        self.logger.debug(f"Configuring Search Agent with built-in web tools")
        self.logger.debug(f"Allowed tools: {allowed_tools}")

        # Create new claude_options with built-in tools enabled
        self.claude_options = ClaudeAgentOptions(
            mcp_servers={},  # No external MCP servers needed
            allowed_tools=allowed_tools,
            system_prompt=self.system_prompt
        )

        self.logger.info("Search Agent initialized with built-in web search capabilities")

    def _get_skills(self):
        """Define search agent skills for A2A discovery."""
        return [
            {
                "id": "web_search",
                "name": "Web Search",
                "description": "Search the web using DuckDuckGo for current information, news, facts, and real-time data",
                "tags": ["search", "web", "internet", "information", "current", "news", "lookup"],
                "examples": [
                    "Search for the latest news about artificial intelligence",
                    "What is the current weather in New York?",
                    "Find information about the Python programming language",
                    "Search for recent developments in quantum computing",
                    "Look up the definition of machine learning"
                ]
            },
            {
                "id": "information_retrieval",
                "name": "Information Retrieval",
                "description": "Retrieve and synthesize information from the web on any topic",
                "tags": ["information", "research", "facts", "data", "knowledge"],
                "examples": [
                    "What are the main features of the latest iPhone?",
                    "Find information about climate change statistics",
                    "Research the history of the internet",
                    "Get current stock market trends"
                ]
            }
        ]

    def _get_allowed_tools(self):
        """
        Allow access to Claude Code's built-in web search tools.
        WebSearch: Search the web for information
        WebFetch: Fetch content from specific URLs
        """
        return [
            "WebSearch",
            "WebFetch"
        ]


def main():
    """Run the Search Agent."""
    agent = SearchAgent(port=9004)
    print("Starting Search Agent on port 9004...")
    print("This agent uses Claude Code's built-in WebSearch and WebFetch tools.")
    agent.run()


if __name__ == "__main__":
    main()

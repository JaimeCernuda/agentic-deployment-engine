"""
Summarizer Agent for the Research Assistant Pipeline.

Specializes in extracting key points and summarizing content.
"""

from claude_agent_sdk import create_sdk_mcp_server

from examples.tools.research_tools import extract_key_points
from src import BaseA2AAgent


class SummarizerAgent(BaseA2AAgent):
    """Agent specialized in summarizing content and extracting key points."""

    def __init__(self, port: int = 9022):
        """Initialize the Summarizer Agent.

        Args:
            port: Port to run the agent on (default 9022)
        """
        server = create_sdk_mcp_server(
            name="summarizer_agent",
            version="1.0.0",
            tools=[extract_key_points],
        )

        super().__init__(
            name="Summarizer Agent",
            description="Extracts key points and summarizes content",
            port=port,
            sdk_mcp_server=server,
            system_prompt="""You are a Summarizer Agent specialized in condensing information.

Your capabilities:
- Extract key points from large amounts of text
- Create concise, accurate summaries
- Identify the most important information

When summarizing content:
1. Identify the main topics and themes
2. Extract the most relevant facts and data
3. Present information in a clear, structured format
4. Highlight key findings and conclusions

Always maintain accuracy while condensing information.""",
        )

    def _get_skills(self) -> list:
        """Return the list of skills this agent provides."""
        return [
            {
                "id": "summarize",
                "name": "Summarize Content",
                "description": "Create concise summaries of text content",
                "tags": ["summary", "extraction", "analysis"],
                "examples": [
                    "Summarize this research paper",
                    "Extract the key points from this article",
                ],
            },
        ]

    def _get_allowed_tools(self) -> list[str]:
        """Return the list of allowed tools for this agent."""
        return [
            "mcp__summarizer_agent__extract_key_points",
        ]


def main():
    """Run the Summarizer Agent."""
    agent = SummarizerAgent()
    agent.run()


if __name__ == "__main__":
    main()

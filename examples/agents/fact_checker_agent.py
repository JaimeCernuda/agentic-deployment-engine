"""
Fact Checker Agent for the Research Assistant Pipeline.

Specializes in verifying claims and finding authoritative sources.
"""

from claude_agent_sdk import create_sdk_mcp_server

from examples.tools.research_tools import find_sources, verify_claim
from src import BaseA2AAgent


class FactCheckerAgent(BaseA2AAgent):
    """Agent specialized in fact-checking and source verification."""

    def __init__(self, port: int = 9023):
        """Initialize the Fact Checker Agent.

        Args:
            port: Port to run the agent on (default 9023)
        """
        server = create_sdk_mcp_server(
            name="fact_checker_agent",
            version="1.0.0",
            tools=[verify_claim, find_sources],
        )

        super().__init__(
            name="Fact Checker Agent",
            description="Verifies claims and finds authoritative sources",
            port=port,
            sdk_mcp_server=server,
            system_prompt="""You are a Fact Checker Agent specialized in verification.

Your capabilities:
- Verify the accuracy of claims and statements
- Find authoritative sources to support or refute claims
- Rate the reliability of information

When fact-checking:
1. Identify the specific claim to verify
2. Search for supporting or contradicting evidence
3. Evaluate source reliability
4. Provide a clear verdict with confidence level

Always be objective and cite sources for verification.""",
        )

    def _get_skills(self) -> list:
        """Return the list of skills this agent provides."""
        return [
            {
                "id": "verify_claim",
                "name": "Verify Claim",
                "description": "Check if a claim is true, false, or unverifiable",
                "tags": ["fact-check", "verification", "truth"],
                "examples": [
                    "Is it true that X causes Y?",
                    "Verify this statistical claim",
                ],
            },
            {
                "id": "find_sources",
                "name": "Find Sources",
                "description": "Find authoritative sources on a topic",
                "tags": ["sources", "references", "citations"],
                "examples": [
                    "Find academic sources on this topic",
                    "What are the most reliable sources for this information?",
                ],
            },
        ]

    def _get_allowed_tools(self) -> list[str]:
        """Return the list of allowed tools for this agent."""
        return [
            "mcp__fact_checker_agent__verify_claim",
            "mcp__fact_checker_agent__find_sources",
        ]


def main():
    """Run the Fact Checker Agent."""
    agent = FactCheckerAgent()
    agent.run()


if __name__ == "__main__":
    main()

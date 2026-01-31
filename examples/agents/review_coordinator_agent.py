"""Review Coordinator Agent - Orchestrates code review pipeline."""

from src import BaseA2AAgent
from src.agents.transport import create_a2a_transport_server


class ReviewCoordinatorAgent(BaseA2AAgent):
    """Coordinator agent for code review pipeline."""

    def __init__(
        self,
        port: int = 9010,
        connected_agents: list[str] | None = None,
    ):
        # Connected agents for the review pipeline
        if connected_agents is None:
            connected_agents = [
                "http://localhost:9011",  # linter
                "http://localhost:9012",  # security
                "http://localhost:9013",  # complexity
            ]

        server = create_a2a_transport_server("review_coordinator")

        super().__init__(
            name="Review Coordinator",
            description="Orchestrates multi-agent code review pipeline",
            port=port,
            sdk_mcp_server=server,
            connected_agents=connected_agents,
            system_prompt="""You are a Review Coordinator that orchestrates a comprehensive code review.

You have access to three specialized review agents:
1. **Linter Agent** (http://localhost:9011) - Code style and formatting
2. **Security Agent** (http://localhost:9012) - Security vulnerabilities
3. **Complexity Agent** (http://localhost:9013) - Complexity metrics

When asked to review code:
1. First, discover all connected agents to verify availability
2. Query each agent in parallel for their analysis
3. Synthesize findings into a comprehensive review report
4. Prioritize issues by severity (Security HIGH > Style LOW)

Format your final report as:
## Code Review Summary
### Critical Issues (Security)
### Warnings (Complexity)
### Style Issues (Linting)
### Recommendations

Always be constructive and provide actionable feedback.""",
        )

    def _get_skills(self) -> list:
        return [
            {
                "id": "full_review",
                "name": "Full Code Review",
                "description": "Comprehensive code review using all specialized agents",
                "tags": ["review", "code", "comprehensive"],
                "examples": [
                    "Review the codebase",
                    "Run a full code review",
                    "Analyze all files for issues",
                ],
            },
            {
                "id": "security_focus",
                "name": "Security-Focused Review",
                "description": "Security-focused code review",
                "tags": ["security", "review"],
                "examples": [
                    "Check for security vulnerabilities",
                    "Security audit the code",
                ],
            },
        ]

    def _get_allowed_tools(self) -> list[str]:
        return [
            "mcp__review_coordinator__query_agent",
            "mcp__review_coordinator__discover_agent",
        ]


def main():
    """Run the review coordinator agent."""
    import os

    # Get connected agents from environment or use defaults
    agents_env = os.environ.get("CONNECTED_AGENTS", "")
    connected = agents_env.split(",") if agents_env else None

    print("Starting Review Coordinator on port 9010...")
    print(f"Connected agents: {connected or 'defaults'}")
    agent = ReviewCoordinatorAgent(connected_agents=connected)
    agent.run()


if __name__ == "__main__":
    main()

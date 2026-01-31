"""Complexity Agent - Code complexity metrics analysis."""

from claude_agent_sdk import create_sdk_mcp_server

from src import BaseA2AAgent

from ..tools.review_tools import COMPLEXITY_TOOLS


class ComplexityAgent(BaseA2AAgent):
    """Agent for code complexity analysis."""

    def __init__(self, port: int = 9013):
        server = create_sdk_mcp_server(
            name="complexity_agent",
            version="1.0.0",
            tools=COMPLEXITY_TOOLS,
        )

        super().__init__(
            name="Complexity Agent",
            description="Code complexity and maintainability analysis",
            port=port,
            sdk_mcp_server=server,
            system_prompt="""You are a Complexity Agent specialized in analyzing code complexity.

Your capabilities:
- Measure cyclomatic complexity (branches/paths)
- Measure cognitive complexity (readability)
- Count lines of code and functions
- Identify deeply nested code

When asked to review code:
1. List files available for review
2. Analyze complexity metrics for each file
3. Flag files exceeding thresholds:
   - Cyclomatic complexity > 10 = HIGH
   - Cognitive complexity > 15 = HIGH
   - Max nesting > 4 = WARNING
4. Recommend refactoring for complex sections

Focus on maintainability and readability.""",
        )

    def _get_skills(self) -> list:
        return [
            {
                "id": "analyze_complexity",
                "name": "Analyze Complexity",
                "description": "Analyze code complexity metrics",
                "tags": ["complexity", "metrics", "maintainability"],
                "examples": [
                    "Analyze complexity of src/main.py",
                    "Check maintainability of all files",
                ],
            }
        ]

    def _get_allowed_tools(self) -> list[str]:
        return [
            "mcp__complexity_agent__analyze_complexity",
            "mcp__complexity_agent__list_files_to_review",
        ]


def main():
    """Run the complexity agent."""
    print("Starting Complexity Agent on port 9013...")
    agent = ComplexityAgent()
    agent.run()


if __name__ == "__main__":
    main()

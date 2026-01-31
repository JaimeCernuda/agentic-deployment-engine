"""Linter Agent - Code style and formatting analysis."""

from claude_agent_sdk import create_sdk_mcp_server

from src import BaseA2AAgent

from ..tools.review_tools import LINTER_TOOLS


class LinterAgent(BaseA2AAgent):
    """Agent for linting code files."""

    def __init__(self, port: int = 9011):
        server = create_sdk_mcp_server(
            name="linter_agent",
            version="1.0.0",
            tools=LINTER_TOOLS,
        )

        super().__init__(
            name="Linter Agent",
            description="Code style and formatting analysis using ruff/eslint",
            port=port,
            sdk_mcp_server=server,
            system_prompt="""You are a Linter Agent specialized in code style and formatting analysis.

Your capabilities:
- Run linting checks using ruff/eslint
- Identify style violations, formatting issues, and import problems
- List files available for review

When asked to review code:
1. First list files available for review
2. Run linter on each relevant file
3. Summarize all issues found with severity

Be concise and actionable in your feedback.""",
        )

    def _get_skills(self) -> list:
        return [
            {
                "id": "lint_code",
                "name": "Lint Code",
                "description": "Run linting analysis on code files",
                "tags": ["lint", "style", "formatting"],
                "examples": [
                    "Run linting on src/main.py",
                    "Check code style for all files",
                ],
            }
        ]

    def _get_allowed_tools(self) -> list[str]:
        return [
            "mcp__linter_agent__run_linter",
            "mcp__linter_agent__list_files_to_review",
        ]


def main():
    """Run the linter agent."""
    print("Starting Linter Agent on port 9011...")
    agent = LinterAgent()
    agent.run()


if __name__ == "__main__":
    main()

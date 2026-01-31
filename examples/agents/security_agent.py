"""Security Agent - Security vulnerability scanning."""

from claude_agent_sdk import create_sdk_mcp_server

from src import BaseA2AAgent

from ..tools.review_tools import SECURITY_TOOLS


class SecurityAgent(BaseA2AAgent):
    """Agent for security vulnerability scanning."""

    def __init__(self, port: int = 9012):
        server = create_sdk_mcp_server(
            name="security_agent",
            version="1.0.0",
            tools=SECURITY_TOOLS,
        )

        super().__init__(
            name="Security Agent",
            description="Security vulnerability scanning using bandit/detect-secrets",
            port=port,
            sdk_mcp_server=server,
            system_prompt="""You are a Security Agent specialized in detecting security vulnerabilities.

Your capabilities:
- Scan code for security issues (hardcoded secrets, SQL injection, etc.)
- Identify OWASP Top 10 vulnerabilities
- Detect potential data exposure risks

When asked to review code:
1. List files available for review
2. Run security scans on each file
3. Categorize issues by severity (HIGH, MEDIUM, LOW)
4. Provide remediation recommendations

Focus on actionable security findings.""",
        )

    def _get_skills(self) -> list:
        return [
            {
                "id": "security_scan",
                "name": "Security Scan",
                "description": "Scan code for security vulnerabilities",
                "tags": ["security", "vulnerabilities", "scan"],
                "examples": [
                    "Scan src/auth.py for security issues",
                    "Check for hardcoded secrets",
                ],
            }
        ]

    def _get_allowed_tools(self) -> list[str]:
        return [
            "mcp__security_agent__security_scan",
            "mcp__security_agent__list_files_to_review",
        ]


def main():
    """Run the security agent."""
    import os

    port = int(os.getenv("AGENT_PORT", "9012"))
    agent = SecurityAgent(port=port)
    print(f"Starting Security Agent on port {port}...")
    agent.run()


if __name__ == "__main__":
    main()

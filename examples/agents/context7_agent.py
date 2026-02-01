"""Context7 Agent using external MCP server (npx @upstash/context7-mcp).

This agent uses the real Context7 MCP server from Upstash to provide
up-to-date code documentation for various libraries and frameworks.

Requires Node.js 18+ installed.
"""

import os
from typing import Any

from src import BaseA2AAgent
from src.security import PermissionPreset


class Context7Agent(BaseA2AAgent):
    """Agent using real Context7 MCP server for code documentation.

    Uses npx @upstash/context7-mcp as an external stdio MCP server.
    This is a REAL external MCP server, not a mock!
    """

    def __init__(
        self,
        port: int = 9004,
        permission_preset: PermissionPreset = PermissionPreset.FULL_ACCESS,
    ):
        # Configure Context7 stdio MCP server
        # Uses npx to run @upstash/context7-mcp
        stdio_mcp_config = {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@upstash/context7-mcp@latest"],
            "env": {},
        }

        system_prompt = """You are a Documentation Agent with access to Context7 MCP server.

**IMPORTANT: You have access to the Context7 MCP tools:**
- `mcp__context7__resolve-library-id`: Resolve a library name to its Context7 ID
- `mcp__context7__get-library-docs`: Get documentation for a specific library

**How to respond:**
1. When asked about a library's docs, first resolve the library ID
2. Then fetch the documentation using get-library-docs
3. Provide a helpful summary of the documentation

**Example workflow:**
- User asks: "How do I use FastAPI?"
- First resolve: resolve-library-id("fastapi")
- Then get docs: get-library-docs(library_id, topic="getting started")

**DO NOT:**
- Make up documentation - always use the tools
- Guess API usage without checking docs"""

        super().__init__(
            name="Context7 Agent",
            description="Documentation agent using real Context7 MCP server",
            port=port,
            sdk_mcp_server=None,
            mcp_servers={"context7": stdio_mcp_config},
            system_prompt=system_prompt,
            permission_preset=permission_preset,
        )

    def _get_skills(self) -> list[dict[str, Any]]:
        """Define Context7 agent skills for A2A discovery."""
        return [
            {
                "id": "library_docs",
                "name": "Library Documentation",
                "description": "Get up-to-date documentation for code libraries",
                "tags": ["documentation", "code", "libraries", "context7", "external"],
                "examples": [
                    "How do I use FastAPI?",
                    "What are React hooks?",
                    "Show me Pydantic validation examples",
                ],
            },
        ]

    def _get_allowed_tools(self) -> list[str]:
        """Allow Context7 MCP tools."""
        return [
            "mcp__context7__resolve-library-id",
            "mcp__context7__get-library-docs",
        ]


def main():
    """Run the Context7 Agent."""
    port = int(os.getenv("AGENT_PORT", "9004"))
    agent = Context7Agent(port=port)
    print(f"Starting Context7 Agent on port {port}...")
    print("Using real Context7 MCP server (npx @upstash/context7-mcp)")
    agent.run()


if __name__ == "__main__":
    main()

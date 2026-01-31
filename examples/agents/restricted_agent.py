"""Restricted agent for testing permission presets."""

from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from src import BaseA2AAgent
from src.security import PermissionPreset


@tool(
    "simple_echo",
    "Echo a message back",
    {"message": str},
)
async def simple_echo(args: dict[str, Any]) -> dict[str, Any]:
    """Echo a message back."""
    message = args.get("message", "")
    return {"content": [{"type": "text", "text": f"Echo: {message}"}]}


class RestrictedAgent(BaseA2AAgent):
    """Agent with restricted permissions for testing."""

    def __init__(
        self,
        port: int = 9005,
        preset: PermissionPreset = PermissionPreset.READ_ONLY,
    ):
        server = create_sdk_mcp_server(
            name="restricted_agent",
            version="1.0.0",
            tools=[simple_echo],
        )

        # System prompt that encourages reading files (which READ_ONLY allows)
        # and writing files (which READ_ONLY should block)
        super().__init__(
            name="Restricted Agent",
            description="Agent with restricted permissions for testing",
            port=port,
            sdk_mcp_server=server,
            system_prompt="""You are a restricted agent with limited permissions.
When asked to echo something, use the simple_echo tool.
When asked to read a file, try to use the Read tool.
When asked to write a file, try to use the Write tool.
Report honestly what you can and cannot do based on your permissions.""",
            permission_preset=preset,
        )

    def _get_skills(self) -> list:
        return [
            {
                "id": "echo",
                "name": "Echo",
                "description": "Echo messages back",
            }
        ]

    def _get_allowed_tools(self) -> list[str]:
        # Agent's own tools plus external tools it MIGHT use
        # The permission preset will filter external tools
        return [
            "mcp__restricted_agent__simple_echo",
            "Read",  # This will be filtered out if not allowed by preset
            "Write",  # This will be filtered out if not allowed by preset
            "Bash",  # This will be filtered out if not allowed by preset
        ]


def main():
    """Run the restricted agent."""
    import os

    # Get preset from environment
    preset_name = os.environ.get("PERMISSION_PRESET", "read_only")

    presets = {
        "full_access": PermissionPreset.FULL_ACCESS,
        "read_only": PermissionPreset.READ_ONLY,
        "communication_only": PermissionPreset.COMMUNICATION_ONLY,
    }

    preset = presets.get(preset_name, PermissionPreset.READ_ONLY)

    print(f"Starting Restricted Agent with {preset.value} permissions...")
    agent = RestrictedAgent(preset=preset)
    agent.run()


if __name__ == "__main__":
    main()

"""
Permission system for A2A agents.

Provides permission presets and handlers for controlling tool access in distributed agents.
"""

from collections.abc import Awaitable, Callable
from enum import Enum


class PermissionPreset(Enum):
    """Permission presets for agent tool access.

    Each preset defines a set of tool access rules:
    - FULL_ACCESS: All tools allowed (default for trusted agents)
    - READ_ONLY: Only read operations (Read, Glob, Grep, discover_agent)
    - COMMUNICATION_ONLY: Only A2A communication tools (query_agent, discover_agent)
    - CUSTOM: User-defined rules via custom_rules parameter
    """

    FULL_ACCESS = "full_access"
    READ_ONLY = "read_only"
    COMMUNICATION_ONLY = "communication_only"
    CUSTOM = "custom"


# Tool categories for permission presets
TOOL_CATEGORIES = {
    "read": [
        "Read",
        "Glob",
        "Grep",
        "discover_agent",  # Discovering agents is a read operation
    ],
    "communication": [
        "query_agent",
        "discover_agent",
    ],
    "write": [
        "Write",
        "Edit",
        "NotebookEdit",
    ],
    "execute": [
        "Bash",
        "Task",
    ],
}

# Preset to allowed tool patterns mapping
PRESET_ALLOWED_PATTERNS: dict[PermissionPreset, list[str]] = {
    PermissionPreset.FULL_ACCESS: ["*"],  # Allow all tools
    PermissionPreset.READ_ONLY: TOOL_CATEGORIES["read"],
    PermissionPreset.COMMUNICATION_ONLY: TOOL_CATEGORIES["communication"],
    PermissionPreset.CUSTOM: [],  # Requires custom_rules
}


class PermissionResult:
    """Result of a permission check."""

    def __init__(
        self, allowed: bool, message: str = "", updated_input: dict | None = None
    ):
        """Initialize permission result.

        Args:
            allowed: Whether the tool use is allowed
            message: Optional message (e.g., denial reason)
            updated_input: Optional modified input data (for transformations)
        """
        self.allowed = allowed
        self.message = message
        self.updated_input = updated_input


class PermissionResultAllow(PermissionResult):
    """Result indicating tool use is allowed."""

    def __init__(self, updated_input: dict | None = None):
        super().__init__(allowed=True, updated_input=updated_input)


class PermissionResultDeny(PermissionResult):
    """Result indicating tool use is denied."""

    def __init__(self, message: str):
        super().__init__(allowed=False, message=message)


# Type alias for permission handler function
PermissionHandler = Callable[[str, dict, dict], Awaitable[PermissionResult]]


def _matches_pattern(tool_name: str, pattern: str) -> bool:
    """Check if tool name matches a pattern.

    Args:
        tool_name: Full tool name (e.g., mcp__weather_agent__get_weather)
        pattern: Pattern to match (e.g., "query_agent", "*", or full name)

    Returns:
        True if the tool name matches the pattern
    """
    if pattern == "*":
        return True

    # Direct match
    if tool_name == pattern:
        return True

    # Check if pattern appears in tool name (e.g., "query_agent" in "mcp__controller__query_agent")
    if pattern in tool_name:
        return True

    # Check suffix match (tool name ends with __pattern)
    if tool_name.endswith(f"__{pattern}"):
        return True

    return False


def get_allowed_patterns(
    preset: PermissionPreset, custom_rules: list[str] | None = None
) -> list[str]:
    """Get allowed tool patterns for a preset.

    Args:
        preset: The permission preset
        custom_rules: Custom tool patterns (required for CUSTOM preset)

    Returns:
        List of allowed tool patterns
    """
    if preset == PermissionPreset.CUSTOM:
        return custom_rules or []
    return PRESET_ALLOWED_PATTERNS.get(preset, [])


async def create_permission_handler(
    preset: PermissionPreset,
    custom_rules: list[str] | None = None,
) -> PermissionHandler:
    """Create a permission handler based on preset.

    This handler can be used with Claude SDK's can_use_tool callback
    to control tool access at runtime.

    Args:
        preset: The permission preset to use
        custom_rules: Custom tool patterns (required for CUSTOM preset)

    Returns:
        Async function that checks tool permissions
    """
    allowed_patterns = get_allowed_patterns(preset, custom_rules)

    async def handler(
        tool_name: str, input_data: dict, context: dict
    ) -> PermissionResult:
        """Check if a tool can be used.

        Args:
            tool_name: Name of the tool being invoked
            input_data: Input arguments to the tool
            context: Additional context about the invocation

        Returns:
            PermissionResult indicating allow/deny
        """
        # Full access allows everything
        if preset == PermissionPreset.FULL_ACCESS:
            return PermissionResultAllow(updated_input=input_data)

        # Check against allowed patterns
        for pattern in allowed_patterns:
            if _matches_pattern(tool_name, pattern):
                return PermissionResultAllow(updated_input=input_data)

        return PermissionResultDeny(
            message=f"Tool '{tool_name}' not allowed by {preset.value} permission preset"
        )

    return handler


def is_tool_allowed(
    tool_name: str, preset: PermissionPreset, custom_rules: list[str] | None = None
) -> bool:
    """Synchronously check if a tool is allowed by a preset.

    Useful for filtering tool lists before passing to SDK.

    Args:
        tool_name: Name of the tool to check
        preset: The permission preset
        custom_rules: Custom tool patterns (for CUSTOM preset)

    Returns:
        True if the tool is allowed
    """
    if preset == PermissionPreset.FULL_ACCESS:
        return True

    allowed_patterns = get_allowed_patterns(preset, custom_rules)
    return any(_matches_pattern(tool_name, pattern) for pattern in allowed_patterns)


def filter_allowed_tools(
    tools: list[str],
    preset: PermissionPreset,
    custom_rules: list[str] | None = None,
) -> list[str]:
    """Filter a list of tools to only those allowed by the preset.

    Args:
        tools: List of tool names to filter
        preset: The permission preset
        custom_rules: Custom tool patterns (for CUSTOM preset)

    Returns:
        List of tools that are allowed
    """
    return [tool for tool in tools if is_tool_allowed(tool, preset, custom_rules)]

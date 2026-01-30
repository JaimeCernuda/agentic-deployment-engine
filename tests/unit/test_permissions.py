"""Unit tests for the permission system."""

import pytest

from src.security.permissions import (
    PRESET_ALLOWED_PATTERNS,
    TOOL_CATEGORIES,
    PermissionPreset,
    PermissionResultAllow,
    PermissionResultDeny,
    _matches_pattern,
    create_permission_handler,
    filter_allowed_tools,
    get_allowed_patterns,
    is_tool_allowed,
)


class TestPermissionPreset:
    """Tests for PermissionPreset enum."""

    def test_all_presets_defined(self) -> None:
        """Verify all expected presets exist."""
        assert PermissionPreset.FULL_ACCESS.value == "full_access"
        assert PermissionPreset.READ_ONLY.value == "read_only"
        assert PermissionPreset.COMMUNICATION_ONLY.value == "communication_only"
        assert PermissionPreset.CUSTOM.value == "custom"

    def test_presets_have_patterns(self) -> None:
        """Verify all presets have associated patterns."""
        for preset in PermissionPreset:
            assert preset in PRESET_ALLOWED_PATTERNS


class TestToolCategories:
    """Tests for tool category definitions."""

    def test_read_category(self) -> None:
        """Verify read category includes expected tools."""
        assert "Read" in TOOL_CATEGORIES["read"]
        assert "Glob" in TOOL_CATEGORIES["read"]
        assert "Grep" in TOOL_CATEGORIES["read"]
        assert "discover_agent" in TOOL_CATEGORIES["read"]

    def test_communication_category(self) -> None:
        """Verify communication category includes expected tools."""
        assert "query_agent" in TOOL_CATEGORIES["communication"]
        assert "discover_agent" in TOOL_CATEGORIES["communication"]

    def test_write_category(self) -> None:
        """Verify write category includes expected tools."""
        assert "Write" in TOOL_CATEGORIES["write"]
        assert "Edit" in TOOL_CATEGORIES["write"]

    def test_execute_category(self) -> None:
        """Verify execute category includes expected tools."""
        assert "Bash" in TOOL_CATEGORIES["execute"]
        assert "Task" in TOOL_CATEGORIES["execute"]


class TestMatchesPattern:
    """Tests for pattern matching function."""

    def test_wildcard_matches_all(self) -> None:
        """Wildcard pattern should match any tool."""
        assert _matches_pattern("mcp__weather_agent__get_weather", "*")
        assert _matches_pattern("Read", "*")
        assert _matches_pattern("any_tool_name", "*")

    def test_direct_match(self) -> None:
        """Direct match should work for exact tool names."""
        assert _matches_pattern("Read", "Read")
        assert _matches_pattern("query_agent", "query_agent")
        assert not _matches_pattern("Read", "Write")

    def test_pattern_in_tool_name(self) -> None:
        """Pattern should match if it appears in tool name."""
        assert _matches_pattern("mcp__controller_agent__query_agent", "query_agent")
        assert _matches_pattern("mcp__weather_agent__get_weather", "get_weather")
        assert not _matches_pattern("mcp__weather_agent__get_weather", "get_distance")

    def test_suffix_match(self) -> None:
        """Pattern should match tool name suffixes."""
        assert _matches_pattern("mcp__controller__query_agent", "query_agent")
        assert _matches_pattern("mcp__test__discover_agent", "discover_agent")


class TestPermissionResult:
    """Tests for permission result classes."""

    def test_allow_result(self) -> None:
        """PermissionResultAllow should indicate allowed."""
        result = PermissionResultAllow(updated_input={"key": "value"})
        assert result.allowed is True
        assert result.message == ""
        assert result.updated_input == {"key": "value"}

    def test_deny_result(self) -> None:
        """PermissionResultDeny should indicate denied."""
        result = PermissionResultDeny(message="Tool not allowed")
        assert result.allowed is False
        assert result.message == "Tool not allowed"
        assert result.updated_input is None


class TestGetAllowedPatterns:
    """Tests for get_allowed_patterns function."""

    def test_full_access_returns_wildcard(self) -> None:
        """FULL_ACCESS should return wildcard pattern."""
        patterns = get_allowed_patterns(PermissionPreset.FULL_ACCESS)
        assert patterns == ["*"]

    def test_read_only_returns_read_tools(self) -> None:
        """READ_ONLY should return read category tools."""
        patterns = get_allowed_patterns(PermissionPreset.READ_ONLY)
        assert "Read" in patterns
        assert "Glob" in patterns
        assert "discover_agent" in patterns
        assert "query_agent" not in patterns

    def test_communication_only_returns_comms_tools(self) -> None:
        """COMMUNICATION_ONLY should return communication tools."""
        patterns = get_allowed_patterns(PermissionPreset.COMMUNICATION_ONLY)
        assert "query_agent" in patterns
        assert "discover_agent" in patterns
        assert "Read" not in patterns

    def test_custom_returns_custom_rules(self) -> None:
        """CUSTOM should return provided custom rules."""
        custom = ["my_tool", "other_tool"]
        patterns = get_allowed_patterns(PermissionPreset.CUSTOM, custom)
        assert patterns == custom

    def test_custom_without_rules_returns_empty(self) -> None:
        """CUSTOM without rules should return empty list."""
        patterns = get_allowed_patterns(PermissionPreset.CUSTOM)
        assert patterns == []


class TestIsToolAllowed:
    """Tests for synchronous tool permission check."""

    def test_full_access_allows_all(self) -> None:
        """FULL_ACCESS should allow any tool."""
        assert is_tool_allowed("mcp__agent__any_tool", PermissionPreset.FULL_ACCESS)
        assert is_tool_allowed("Read", PermissionPreset.FULL_ACCESS)
        assert is_tool_allowed("Bash", PermissionPreset.FULL_ACCESS)

    def test_read_only_allows_read_tools(self) -> None:
        """READ_ONLY should allow only read tools."""
        assert is_tool_allowed("Read", PermissionPreset.READ_ONLY)
        assert is_tool_allowed("Glob", PermissionPreset.READ_ONLY)
        assert is_tool_allowed("mcp__agent__discover_agent", PermissionPreset.READ_ONLY)
        assert not is_tool_allowed("Write", PermissionPreset.READ_ONLY)
        assert not is_tool_allowed(
            "mcp__agent__query_agent", PermissionPreset.READ_ONLY
        )

    def test_communication_only_allows_comms_tools(self) -> None:
        """COMMUNICATION_ONLY should allow only communication tools."""
        assert is_tool_allowed(
            "mcp__controller__query_agent", PermissionPreset.COMMUNICATION_ONLY
        )
        assert is_tool_allowed(
            "mcp__controller__discover_agent", PermissionPreset.COMMUNICATION_ONLY
        )
        assert not is_tool_allowed("Read", PermissionPreset.COMMUNICATION_ONLY)
        assert not is_tool_allowed("Bash", PermissionPreset.COMMUNICATION_ONLY)

    def test_custom_allows_specified_tools(self) -> None:
        """CUSTOM should allow only specified tools."""
        custom = ["my_tool", "query_agent"]
        assert is_tool_allowed("my_tool", PermissionPreset.CUSTOM, custom)
        assert is_tool_allowed(
            "mcp__agent__query_agent", PermissionPreset.CUSTOM, custom
        )
        assert not is_tool_allowed("other_tool", PermissionPreset.CUSTOM, custom)


class TestFilterAllowedTools:
    """Tests for tool list filtering."""

    def test_full_access_keeps_all(self) -> None:
        """FULL_ACCESS should keep all tools."""
        tools = ["Read", "Write", "mcp__agent__query_agent", "Bash"]
        filtered = filter_allowed_tools(tools, PermissionPreset.FULL_ACCESS)
        assert filtered == tools

    def test_read_only_filters_write_tools(self) -> None:
        """READ_ONLY should filter out write/execute tools."""
        tools = ["Read", "Write", "Glob", "Bash", "mcp__agent__discover_agent"]
        filtered = filter_allowed_tools(tools, PermissionPreset.READ_ONLY)
        assert "Read" in filtered
        assert "Glob" in filtered
        assert "mcp__agent__discover_agent" in filtered
        assert "Write" not in filtered
        assert "Bash" not in filtered

    def test_communication_only_filters_non_comms(self) -> None:
        """COMMUNICATION_ONLY should filter non-communication tools."""
        tools = [
            "mcp__controller__query_agent",
            "mcp__controller__discover_agent",
            "Read",
            "mcp__weather__get_weather",
        ]
        filtered = filter_allowed_tools(tools, PermissionPreset.COMMUNICATION_ONLY)
        assert "mcp__controller__query_agent" in filtered
        assert "mcp__controller__discover_agent" in filtered
        assert "Read" not in filtered
        assert "mcp__weather__get_weather" not in filtered

    def test_empty_list_returns_empty(self) -> None:
        """Empty tool list should return empty."""
        filtered = filter_allowed_tools([], PermissionPreset.FULL_ACCESS)
        assert filtered == []


@pytest.mark.asyncio
class TestCreatePermissionHandler:
    """Tests for async permission handler factory."""

    async def test_full_access_handler_allows_all(self) -> None:
        """FULL_ACCESS handler should allow any tool."""
        handler = await create_permission_handler(PermissionPreset.FULL_ACCESS)
        result = await handler("any_tool", {"input": "data"}, {})
        assert result.allowed is True
        assert result.updated_input == {"input": "data"}

    async def test_read_only_handler_allows_read_tools(self) -> None:
        """READ_ONLY handler should allow read tools."""
        handler = await create_permission_handler(PermissionPreset.READ_ONLY)

        read_result = await handler("Read", {}, {})
        assert read_result.allowed is True

        glob_result = await handler("Glob", {}, {})
        assert glob_result.allowed is True

    async def test_read_only_handler_denies_write_tools(self) -> None:
        """READ_ONLY handler should deny write tools."""
        handler = await create_permission_handler(PermissionPreset.READ_ONLY)

        write_result = await handler("Write", {}, {})
        assert write_result.allowed is False
        assert "not allowed" in write_result.message

        bash_result = await handler("Bash", {}, {})
        assert bash_result.allowed is False

    async def test_communication_handler_allows_query(self) -> None:
        """COMMUNICATION_ONLY handler should allow query_agent."""
        handler = await create_permission_handler(PermissionPreset.COMMUNICATION_ONLY)

        query_result = await handler(
            "mcp__controller__query_agent",
            {"agent_url": "http://localhost:9001", "query": "test"},
            {},
        )
        assert query_result.allowed is True

    async def test_communication_handler_denies_read(self) -> None:
        """COMMUNICATION_ONLY handler should deny Read tool."""
        handler = await create_permission_handler(PermissionPreset.COMMUNICATION_ONLY)

        read_result = await handler("Read", {}, {})
        assert read_result.allowed is False

    async def test_custom_handler_with_rules(self) -> None:
        """CUSTOM handler should respect custom rules."""
        handler = await create_permission_handler(
            PermissionPreset.CUSTOM, custom_rules=["my_special_tool", "query_agent"]
        )

        special_result = await handler("my_special_tool", {}, {})
        assert special_result.allowed is True

        query_result = await handler("mcp__agent__query_agent", {}, {})
        assert query_result.allowed is True

        other_result = await handler("other_tool", {}, {})
        assert other_result.allowed is False

    async def test_handler_preserves_input_data(self) -> None:
        """Handler should preserve input data in result."""
        handler = await create_permission_handler(PermissionPreset.FULL_ACCESS)
        input_data = {"key1": "value1", "key2": 123}
        result = await handler("any_tool", input_data, {})
        assert result.updated_input == input_data


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios."""

    def test_controller_agent_tools_with_communication_preset(self) -> None:
        """Controller agent tools should be allowed with COMMUNICATION_ONLY preset."""
        controller_tools = [
            "mcp__controller_agent__query_agent",
            "mcp__controller_agent__discover_agent",
        ]
        filtered = filter_allowed_tools(
            controller_tools, PermissionPreset.COMMUNICATION_ONLY
        )
        assert len(filtered) == 2
        assert "mcp__controller_agent__query_agent" in filtered
        assert "mcp__controller_agent__discover_agent" in filtered

    def test_weather_agent_tools_not_allowed_with_communication_preset(self) -> None:
        """Weather agent domain tools should not be allowed with COMMUNICATION_ONLY preset."""
        weather_tools = [
            "mcp__weather_agent__get_weather",
            "mcp__weather_agent__get_locations",
        ]
        filtered = filter_allowed_tools(
            weather_tools, PermissionPreset.COMMUNICATION_ONLY
        )
        assert len(filtered) == 0

    def test_mixed_tools_filtered_correctly(self) -> None:
        """Mixed tool list should be filtered correctly."""
        tools = [
            "mcp__controller__query_agent",
            "mcp__controller__discover_agent",
            "mcp__weather__get_weather",
            "Read",
            "Write",
            "Bash",
        ]

        # COMMUNICATION_ONLY should only keep A2A tools
        comms_filtered = filter_allowed_tools(
            tools, PermissionPreset.COMMUNICATION_ONLY
        )
        assert "mcp__controller__query_agent" in comms_filtered
        assert "mcp__controller__discover_agent" in comms_filtered
        assert len(comms_filtered) == 2

        # READ_ONLY should keep Read and discover_agent
        read_filtered = filter_allowed_tools(tools, PermissionPreset.READ_ONLY)
        assert "Read" in read_filtered
        assert "mcp__controller__discover_agent" in read_filtered
        assert "Write" not in read_filtered
        assert "Bash" not in read_filtered

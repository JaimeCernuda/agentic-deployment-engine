# SDK MCP Tools Issue Analysis

## Problem Summary

SDK MCP tools are NOT being invoked by agents, despite all tests passing. Agents fall back to reading source code files and calculating results manually instead of using the configured SDK MCP tools.

## Root Cause Identified

**Server Name Mismatch**: The SDK MCP server names did not match the dictionary keys used to register them in `ClaudeAgentOptions`.

### The Issue

In `weather_agent.py` and `maps_agent.py`:
```python
# BEFORE (broken):
weather_sdk_server = create_sdk_mcp_server(
    name="weather",  # ← Server name
    ...
)
```

In `base_a2a_agent.py:84-86`:
```python
if sdk_mcp_server:
    server_key = self.name.lower().replace(" ", "_")  # "Weather Agent" → "weather_agent"
    mcp_servers[server_key] = sdk_mcp_server
```

According to claude-agent-sdk documentation:
> **Tool naming uses the DICTIONARY KEY, not server name**: `mcp__{dict_key}__{tool_name}`

### Expected vs Actual Tool Names

| Component | Expected (from `_get_allowed_tools()`) | Actual (from SDK server name) |
|-----------|---------------------------------------|-------------------------------|
| Weather   | `mcp__weather_agent__get_weather`     | `mcp__weather__get_weather`   |
| Weather   | `mcp__weather_agent__get_locations`   | `mcp__weather__get_locations` |
| Maps      | `mcp__maps_agent__get_distance`       | `mcp__maps__get_distance`     |
| Maps      | `mcp__maps_agent__get_cities`         | `mcp__maps__get_cities`       |

This mismatch meant Claude couldn't find the tools and fell back to alternative methods.

## Fix Applied

Updated SDK server names to match the dictionary keys:

**weather_agent.py:21**:
```python
# AFTER (fixed):
weather_sdk_server = create_sdk_mcp_server(
    name="weather_agent",  # Must match self.name.lower().replace(" ", "_")
    version="1.0.0",
    tools=[get_weather, get_locations]
)
```

**maps_agent.py:21**:
```python
# AFTER (fixed):
maps_sdk_server = create_sdk_mcp_server(
    name="maps_agent",  # Must match self.name.lower().replace(" ", "_")
    version="1.0.0",
    tools=[get_distance, get_cities]
)
```

## Evidence from Previous Logs

### Maps Agent Log (Before Fix)

From `logs/maps_agent.log` (lines 19-87):

1. **Attempt to use SDK tool** (Message 3, line 24):
   ```
   Tool: mcp__maps_agent__get_distance
   Input: {'origin': 'Tokyo', 'destination': 'London', 'unit': 'kilometers'}
   ```

2. **Tool invocation failed silently** - No tool result logged

3. **Agent fell back to alternative methods** (Messages 6-22):
   - Bash tool: Attempted to curl itself (recursive, wrong)
   - WebFetch tool: Tried to fetch from localhost
   - Read tool: Read `maps_agent.py` source code
   - Read tool: Read `maps_tools.py` source code
   - Manual calculation: Extracted coordinates from source and calculated distance

4. **Final result** (line 87):
   ```
   Query completed. Messages: 23, Tools used: 7, Response: 1030 chars
   ```
   - 7 tools used, BUT NOT the SDK MCP tool
   - Agent read source code and manually calculated the answer

### Weather Agent Log (Before Fix)

Weather Agent showed NO query handling logs despite Controller Agent successfully curling it. This suggests the Weather Agent responded but through a different code path.

## Why Tests Were Passing

Tests passed because agents were **getting correct answers**, just through the **wrong mechanism**:

- Instead of calling `mcp__maps_agent__get_distance` tool
- Agent read `maps_tools.py` file
- Extracted `CITY_COORDINATES` data
- Manually applied `haversine_distance()` formula
- Returned correct calculated distance

The **results were correct**, but the **method was completely wrong**.

## Testing the Fix

After applying the fix, need to verify:

1. **Start fresh agents**:
   ```bash
   pkill -f 'weather_agent|maps_agent|controller_agent'
   rm -rf logs/*.log
   uv run start-all
   ```

2. **Run integration tests**:
   ```bash
   uv run pytest tests/test_integration.py -v
   ```

3. **Check logs for SDK tool usage**:
   ```bash
   grep -A 2 "Tool: mcp__" logs/maps_agent.log logs/weather_agent.log
   ```

   Should see:
   ```
   Tool: mcp__maps_agent__get_distance
   Input: {...}
   [Next message should be ToolResultBlock, not Read/Bash]
   ```

4. **Verify NO file reading**:
   ```bash
   grep "Read.*tools.py" logs/*.log
   ```

   Should return NO results (agents shouldn't read source files anymore)

## Documentation Update Needed

The `CLAUDE.md` file correctly documents this pattern, but should emphasize it more:

```markdown
**Critical SDK MCP Server Facts:**
1. SDK server created with `create_sdk_mcp_server(name="server_name", tools=[...])`
2. Server passed to `ClaudeCodeOptions(mcp_servers={"dict_key": sdk_server})`
3. **Tool naming uses the DICTIONARY KEY, not server name**: `mcp__{dict_key}__{tool_name}`
4. Example: If `mcp_servers={"mytools": server}`, tool name is `mcp__mytools__greet`

**In this codebase:**
- Weather Agent: `mcp_servers={"weather_agent": sdk_server}` → tools are `mcp__weather_agent__*`
- Maps Agent: `mcp_servers={"maps_agent": sdk_server}` → tools are `mcp__maps_agent__*`
- Dictionary key comes from `self.name.lower().replace(" ", "_")` in BaseA2AAgent
```

## Lessons Learned

1. **Tool naming is critical**: SDK MCP tools use the dictionary key, not the server name
2. **Silent failures are dangerous**: Tool invocation failures didn't raise errors, agents just fell back
3. **Test what you think you're testing**: Tests passed but weren't actually testing SDK tool invocation
4. **Log analysis is essential**: Detailed logs revealed the agents were reading source code
5. **User intuition was correct**: User suspected "weird stuff" - agents WERE doing weird stuff

## Next Steps

1. ✅ Fixed SDK server names to match dictionary keys
2. ⏳ Restart agents with fix applied
3. ⏳ Run integration tests to verify SDK tools are actually invoked
4. ⏳ Analyze logs to confirm NO source file reading
5. ⏳ Update `FINAL_STATUS.md` with findings and fix details
6. ⏳ Consider adding test to verify SDK tool invocation (not just correct results)

## Files Modified

- `weather_agent.py:21` - Changed server name from `"weather"` to `"weather_agent"`
- `maps_agent.py:21` - Changed server name from `"maps"` to `"maps_agent"`
- `SDK_TOOLS_ISSUE_ANALYSIS.md` - This document

## Status

**Issue**: IDENTIFIED and FIXED
**Testing**: PENDING (need to restart agents and verify)
**Documentation**: PENDING (need to update FINAL_STATUS.md)

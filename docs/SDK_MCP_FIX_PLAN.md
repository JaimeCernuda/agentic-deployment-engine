# SDK MCP Server Fix Plan

## Context & Problem Statement

**Goal:** Achieve fastest possible MCP tool calls for multi-agent system (user → controller → weather/maps agents)

**Performance Comparison:**
- **SDK MCP (in-process):** Direct Python function calls, no IPC, no subprocess overhead → **FASTEST**
- **Subprocess MCP:** Requires process spawning, IPC over stdio, JSON serialization → **MUCH SLOWER**

**Current Issue:**
- SDK MCP servers (created with `create_sdk_mcp_server()`) don't work with Claude Code CLI
- GitHub Issue: https://github.com/anthropics/claude-agent-sdk-python/issues/207
- Root cause: CLI doesn't recognize `{"type": "sdk"}` server configurations
- SDK tries to send SDK server config to CLI, but CLI only accepts stdio/sse/http types

**Versions:**
- Target: `claude-agent-sdk==0.1.0` (latest, renamed from claude-code-sdk)
- Claude Code CLI: 2.0.8
- Python: 3.10+

## The Fix

**Location:** `.venv/lib/python3.12/site-packages/claude_agent_sdk/_internal/transport/subprocess_cli.py`

**What to change:** In the `_build_command()` method, when processing `mcp_servers` configuration:

**Current behavior (BROKEN):**
```python
if isinstance(config, dict) and config.get("type") == "sdk":
    # Strips 'instance' field and sends to CLI
    sdk_config = {k: v for k, v in config.items() if k != "instance"}
    servers_for_cli[name] = sdk_config  # ❌ CLI rejects this
```

**Fixed behavior (WORKING):**
```python
if isinstance(config, dict) and config.get("type") == "sdk":
    # SDK servers are handled in-process, don't send to CLI
    continue  # ✅ Skip SDK servers entirely
```

**Why this works:**
1. SDK servers are already extracted in `client.py` and passed to `Query` class
2. `Query` handles SDK servers entirely in Python (via `sdk_mcp_servers` parameter)
3. CLI never needs to know about SDK servers - they're not subprocess-based
4. Only stdio/sse/http servers should go to CLI

## Execution Steps

1. **Upgrade to claude-agent-sdk 0.1.0**
   ```bash
   # Update pyproject.toml
   dependencies = ["claude-agent-sdk==0.1.0", ...]
   uv sync
   ```

2. **Update imports in all files**
   - `claude_code_sdk` → `claude_agent_sdk`
   - `ClaudeCodeOptions` → `ClaudeAgentOptions`

3. **Apply the fix to subprocess_cli.py**
   - File: `.venv/lib/python3.12/site-packages/claude_agent_sdk/_internal/transport/subprocess_cli.py`
   - Function: `_build_command()`
   - Lines: ~131-136
   - Change: Add `continue` to skip SDK servers instead of sending stripped config

4. **Test SDK MCP servers work**
   ```python
   server = create_sdk_mcp_server(name="test", tools=[...])
   options = ClaudeAgentOptions(
       mcp_servers={"tools": server},
       allowed_tools=["mcp__tools__tool_name"]
   )
   async with ClaudeSDKClient(options=options) as client:
       await client.query("test query")
       async for msg in client.receive_response():
           print(msg)
   ```

5. **Verify all three agents**
   - Weather Agent: SDK MCP tools (get_weather, get_locations)
   - Maps Agent: SDK MCP tools (get_distance, get_cities)
   - Controller Agent: Uses Bash tool to make HTTP calls to other agents
   - Test flow: User → Controller → Weather/Maps → back to Controller

## Expected Outcomes

✅ SDK MCP servers work with in-process tool calls (fastest performance)
✅ No subprocess overhead for tool execution
✅ Agents can use Claude intelligence + fast tools
✅ A2A protocol works for inter-agent communication

## Why This Hack is Necessary

- Official SDK has a bug (issue #207)
- No official fix/response from maintainers yet
- SDK incorrectly tries to send SDK servers to CLI
- CLI correctly rejects them (it's not designed to handle in-process Python objects)
- Fix is minimal (one line change: add `continue`)
- Preserves intended architecture: SDK servers stay Python-side, CLI handles external servers

## Alternative Approaches Considered

1. **Use subprocess MCP servers** - Works but MUCH slower (rejected)
2. **Remove ClaudeSDKClient entirely** - Loses AI intelligence (rejected)
3. **Wait for official fix** - Timeline unknown, blocking project (rejected)
4. **This hack** - Minimal change, achieves performance goals ✅

## Post-Compaction Recovery

If conversation is compacted, use this plan to:
1. Understand why the fix was needed
2. Re-apply the fix to `.venv/lib/python3.12/site-packages/claude_agent_sdk/_internal/transport/subprocess_cli.py`
3. Verify tests pass
4. Continue development

The fix is a one-line change but requires understanding the SDK internals and why SDK servers shouldn't be sent to the CLI.

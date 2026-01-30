# Exploration Session Scratch File

## Current Iteration: 1
**Started:** 2026-01-29 23:48
**Focus:** Priority 1 - Core Platform Usage

---

## Iteration 1: Core Platform Startup and Query Flow

### What I Tested
1. Agent startup with `uv run start-all`
2. Individual agent startup with `uv run weather-agent`
3. Health check endpoints
4. A2A discovery endpoints
5. Query flow through agents
6. Multi-agent coordination (controller → weather)

### Observations

#### Agent Startup
- **Works**: Agents start successfully and listen on configured ports (9000, 9001, 9002)
- **Works**: Log files are created per-agent in `src/agents/logs/`
- **Works**: Controller discovers connected agents at startup and updates system prompt
- **Issue Fixed**: `start-all` was capturing stdout/stderr to pipes, losing all console output
- **Issue Fixed**: "Event loop is closed" error during cleanup (registry.py)

#### Query Flow
- **Works**: Health endpoints return correct JSON: `{"status":"healthy","agent":"Weather Agent"}`
- **Works**: A2A discovery endpoint (`.well-known/agent-configuration`) returns complete agent info
- **Works**: Individual agent queries work - weather agent correctly uses MCP tools
- **Works**: Multi-agent queries work - controller routes to weather agent via A2A

#### Log Quality
- **Good**: Detailed DEBUG logs show message flow, tool calls, and results
- **Good**: Pool initialization logs show client connections
- **Example log flow**:
  ```
  Handling query: What is the weather in Tokyo?
  Initializing client pool with 3 clients...
  Pool client 1/3 connected
  ...
  Message 2: AssistantMessage
    Content block 0: ToolUseBlock
    Tool: mcp__weather_agent__get_weather
    Input: {'location': 'Tokyo', 'units': 'metric'}
  Message 3: UserMessage
    Content block 0: ToolResultBlock
    Result content: [{'type': 'text', 'text': 'Weather in Tokyo: 22.5°C, Partly cloudy...'}]
  Query completed. Messages: 5, Tools used: 1, Response: 208 chars
  ```

#### Performance
- Client pool initialization takes ~5-6 seconds (3 clients, ~2s each)
- Individual queries after pool init are fast (~3-4 seconds for tool call + response)

### Bugs Found and Fixed

1. **Event loop closed error during cleanup**
   - File: `src/agents/registry.py`
   - Problem: `await self._client.aclose()` throws RuntimeError when event loop is already closed
   - Fix: Added try/except to handle gracefully

2. **start-all suppresses agent output**
   - File: `src/start_all.py`
   - Problem: `stdout=subprocess.PIPE, stderr=subprocess.PIPE` captures and discards agent output
   - Fix: Removed pipe redirection so output is visible

### Questions Raised
- Why does client pool initialization take ~2s per client? Is this connection establishment or something else?
- Should the pool size be configurable?
- First query sometimes hangs - need to investigate if related to timing

---

## Issues Found (To Create)

None yet - the issues found so far were bugs that were fixed.

---

## Next Steps
- [ ] Run tests to verify fixes don't break anything
- [ ] Test deployment CLI (`uv run deploy validate/plan/start`)
- [ ] Test SSH deployment
- [ ] Create a new agent to test agent creation workflow
- [ ] Test permission presets

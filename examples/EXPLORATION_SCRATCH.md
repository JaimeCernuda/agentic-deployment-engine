# Exploration Session Scratch File

## Current Iteration: 2
**Started:** 2026-01-29 23:48
**Updated:** 2026-01-30 00:15
**Focus:** Priority 1 (done) → Priority 2 (in progress)

---

## Iteration 1: Core Platform Startup and Query Flow ✅

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
   - Commit: 4013721

2. **start-all suppresses agent output**
   - File: `src/start_all.py`
   - Problem: `stdout=subprocess.PIPE, stderr=subprocess.PIPE` captures and discards agent output
   - Fix: Removed pipe redirection so output is visible
   - Commit: 4013721

---

## Iteration 2: Deployment CLI Testing ✅

### What I Tested
1. `uv run deploy validate <job.yaml>` - validation
2. `uv run deploy plan <job.yaml>` - dry run planning
3. `uv run deploy start <job.yaml>` - actual deployment
4. `uv run deploy status <job-name>` - status monitoring
5. `uv run deploy stop <job-name>` - stopping deployment
6. SSH deployment to homelab

### Observations

#### Deployment CLI
- **Works**: Validate command correctly validates YAML schema
- **Works**: Plan command shows deployment stages, agent URLs, and connections
- **Works**: Start command deploys agents in correct order (spokes before hub)
- **Works**: Status command shows real-time agent health with PID info
- **Works**: Stop command terminates all agents cleanly

#### SSH Deployment
- **Limited**: localhost doesn't have SSH server (Windows)
- **Limited**: homelab has Python 3.9.2, needs 3.11+ for this framework
- **Works**: SSH connectivity test to homelab successful
- **Works**: Job validation and planning works for SSH jobs

### Example CLI Output (Plan)
```
Deployment Plan for simple-weather-workflow
        Deployment Stages
+-------------------------------+
| Stage | Agents        | Count |
|-------+---------------+-------|
| 1     | weather, maps | 2     |
| 2     | controller    | 1     |
+-------------------------------+
```

### Example CLI Output (Status)
```
+-------------------------------- Job Status ---------------------------------+
| Job: simple-weather-workflow                                                |
| Status: running                                                             |
+-----------------------------------------------------------------------------+
                           Agent Status
+----------------------------------------------------------------+
| Agent ID   | URL                   | PID   | Status  | Health  |
|------------+-----------------------+-------+---------+---------|
| weather    | http://localhost:9001 | 61112 | healthy | healthy |
| maps       | http://localhost:9002 | 31868 | healthy | healthy |
| controller | http://localhost:9000 | 40368 | healthy | healthy |
+----------------------------------------------------------------+
```

---

## Iteration 3: Create New Agent (IN PROGRESS)

### Goal
Create a meaningful new agent (stock agent) to test the agent creation workflow.

### Steps
1. Create MCP tools in `examples/tools/stock_tools.py`
2. Create agent class in `examples/agents/stock_agent.py`
3. Add entry point to `pyproject.toml`
4. Create job YAML for the new agent
5. Test deployment

---

## Issues Found (To Create)

### Feature Request: SSH deployment needs Python version check
- Currently no warning if remote host has incompatible Python
- Could check `python3 --version` during plan phase

---

## Progress Checklist

### Priority 1: Core Platform Usage ✅
- [x] Agent Startup
- [x] Query Flow
- [x] Agent Discovery
- [x] Health Checks
- [x] Deployment CLI

### Priority 2: Create New Agents (IN PROGRESS)
- [ ] Create stock tools
- [ ] Create stock agent
- [ ] Create job YAML
- [ ] Test deployment

### Priority 3-8: TODO
- [ ] Multi-Agent Scenarios
- [ ] Deployment & Scaling (partial - SSH limited)
- [ ] Security & Permissions
- [ ] Observability
- [ ] Backends & Performance
- [ ] Edge Cases & Failures

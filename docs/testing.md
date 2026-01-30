# Testing

This guide covers the test suite structure, how to run tests, and how to write new tests.

## Overview

Tests are organized into three categories:

| Directory | Purpose | Speed |
|-----------|---------|-------|
| `tests/unit/` | Isolated component tests with mocks | Fast |
| `tests/integration/` | Component coordination tests | Medium |
| `tests/usability/` | End-to-end user workflow tests | Slow |

## Running tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run by category
uv run pytest tests/unit/ -v          # Fast, mocked
uv run pytest tests/integration/ -v   # Component coordination
uv run pytest tests/usability/ -v     # End-to-end

# Run with coverage
uv run pytest tests/ --cov=src --cov-report=term-missing
```

## Test structure

## Log Locations

All agent logs are written to: `src/logs/`

| Agent | Log File |
|-------|----------|
| Controller Agent | `src/logs/controller_agent.log` |
| Weather Agent | `src/logs/weather_agent.log` |
| Maps Agent | `src/logs/maps_agent.log` |

### Verifying Full Message Logging

Check logs to ensure messages are NOT truncated (should show full content, not ending in `...` at 200 chars):

```bash
# Check recent log entries
tail -50 src/logs/controller_agent.log

# Search for tool inputs (should show full JSON)
grep "Input:" src/logs/weather_agent.log | tail -5

# Check query completion summary
grep "Query completed" src/logs/controller_agent.log | tail -5
# Expected format: "Query completed. Messages: N, Tools used: M, Response: X chars"
```

---

## Test Files Summary

| Test File | Tests | Purpose | Agents Used |
|-----------|-------|---------|-------------|
| `test_backends.py` | 12 | Backend factory and configuration | None (unit tests) |
| `test_observability.py` | 13 | Log configuration and truncation | None (unit tests) |
| `test_tool_calls.py` | 6 | Verify agents actually use their tools | All (Weather, Maps, Controller) |
| `test_ssh_deployment.py` | 1 | SSH deployment to localhost | All via SSH |
| `test_complete_system.py` | 1 | Full end-to-end system validation | All |
| `test_job_deployment.py` | Various | Job loading and deployment | All |
| `test_scenarios.py` | Various | User scenario testing | Various |

---

## Detailed Test Descriptions

### 1. test_backends.py (12 tests)

**Purpose**: Verify backend factory creates correct backend types and configuration is handled properly.

**Agents Used**: None (pure unit tests)

**How to Run**:
```bash
uv run pytest tests/usability/test_backends.py -v
```

#### Tests:

| Test | Input | Expected Output |
|------|-------|-----------------|
| `test_creates_claude_backend_by_default` | `AGENT_BACKEND_TYPE=claude` | Backend with `name="claude-agent-sdk"` |
| `test_creates_gemini_backend_directly` | `GeminiCLIBackend(config)` | Backend with `name="gemini-cli"` |
| `test_creates_crewai_backend_directly` | `CrewAIBackend(config, ollama_model="llama3.2")` | Backend with `name="crewai"`, model="llama3.2" |
| `test_unknown_backend_defaults_to_claude` | `AGENT_BACKEND_TYPE=unknown` | Falls back to Claude backend |
| `test_backend_with_custom_model` | `model="gemini-2.0-flash"` | `backend.model == "gemini-2.0-flash"` |
| `test_backend_with_yolo_disabled` | `yolo_mode=False` | `backend.yolo_mode == False` |
| `test_backend_with_custom_ollama_model` | `ollama_model="llama3.2"` | `backend.ollama_model == "llama3.2"` |
| `test_backend_with_custom_ollama_url` | `ollama_base_url="http://ollama:11434"` | Custom URL used |
| `test_config_with_all_fields` | Full BackendConfig | All fields preserved |
| `test_config_with_minimal_fields` | `BackendConfig(name="minimal")` | Defaults applied |

---

### 2. test_observability.py (13 tests)

**Purpose**: Verify log configuration, truncation settings, backend config, and OpenTelemetry settings.

**Agents Used**: None (pure unit tests)

**How to Run**:
```bash
uv run pytest tests/usability/test_observability.py -v
```

#### Tests:

| Test | Input | Expected Output |
|------|-------|-----------------|
| `test_default_log_max_content_length` | Default settings | `log_max_content_length == 2000` |
| `test_log_max_content_length_configurable` | `AGENT_LOG_MAX_CONTENT_LENGTH=5000` | Value is 5000 |
| `test_log_max_content_length_zero_means_unlimited` | `AGENT_LOG_MAX_CONTENT_LENGTH=0` | Value is 0 (unlimited) |
| `test_truncation_at_limit` | 100 chars at limit 100 | No truncation |
| `test_truncation_over_limit` | 150 chars at limit 100 | Truncated to 103 chars (`...`) |
| `test_truncation_disabled_with_zero` | 10000 chars, limit 0 | No truncation |
| `test_default_backend_type` | Default | `backend_type == "claude"` |
| `test_backend_type_configurable` | `AGENT_BACKEND_TYPE=gemini` | Value is "gemini" |
| `test_ollama_model_configurable` | `AGENT_OLLAMA_MODEL=mistral` | Value is "mistral" |
| `test_ollama_base_url_configurable` | `AGENT_OLLAMA_BASE_URL=http://remote:11434` | Custom URL |
| `test_otel_disabled_by_default` | Default | `otel_enabled == False` |
| `test_otel_can_be_enabled` | `AGENT_OTEL_ENABLED=true` | `otel_enabled == True` |
| `test_otel_endpoint_configurable` | `AGENT_OTEL_ENDPOINT=http://jaeger:4317` | Custom endpoint |

---

### 3. test_tool_calls.py (6 tests)

**Purpose**: Verify that agents actually USE their MCP tools when responding to queries (not just respond without tool usage).

**Agents Used**: All (Weather, Maps, Controller)

**Log Files to Check**:
- `src/logs/weather_agent.log` - Should show `Tool: mcp__weather_agent__get_weather`
- `src/logs/maps_agent.log` - Should show `Tool: mcp__maps_agent__get_distance`
- `src/logs/controller_agent.log` - Should show `Tool: mcp__controller_agent__query_agent`

**How to Run**:
```bash
uv run pytest tests/usability/test_tool_calls.py -v --tb=short
```

#### Tests:

| Test | Query | Expected Log Output |
|------|-------|---------------------|
| `test_weather_agent_uses_tools` | "What is the weather in Tokyo?" | `Tools used: N` where N > 0 |
| `test_controller_agent_uses_a2a_tools` | "What is the weather in Tokyo? Please use the weather agent." | `mcp__controller_agent__query_agent` called |
| `test_maps_agent_uses_tools` | "What is the distance from Tokyo to London?" | `Tools used: N` where N > 0 |
| `test_tool_naming_convention` | "What is the weather in Tokyo?" | Log shows `mcp__weather_agent__` prefix |
| `test_all_agents_use_tools` | Multiple queries to all agents | All agents report Tools used > 0 |

#### How to Verify in Logs:

```bash
# Check weather agent used tools
grep "Tools used:" src/logs/weather_agent.log | tail -5
# Expected: "Query completed. Messages: N, Tools used: 2, Response: X chars"

# Check specific tool was called
grep "Tool: mcp__weather_agent__get_weather" src/logs/weather_agent.log | tail -3

# Verify input was logged (not truncated)
grep -A1 "Tool: mcp__weather_agent__get_weather" src/logs/weather_agent.log | tail -4
# Should show full: Input: {'location': 'Tokyo', 'units': 'metric'}
```

---

### 4. test_ssh_deployment.py (1 test)

**Purpose**: Test deploying agents via SSH to localhost (requires SSH server setup).

**Agents Used**: All (deployed via SSH)

**Prerequisites**:
```bash
# Install SSH server
sudo apt-get install openssh-server  # Ubuntu/Debian
# OR
sudo yum install openssh-server      # CentOS/RHEL

# Start SSH
sudo systemctl start sshd

# Setup passwordless SSH
ssh-keygen -t rsa -N '' -f ~/.ssh/id_rsa
cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# Test
ssh localhost whoami
```

**How to Run**:
```bash
uv run pytest tests/usability/test_ssh_deployment.py -v
# OR run directly
uv run python tests/usability/test_ssh_deployment.py
```

**Input**: Job file `examples/jobs/ssh-localhost.yaml`

**Expected Output**:
```
1. Checking SSH setup... ✓ SSH to localhost available
2. Loading SSH job definition... ✓ Loaded: ssh-localhost-test
3. Generating deployment plan... ✓ Stages: 2
4. Deploying agents via SSH... ✓ Deployed: <job-id>
5. Testing agent health...
   ✓ weather (http://localhost:9001): healthy
   ✓ maps (http://localhost:9002): healthy
   ✓ controller (http://localhost:9000): healthy
6. Agents running. Waiting 5 seconds...
7. Stopping agents... ✓ Agents stopped
```

---

### 5. test_complete_system.py (1 comprehensive test)

**Purpose**: End-to-end validation of the complete job deployment system.

**Agents Used**: All

**How to Run**:
```bash
uv run pytest tests/usability/test_complete_system.py -v
# OR run directly
uv run python tests/usability/test_complete_system.py
```

**Tests Performed**:

1. **Local Deployment** - Deploy `simple-weather.yaml` via subprocess
2. **SSH Deployment Validation** - Validate `ssh-localhost.yaml` configuration
3. **Multi-Topology Validation** - Validate all topology examples:
   - `simple-weather.yaml` (hub-spoke)
   - `pipeline.yaml` (pipeline)
   - `distributed-dag.yaml` (dag)
   - `collaborative-mesh.yaml` (mesh)
   - `hierarchical-tree.yaml` (hierarchical)
   - `ssh-localhost.yaml` (hub-spoke SSH)
   - `ssh-multi-host.yaml` (multi-host)
4. **Validation Features** - DAG cycle detection, port conflicts, etc.

**Expected Output**:
```
✓ Local deployment: Working
✓ SSH deployment validation: Working
✓ All topology patterns: Validated
✓ Validation features: Working
🎉 All tests passed!
```

---

## Manual Reproduction Guide

### Test 1: Basic Weather Query

```bash
# Start weather agent
.venv/Scripts/python.exe -m agents.weather_agent &

# Wait for startup
sleep 5

# Query
curl -X POST http://localhost:9001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in Tokyo?"}'

# Check logs for tool usage
grep "Tool:" src/logs/weather_agent.log | tail -5
grep "Tools used:" src/logs/weather_agent.log | tail -1
```

### Test 2: Multi-Agent Coordination

```bash
# Start all agents
.venv/Scripts/python.exe -m agents.weather_agent &
.venv/Scripts/python.exe -m agents.maps_agent &
.venv/Scripts/python.exe -m agents.controller_agent &

# Wait for startup
sleep 8

# Query controller
curl -X POST http://localhost:9000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in Paris and how far is it from London?"}'

# Check controller logs for A2A calls
grep "query_agent" src/logs/controller_agent.log | tail -5

# Check full input/output logging (not truncated)
grep -A2 "Tool:" src/logs/controller_agent.log | tail -10
```

### Test 3: Backend Switching

```bash
# Test Gemini CLI backend
export AGENT_BACKEND_TYPE=gemini
.venv/Scripts/python.exe -c "
from src.backends.gemini_cli import GeminiCLIBackend
from src.backends import BackendConfig
import asyncio

async def test():
    config = BackendConfig(name='test', system_prompt='Be brief')
    backend = GeminiCLIBackend(config)
    await backend.initialize()
    result = await backend.query('What is 2+2?')
    print(f'Result: {result.response}')

asyncio.run(test())
"

# Test CrewAI/Ollama backend
.venv/Scripts/python.exe -c "
from src.backends.crewai import CrewAIBackend
from src.backends import BackendConfig
import asyncio

async def test():
    config = BackendConfig(name='test', system_prompt='Be brief')
    backend = CrewAIBackend(config, ollama_model='llama3.2')
    await backend.initialize()
    result = await backend.query('What is 3+3?')
    print(f'Result: {result.response}')

asyncio.run(test())
"
```

### Test 4: Error Handling

```bash
# Invalid JSON
curl -X POST http://localhost:9000/query \
  -H "Content-Type: application/json" \
  -d 'not json'
# Expected: 422 with "JSON decode error"

# Missing query field
curl -X POST http://localhost:9000/query \
  -H "Content-Type: application/json" \
  -d '{"wrong": "field"}'
# Expected: 422 with "Field required"
```

---

## Running All Usability Tests

```bash
# Run all usability tests
uv run pytest tests/usability/ -v -m usability

# Run with output (see print statements)
uv run pytest tests/usability/ -v -s

# Run specific test file
uv run pytest tests/usability/test_backends.py -v

# Run excluding slow tests (SSH deployment)
uv run pytest tests/usability/ -v -m "usability and not slow"
```

---

## Verifying Log Content is Not Truncated

The old issue was logs truncating at 200 characters. To verify this is fixed:

```bash
# 1. Make a query that generates long content
curl -X POST http://localhost:9000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Compare weather in all 4 cities with detailed analysis"}'

# 2. Check log file for full content
grep "Input:" src/logs/controller_agent.log | tail -3
# Should show FULL JSON, not ending in "..."

# 3. Check tool result content
grep "Result content:" src/logs/weather_agent.log | tail -3
# Should show full weather data

# 4. Verify log_max_content_length setting
.venv/Scripts/python.exe -c "from src.config import settings; print(f'Max log content: {settings.log_max_content_length}')"
# Should show: Max log content: 2000 (or your configured value)
```

---

## Test Results Summary

When all tests pass, you should see:

```
tests/usability/test_backends.py: 12 passed
tests/usability/test_observability.py: 13 passed
tests/usability/test_tool_calls.py: 6 passed (requires agents running)
tests/usability/test_complete_system.py: 1 passed
tests/usability/test_ssh_deployment.py: 1 passed (requires SSH server)

Total: 33+ tests
```

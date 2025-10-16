# Testing Guide

This directory contains unit and integration tests for the clean_mcp_a2a project.

## Test Structure

- **test_unit.py**: Unit tests for MCP tools (weather and maps)
- **test_integration.py**: Integration tests for agents and A2A protocol
- **test_system.py**: System-level testing script

## Running Tests

### Unit Tests

Unit tests test individual MCP tools in isolation:

```bash
uv run pytest tests/test_unit.py -v
```

These tests:
- Test weather tools (get_weather, get_locations)
- Test maps tools (get_distance, get_cities)
- Verify data consistency
- **No agents need to be running**

### Integration Tests

Integration tests require all three agents to be running:

```bash
# Terminal 1: Start Weather Agent
uv run weather-agent

# Terminal 2: Start Maps Agent
uv run maps-agent

# Terminal 3: Start Controller Agent
uv run controller-agent

# Terminal 4: Run integration tests
uv run pytest tests/test_integration.py -v
```

Or use the convenience script to start all agents:

```bash
# Start all agents in background
uv run start-all &

# Wait a few seconds for agents to start
sleep 5

# Run integration tests
uv run pytest tests/test_integration.py -v

# Stop all agents when done
pkill -f "uv run python"
```

Integration tests verify:
- A2A protocol endpoints (/.well-known/agent-configuration)
- Health endpoints
- Weather Agent queries
- Maps Agent queries
- Controller Agent coordination
- Multi-agent workflows
- Logging functionality

### All Tests

Run both unit and integration tests:

```bash
# Start agents first
uv run start-all &
sleep 5

# Run all tests
uv run pytest tests/ -v

# Cleanup
pkill -f "uv run python"
```

## Test Requirements

- pytest >= 7.4.0
- pytest-asyncio >= 0.21.0
- httpx >= 0.25.0
- All agents running (for integration tests only)

## Logs

Test logs and agent logs are stored in the `logs/` directory:
- `weather_agent.log`
- `maps_agent.log`
- `controller_agent.log`

## Test Coverage

### Unit Tests (10 tests)
- ✅ Weather tool: Tokyo query
- ✅ Weather tool: Invalid location
- ✅ Weather tool: Imperial units
- ✅ Weather tool: Get locations
- ✅ Maps tool: Tokyo-London distance
- ✅ Maps tool: Invalid origin
- ✅ Maps tool: Distance in miles
- ✅ Maps tool: Get cities
- ✅ Data consistency: Cities match
- ✅ Data consistency: City count

### Integration Tests (13 tests)
- ✅ Weather Agent A2A discovery
- ✅ Maps Agent A2A discovery
- ✅ Controller Agent A2A discovery
- ✅ Health endpoints for all agents
- ✅ Weather Agent: Tokyo query
- ✅ Weather Agent: Get locations
- ✅ Maps Agent: Distance query
- ✅ Maps Agent: Available cities
- ✅ Controller: Weather delegation
- ✅ Controller: Maps delegation
- ✅ Controller: Multi-agent coordination
- ✅ Logging: Directory exists
- ✅ Logging: Log files created

## Troubleshooting

### Agents Not Running
If integration tests fail with connection errors:
```bash
# Check if agents are running
curl http://localhost:9001/health
curl http://localhost:9002/health
curl http://localhost:9000/health

# Restart if needed
uv run start-all &
```

### Port Already in Use
```bash
# Find and kill processes on ports
lsof -ti:9000,9001,9002 | xargs kill -9
```

### Logs Directory Missing
```bash
mkdir -p logs
```

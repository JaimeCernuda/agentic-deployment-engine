# Examples

This directory contains Python examples demonstrating the agentic deployment engine.

## Quick Start

### demo_multi_agent.py
Complete multi-agent demo showing:
- Agent creation and startup
- Query handling
- A2A communication between agents

```bash
uv run python examples/demo_multi_agent.py
```

### custom_coordinator.py
Shows how to create a custom coordinator agent with specialized routing logic.

## Job Definitions

See `../jobs/examples/` for YAML job files demonstrating different topologies:

| File | Topology | Description |
|------|----------|-------------|
| simple-weather.yaml | Hub-spoke | Controller coordinates weather/maps agents |
| pipeline.yaml | Pipeline | 4-stage linear data processing |
| distributed-dag.yaml | DAG | Parallel branches with convergence |
| collaborative-mesh.yaml | Mesh | 5-agent peer-to-peer collaboration |
| hierarchical-tree.yaml | Hierarchical | 3-level geographic distribution |
| ssh-localhost.yaml | SSH | All agents via SSH to localhost |
| ssh-multi-host.yaml | SSH | Multi-host remote deployment |

Run any job with:
```bash
uv run deploy start ../jobs/examples/<filename>.yaml
```

## Test Scenarios

See `../tests/usability/` for runnable test scenarios that verify:
- End-to-end user journeys
- All topology patterns
- Security with authentication
- SSH deployment
- Alternative backends (Gemini CLI, CrewAI)

## Built-in Agents

The system includes these pre-built agents:

```bash
uv run weather-agent    # Port 9001 - Weather queries
uv run maps-agent       # Port 9002 - Distance/maps queries
uv run controller-agent # Port 9000 - Coordinates other agents
uv run start-all        # Start all agents at once
```

## Backend Configuration

Switch backends using environment variables:

```bash
# Claude Agent SDK (default)
uv run start-all

# Gemini CLI
AGENT_BACKEND_TYPE=gemini uv run start-all

# CrewAI with Ollama
AGENT_BACKEND_TYPE=crewai AGENT_OLLAMA_MODEL=llama3 uv run start-all
```

# Getting started

This guide walks you through installing and running your first agent with the Agentic Deployment Engine.

## Prerequisites

- **Python 3.11+** - Required for the framework
- **uv** - Fast Python package manager ([installation](https://docs.astral.sh/uv/getting-started/installation/))
- **Claude API key** - For agents using the Claude backend

## Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/your-org/agentic-deployment-engine.git
cd agentic-deployment-engine

# Install all dependencies
uv sync
```

## Running your first agent

Start a single agent to verify the installation works:

```bash
# Start the weather agent on port 9001
uv run weather-agent
```

You should see output like:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:9001
```

## Making your first query

With the agent running, send a query in another terminal:

```bash
curl -X POST http://localhost:9001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in Tokyo?"}'
```

Expected response:
```json
{
  "response": "The current weather in Tokyo is 22.5°C with partly cloudy skies..."
}
```

## Understanding the response

When you query an agent:

1. Your HTTP request reaches the agent's FastAPI server
2. The agent passes the query to the Claude SDK client
3. Claude processes the query and may call MCP tools
4. The agent returns Claude's response as JSON

You can observe this in the agent logs at `src/logs/weather_agent.log`.

## Running multiple agents

Start all example agents at once:

```bash
uv run start-all
```

This launches:
- **Weather Agent** (port 9001) - Weather information
- **Maps Agent** (port 9002) - Distance calculations
- **Controller Agent** (port 9000) - Multi-agent coordination

Now you can make complex queries that span multiple agents:

```bash
curl -X POST http://localhost:9000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in Tokyo and how far is it from London?"}'
```

The controller agent will coordinate with weather and maps agents to answer.

## Using job definitions

For declarative deployments, use job YAML files:

```bash
# Validate a job definition
uv run deploy validate examples/jobs/simple-weather.yaml

# Preview the deployment plan
uv run deploy plan examples/jobs/simple-weather.yaml

# Deploy and run
uv run deploy start examples/jobs/simple-weather.yaml
```

## Checking agent health

Each agent exposes a health endpoint:

```bash
# Check if an agent is running
curl http://localhost:9001/health
```

Response:
```json
{
  "status": "healthy",
  "agent": "Weather Agent"
}
```

## Agent discovery

Agents expose their capabilities via the A2A protocol:

```bash
curl http://localhost:9001/.well-known/agent-configuration
```

This returns the agent's name, description, skills, and capabilities.

## Next steps

- [Building agents](building-agents.md) - Create custom agents
- [Job definitions](job-definitions.md) - Declarative deployment
- [Architecture](architecture.md) - System design
- [Configuration](configuration.md) - Environment variables

## Common issues

If you encounter problems, see [Troubleshooting](troubleshooting.md) for solutions to common issues.

### Agent won't start

Check if the port is already in use:
```bash
# Windows
netstat -ano | findstr :9001

# Linux/Mac
lsof -i :9001
```

### Missing API key

Set your Claude API key:
```bash
export ANTHROPIC_API_KEY=your-api-key-here
```

### Import errors

Ensure dependencies are installed:
```bash
uv sync
```

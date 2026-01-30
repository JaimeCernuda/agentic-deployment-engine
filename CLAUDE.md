# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Run Commands

```bash
# Install dependencies
uv sync

# Run individual agents
uv run weather-agent      # Port 9001
uv run maps-agent         # Port 9002
uv run controller-agent   # Port 9000
uv run start-all          # All agents at once

# Job deployment CLI
uv run deploy validate <job.yaml>   # Validate job definition
uv run deploy plan <job.yaml>       # Preview deployment plan (dry run)
uv run deploy start <job.yaml>      # Deploy and run

# Testing
uv run pytest tests/unit/ -v                   # Unit tests
uv run pytest tests/integration/ -v            # Integration tests
uv run pytest tests/usability/ -v              # Usability/E2E tests
uv run pytest tests/ -v                        # All tests

# Linting
ruff check --fix && ruff format
```

## Project Structure

```
agentic-deployment-engine/
├── src/                    # Core source code
│   ├── agents/             # Agent framework
│   │   ├── base.py         # BaseA2AAgent abstract class
│   │   ├── registry.py     # Agent discovery registry
│   │   └── transport.py    # A2A MCP transport
│   ├── backends/           # LLM backend implementations
│   │   ├── claude_sdk.py   # Claude Agent SDK
│   │   ├── gemini_cli.py   # Google Gemini CLI
│   │   └── crewai.py       # CrewAI + Ollama
│   ├── core/               # Core types and utilities
│   │   ├── types.py        # TypedDict definitions
│   │   ├── exceptions.py   # Custom exceptions
│   │   └── container.py    # Dependency injection
│   ├── jobs/               # Deployment orchestration
│   │   ├── models.py       # Job/agent config models
│   │   ├── resolver.py     # Topology resolution
│   │   ├── deployer.py     # Multi-target deployment
│   │   └── cli.py          # CLI interface
│   ├── security/           # Authentication
│   │   ├── auth.py         # API key auth
│   │   └── permissions.py  # Tool permissions
│   ├── observability/      # Logging and tracing
│   │   ├── logging.py      # Structured logging
│   │   └── telemetry.py    # OpenTelemetry
│   └── config.py           # Settings
├── examples/               # Example implementations
│   ├── agents/             # Example agents
│   │   ├── weather_agent.py
│   │   ├── maps_agent.py
│   │   └── controller_agent.py
│   ├── tools/              # Example MCP tools
│   │   ├── weather_tools.py
│   │   └── maps_tools.py
│   ├── jobs/               # Example job YAML files
│   └── demos/              # Demo scripts
├── tests/                  # Test suites
│   ├── unit/               # Unit tests (mocked)
│   ├── integration/        # Integration tests
│   └── usability/          # E2E usability tests
└── docs/                   # Documentation
```

## Architecture

This is a multi-agent deployment framework using Claude Agent SDK with MCP (Model Context Protocol) integration.

### Core Components

**BaseA2AAgent** (`src/agents/base.py`): Abstract base class all agents inherit from. Provides:
- FastAPI server with A2A protocol endpoints (`/query`, `/health`, `/.well-known/agent-configuration`)
- Claude SDK client integration via `ClaudeSDKClient` and `ClaudeAgentOptions`
- Dynamic agent discovery via `AgentRegistry`
- Configurable backend (Claude SDK, Gemini CLI, CrewAI)

**SDK MCP A2A Transport** (`src/agents/transport.py`): In-process MCP tools for agent communication:
- `query_agent(agent_url, query)` - Query another agent via HTTP POST
- `discover_agent(agent_url)` - Get agent capabilities via A2A discovery endpoint
- Created via `create_sdk_mcp_server()` from `claude_agent_sdk`

**Jobs System** (`src/jobs/`): Declarative YAML-based deployment orchestration:
- `models.py` - Pydantic models for job definitions (JobDefinition, AgentConfig, TopologyConfig)
- `resolver.py` - Converts topology patterns (hub-spoke, pipeline, dag, mesh, hierarchical) to deployment plans
- `deployer.py` - Multi-target deployment (localhost, SSH, Docker, Kubernetes)
- `cli.py` - Typer CLI interface

### Creating New Agents

1. Create MCP tools in `examples/tools/<name>_tools.py` using `@tool` decorator from `claude_agent_sdk`
2. Create agent class in `examples/agents/<name>_agent.py` extending `BaseA2AAgent`
3. Implement `_get_skills()` and `_get_allowed_tools()` abstract methods
4. Add entry point to `pyproject.toml` under `[project.scripts]`

Tool naming convention: `mcp__<server_name>__<tool_name>`

Example agent structure:
```python
from src import BaseA2AAgent
from src.security import PermissionPreset
from claude_agent_sdk import create_sdk_mcp_server

class MyAgent(BaseA2AAgent):
    def __init__(self, port: int = 9003):
        server = create_sdk_mcp_server(name="my_agent", version="1.0.0", tools=[...])
        super().__init__(
            name="My Agent",
            description="...",
            port=port,
            sdk_mcp_server=server,
            system_prompt="..."
        )

    def _get_skills(self) -> list:
        return [{"id": "...", "name": "...", "description": "..."}]

    def _get_allowed_tools(self) -> list[str]:
        return ["mcp__my_agent__tool_name"]
```

### Topology Patterns

Job definitions use `topology.type` to define agent relationships:
- `hub-spoke`: Central coordinator with workers (hub deploys last)
- `pipeline`: Sequential stages (each connects to next)
- `dag`: Directed acyclic graph with explicit connections
- `mesh`: All agents connect to all others
- `hierarchical`: Tree structure from root

### Key Dependencies

- `claude-agent-sdk` from GitHub main branch (not PyPI release)
- FastAPI + Uvicorn for agent HTTP servers
- httpx for async HTTP client (A2A communication)
- Pydantic for data validation
- paramiko for SSH deployment

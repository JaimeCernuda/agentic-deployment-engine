# Agentic deployment engine

A multi-agent deployment framework using Claude Agent SDK with MCP integration and declarative job orchestration.

## Features

- **SDK MCP A2A transport** - Efficient in-process agent communication (10-100x faster than subprocess)
- **Dynamic agent discovery** - Automatic capability detection via A2A protocol
- **Declarative job definitions** - Define complex topologies in YAML
- **Multi-target deployment** - Deploy to localhost, SSH, Docker, or Kubernetes
- **Multiple topology patterns** - Hub-spoke, pipeline, mesh, DAG, hierarchical

## Quick start

### Installation

```bash
uv sync
```

### Run agents

```bash
# Start all example agents
uv run start-all

# Or individually
uv run weather-agent      # Port 9001
uv run maps-agent         # Port 9002
uv run controller-agent   # Port 9000
```

### Deploy a job

```bash
uv run deploy start examples/jobs/simple-weather.yaml
```

### Query an agent

```bash
curl -X POST http://localhost:9000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in Tokyo?"}'
```

## Project structure

```
agentic-deployment-engine/
├── src/                    # Core framework
│   ├── agents/             # Agent base classes and transport
│   ├── backends/           # LLM backends (Claude, Gemini, CrewAI)
│   ├── core/               # Types, exceptions, container
│   ├── jobs/               # Job deployment system
│   ├── security/           # Auth and permissions
│   └── observability/      # Logging and telemetry
├── examples/               # Example implementations
│   ├── agents/             # Weather, Maps, Controller agents
│   ├── tools/              # MCP tools
│   ├── jobs/               # Job YAML definitions
│   └── demos/              # Demo scripts
├── tests/                  # Test suite
│   ├── unit/               # Fast, mocked tests
│   ├── integration/        # Component coordination
│   └── usability/          # End-to-end validation
└── docs/                   # Documentation
```

## Documentation

- [Getting started](docs/getting-started.md) - Installation and first steps
- [Building agents](docs/building-agents.md) - Create custom agents
- [Architecture](docs/architecture.md) - System design and patterns
- [Configuration](docs/configuration.md) - Settings reference
- [Job definitions](docs/job-definitions.md) - YAML job format
- [SSH deployment](docs/ssh-deployment.md) - Remote deployment
- [Security](docs/security.md) - Authentication and permissions
- [Testing](docs/testing.md) - Running and writing tests
- [MCP transport](docs/mcp-transport.md) - Transport internals
- [Troubleshooting](docs/troubleshooting.md) - Common issues

## Topology patterns

### Hub-and-spoke
Central coordinator with specialized workers.
```
         Controller
         /   |   \
    Weather Maps Database
```

### Pipeline
Sequential processing stages.
```
Intake → Process → Validate → Output
```

### Mesh
All agents connect to all others.
```
  1 ←→ 2
  ↕ ╲╱ ↕
  4 ←→ 3
```

### DAG
Directed acyclic graph with parallel branches.
```
       ┌─ Branch-A ─┐
Source ─┤            ├─ Merge
       └─ Branch-B ─┘
```

### Hierarchical
Multi-level tree organization.
```
         Root
        /    \
    VP-Eng  VP-Sales
    /    \
 Team-A  Team-B
```

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# By category
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v
uv run pytest tests/usability/ -v

# With coverage
uv run pytest tests/ --cov=src
```

## CLI commands

```bash
uv run deploy validate <job.yaml>   # Validate job definition
uv run deploy plan <job.yaml>       # Preview deployment plan
uv run deploy start <job.yaml>      # Deploy and run
```

## Dependencies

- Python 3.11+
- Claude Agent SDK (main branch)
- FastAPI + Uvicorn
- Pydantic
- httpx
- paramiko (SSH deployment)

## License

See LICENSE file.

# Agentic Deployment Engine

A sophisticated multi-agent deployment framework that combines Claude Agent SDK with MCP integration, Agent-to-Agent (A2A) transport, and declarative job orchestration for building and deploying distributed agent systems.

## Overview

The Agentic Deployment Engine makes it easy to build, configure, and deploy complex multi-agent systems with:

- **SDK MCP A2A Transport**: Efficient HTTP-based agent communication via SDK MCP tools
- **Dynamic Agent Discovery**: Automatic agent discovery and capability detection at runtime
- **Declarative Job Definitions**: Define complex agent topologies in YAML without code changes
- **Multi-Target Deployment**: Deploy to localhost, SSH remote hosts, containers, and Kubernetes
- **Multiple Topology Patterns**: Hub-spoke, pipeline, DAG, mesh, and hierarchical architectures

## Key Features

- **In-Process MCP SDK Tools**: 10-100x faster than subprocess MCP servers
- **BaseA2AAgent Framework**: Inheritance-based agent development with built-in A2A capabilities
- **Topology Resolver**: Automatic conversion of patterns to deployment plans
- **Health Monitoring**: Built-in health checks and connectivity validation
- **Connection Resolution**: Automatic URL resolution based on deployment topology
- **Agent Registry**: Runtime service discovery with caching

## Quick Start

### Installation

```bash
# Install dependencies
uv sync
```

### Running Agents Manually

```bash
# Terminal 1: Start weather agent
uv run weather-agent

# Terminal 2: Start maps agent
uv run maps-agent

# Terminal 3: Start controller agent
uv run controller-agent

# Or start all at once
uv run start-all
```

### Deploying with Jobs System

```bash
# Validate a job definition
uv run deploy validate jobs/examples/simple-weather.yaml

# View deployment plan (dry run)
uv run deploy plan jobs/examples/simple-weather.yaml

# Deploy and run the job
uv run deploy start jobs/examples/simple-weather.yaml
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Application Layer (Agents)                 │
│  WeatherAgent, MapsAgent, ControllerAgent              │
│  - Inherit from BaseA2AAgent                            │
│  - Define skills and tools                              │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│         A2A Framework & Agent Infrastructure            │
│  - BaseA2AAgent: FastAPI + A2A endpoints                │
│  - SDK MCP A2A Transport: query_agent, discover_agent   │
│  - Agent Registry: Dynamic discovery & caching          │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│           Job Deployment System (src/jobs)              │
│  - JobDefinition: Comprehensive validation              │
│  - TopologyResolver: Pattern to deployment conversion   │
│  - AgentDeployer: Multi-target orchestration            │
│  - Runners: Local, SSH, Docker, Kubernetes              │
└─────────────────────────────────────────────────────────┘
```

### Example: Hub-and-Spoke Topology

```
         Controller (port 9000)
               ↙        ↘
    Weather Agent    Maps Agent
    (port 9001)      (port 9002)
```

Controller coordinates weather and maps agents via A2A protocol using SDK MCP tools for efficient HTTP-based communication.

## Topology Patterns

### 1. Hub-and-Spoke
Central coordinator with specialized workers. Spokes deploy first (parallel), then hub deploys.

**Example**: `jobs/examples/simple-weather.yaml`

### 2. Pipeline
Sequential processing stages, each connects to next.

**Example**: `jobs/examples/pipeline.yaml`

### 3. DAG (Directed Acyclic Graph)
Parallel branches with convergence points. Topological sort determines deployment order.

**Example**: `jobs/examples/distributed-dag.yaml`

### 4. Full Mesh
All agents connect to all others for peer-to-peer collaboration.

**Example**: `jobs/examples/collaborative-mesh.yaml`

### 5. Hierarchical Tree
Multi-level organization with root-to-leaf connections.

**Example**: `jobs/examples/hierarchical-tree.yaml`

## Project Structure

```
agentic-deployment-engine/
├── agents/                      # Agent implementations
│   ├── weather_agent.py         # Weather service agent
│   ├── maps_agent.py            # Maps/distance calculation agent
│   └── controller_agent.py      # Coordinator agent
├── src/
│   ├── base_a2a_agent.py        # Base A2A agent class
│   ├── a2a_transport.py         # SDK MCP A2A transport tools
│   ├── agent_registry.py        # Dynamic agent discovery
│   └── jobs/                    # Job deployment system
│       ├── models.py            # Job definition models
│       ├── loader.py            # YAML job loader
│       ├── resolver.py          # Topology resolver
│       ├── deployer.py          # Agent deployer
│       └── cli.py               # CLI interface
├── tools/
│   ├── weather_tools.py         # Weather MCP tools
│   └── maps_tools.py            # Maps MCP tools
├── jobs/
│   ├── examples/                # Example job definitions
│   │   ├── simple-weather.yaml
│   │   ├── pipeline.yaml
│   │   ├── distributed-dag.yaml
│   │   ├── collaborative-mesh.yaml
│   │   └── hierarchical-tree.yaml
│   └── README.md                # Jobs system documentation
├── tests/                       # Test suite
├── scripts/                     # Utility scripts
├── examples/                    # Example code
├── docs/                        # Documentation
└── pyproject.toml              # Project configuration
```

## Available Agents

### WeatherAgent (port 9001)
Provides weather information for cities.

**Skills**: Weather analysis, location lookup
**Tools**: `get_weather`, `get_locations`

### MapsAgent (port 9002)
Calculates distances between cities using haversine formula.

**Skills**: Distance calculation, city listing
**Tools**: `get_distance`, `get_cities`

### ControllerAgent (port 9000)
Coordinates multi-agent queries and orchestrates workflows.

**Skills**: Agent coordination, query routing
**Tools**: `query_agent`, `discover_agent` (A2A transport)

## Creating Custom Agents

Extend `BaseA2AAgent` to create new agents:

```python
from src.base_a2a_agent import BaseA2AAgent

class MyAgent(BaseA2AAgent):
    def _get_skills(self) -> str:
        return "Describe agent capabilities"

    def _get_allowed_tools(self) -> list[str]:
        return ["mcp__my_server__my_tool"]
```

See `docs/AGENT_BUILDER_GUIDE.md` for detailed guide.

## Deployment Targets

### Localhost
```yaml
deployment:
  target: localhost
```

### Remote SSH
```yaml
deployment:
  target: remote
  ssh:
    host: remote.example.com
    user: deploy
    key_path: ~/.ssh/id_rsa
```

### Docker Container
```yaml
deployment:
  target: container
  container:
    image: my-agent:latest
```

### Kubernetes
```yaml
deployment:
  target: kubernetes
  kubernetes:
    namespace: agents
    service_type: ClusterIP
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test suite
pytest tests/test_system.py -v

# Run integration tests
uv run test-system
```

## CLI Commands

```bash
# Validate job definition
uv run deploy validate <job.yaml>

# Generate deployment plan
uv run deploy plan <job.yaml>

# Start job
uv run deploy start <job.yaml>

# View job status (placeholder)
uv run deploy status <job-name>

# Stop job (placeholder)
uv run deploy stop <job-name>

# View logs (placeholder)
uv run deploy logs <job-name>

# List all jobs (placeholder)
uv run deploy list
```

## Documentation

- **[Architecture Upgrade](docs/ARCHITECTURE_UPGRADE.md)**: Technical details of SDK MCP A2A implementation
- **[Jobs System](jobs/README.md)**: Complete jobs system documentation
- **[Job Specification](jobs/JOB_SPECIFICATION.md)**: Job definition format reference
- **[Agent Builder Guide](docs/AGENT_BUILDER_GUIDE.md)**: Creating custom agents
- **[SSH Deployment](jobs/SSH_DEPLOYMENT_GUIDE.md)**: Remote SSH deployment guide
- **[Multi-Agent Architectures](docs/MULTI_AGENT_ARCHITECTURES.md)**: Architecture patterns reference

## Example Workflow

1. **Define a job** in YAML with agents and topology
2. **Validate** the job definition: `uv run deploy validate job.yaml`
3. **Review** the deployment plan: `uv run deploy plan job.yaml`
4. **Deploy** the system: `uv run deploy start job.yaml`
5. **Query** agents via their HTTP endpoints

### Example Query

```bash
# Query the controller agent
curl -X POST http://localhost:9000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in Tokyo and how far is it from London?"}'
```

## Dependencies

- Python 3.10+
- FastAPI (web framework)
- Uvicorn (ASGI server)
- Claude Agent SDK (main branch)
- httpx (async HTTP client)
- Pydantic (data validation)
- typer + rich (CLI)
- paramiko (SSH deployment)

## Contributing

This is a research/demo project showcasing multi-agent deployment patterns with Claude Agent SDK and MCP integration.

## License

See LICENSE file for details.

## Support

For issues and questions, please refer to the documentation in the `docs/` directory or review example job definitions in `jobs/examples/`.

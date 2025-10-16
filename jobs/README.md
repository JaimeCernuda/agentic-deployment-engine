# A2A Job System

## Overview

The A2A Job System provides declarative workflow definition and automated deployment for multi-agent systems. Think of it as **"mpirun for agent workflows"** - define complex agent topologies and deploy them anywhere with a single command.

## Key Features

✅ **Declarative Workflows** - Define agent workflows in YAML
✅ **Multiple Topologies** - Hub-spoke, pipeline, DAG, mesh, hierarchical
✅ **Distributed Deployment** - Local, remote (SSH), containers, Kubernetes
✅ **Dynamic Discovery** - Agents discover connections automatically
✅ **Health Monitoring** - Built-in health checks and connectivity validation
✅ **MPI-like Interface** - Familiar deployment patterns for distributed systems

## Quick Start

### 1. Define a Job

Create `my-workflow.yaml`:

```yaml
job:
  name: my-workflow
  version: 1.0.0
  description: My first agent workflow

agents:
  - id: weather
    type: WeatherAgent
    module: agents.weather_agent
    config:
      port: 9001
    deployment:
      target: localhost

  - id: controller
    type: ControllerAgent
    module: agents.controller_agent
    config:
      port: 9000
    deployment:
      target: localhost

topology:
  type: hub-spoke
  hub: controller
  spokes: [weather]

deployment:
  strategy: sequential
  timeout: 30
```

### 2. Deploy

```bash
# Validate the job
uv run deploy validate my-workflow.yaml

# Deploy the job
uv run deploy start my-workflow.yaml

# Monitor status
uv run deploy status my-workflow

# View logs
uv run deploy logs my-workflow

# Stop when done
uv run deploy stop my-workflow
```

## Documentation

### Core Documents

1. **[JOB_SPECIFICATION.md](JOB_SPECIFICATION.md)** - Complete job format specification
   - Job structure and syntax
   - Topology patterns
   - Deployment targets
   - Validation rules
   - Examples and best practices

2. **[DEPLOYMENT_ENGINE.md](DEPLOYMENT_ENGINE.md)** - Deployment engine architecture
   - System architecture
   - Component design
   - Data models
   - Deployment process
   - Implementation plan

### Examples

All examples are in `examples/`:

- **[simple-weather.yaml](examples/simple-weather.yaml)** - Hub-and-spoke pattern
  - Controller coordinating Weather and Maps agents
  - Local deployment
  - Good starting point

- **[pipeline.yaml](examples/pipeline.yaml)** - Linear pipeline pattern
  - 4-stage data processing pipeline
  - Sequential processing
  - Demonstrates data flow

- **[distributed-dag.yaml](examples/distributed-dag.yaml)** - DAG with parallel branches
  - Multi-stage analysis workflow
  - Parallel processing branches
  - Remote deployment across multiple hosts
  - Demonstrates distributed computing

- **[collaborative-mesh.yaml](examples/collaborative-mesh.yaml)** - Full mesh pattern
  - 5 research agents collaborating peer-to-peer
  - All-to-all connectivity
  - Demonstrates collaboration patterns

- **[hierarchical-tree.yaml](examples/hierarchical-tree.yaml)** - Hierarchical pattern
  - 3-level geographic weather network
  - Global → Regional → Local structure
  - Demonstrates organizational hierarchy

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Job Definition (YAML)                      │
│  - Agents, Topology, Deployment, Resources                   │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ↓
┌──────────────────────────────────────────────────────────────┐
│                   Deployment Engine                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │   Parser   │→ │ Validator  │→ │  Planner   │            │
│  └────────────┘  └────────────┘  └────────────┘            │
│                         │                                     │
│                         ↓                                     │
│  ┌──────────────────────────────────────────────┐           │
│  │         Deployment Orchestrator               │           │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐    │           │
│  │  │  Local   │ │  Remote  │ │Container │    │           │
│  │  │ Deployer │ │ Deployer │ │ Deployer │    │           │
│  │  └──────────┘ └──────────┘ └──────────┘    │           │
│  └──────────────────────────────────────────────┘           │
│                         │                                     │
│                         ↓                                     │
│  ┌──────────────────────────────────────────────┐           │
│  │          Health Monitor & Registry            │           │
│  └──────────────────────────────────────────────┘           │
└──────────────────────────────────────────────────────────────┘
                         │
                         ↓
┌──────────────────────────────────────────────────────────────┐
│                   Running Agent Workflow                      │
│   [Agent 1] ←→ [Agent 2] ←→ [Agent 3] ←→ [Agent 4]         │
└──────────────────────────────────────────────────────────────┘
```

## Topology Patterns

### 1. Hub-and-Spoke
**Use case:** Central coordinator with workers

```
    ┌─────────────┐
    │ Controller  │
    └──────┬──────┘
           │
    ┏━━━━━━┻━━━━━━┓
    ↓              ↓
┌────────┐    ┌────────┐
│Weather │    │  Maps  │
└────────┘    └────────┘
```

### 2. Linear Pipeline
**Use case:** Sequential processing stages

```
┌────────┐   ┌──────────┐   ┌───────────┐   ┌────────┐
│ Ingest │ → │ Validate │ → │ Transform │ → │ Output │
└────────┘   └──────────┘   └───────────┘   └────────┘
```

### 3. DAG (Directed Acyclic Graph)
**Use case:** Parallel branches with convergence

```
              ┌───────┐
              │Collect│
              └───┬───┘
                  │
         ┏━━━━━━━━╋━━━━━━━━┓
         ↓        ↓         ↓
    ┌────────┐ ┌─────┐ ┌───────┐
    │ Stats  │ │ ML  │ │  NLP  │
    └────┬───┘ └──┬──┘ └───┬───┘
         └────────┼────────┘
                  ↓
            ┌───────────┐
            │Aggregator │
            └───────────┘
```

### 4. Full Mesh
**Use case:** Peer-to-peer collaboration

```
     ┌────────┐
  ┌─→│Agent 1 │←──┐
  │  └────────┘   │
  │       ↕       │
  │  ┌────────┐  │
  ├─→│Agent 2 │←─┤
  │  └────────┘  │
  │       ↕      │
  │  ┌────────┐ │
  └─→│Agent 3 │←┘
     └────────┘
```

### 5. Hierarchical Tree
**Use case:** Multi-level organization

```
          ┌────────────┐
          │   Global   │
          └─────┬──────┘
                │
      ┏━━━━━━━━━╋━━━━━━━━━┓
      ↓         ↓          ↓
  ┌────────┐ ┌──────┐ ┌────────┐
  │Americas│ │Europe│ │  Asia  │
  └───┬────┘ └──┬───┘ └────┬───┘
      │         │           │
   ┌──┴──┐   ┌─┴─┐      ┌──┴──┐
   NYC  SF   LON PAR    TYO  SIN
```

## Deployment Targets

### Local Deployment
```yaml
deployment:
  target: localhost
```
- Agents run on local machine
- Uses subprocess
- Fast development/testing

### Remote Deployment (SSH)
```yaml
deployment:
  target: remote
  host: worker-1.example.com
  user: agent-user
  python: /usr/bin/python3
  workdir: /opt/agents
```
- Deploys to remote hosts via SSH
- Requires SSH key access
- Distributed processing

### Container Deployment
```yaml
deployment:
  target: container
  image: agent-runtime:latest
  network: agent-network
```
- Deploys in Docker containers
- Isolated environments
- Easy scaling

### Kubernetes Deployment
```yaml
deployment:
  target: kubernetes
  namespace: agents
  service_type: ClusterIP
```
- Cloud-native deployment
- Auto-scaling
- Production-grade orchestration

## Workflow Lifecycle

```
1. Define
   ↓
2. Validate
   ↓
3. Plan
   ↓
4. Deploy
   ↓
5. Monitor
   ↓
6. Execute
   ↓
7. Shutdown
```

### Detailed Steps

**1. Define** - Write job YAML with agents and topology

**2. Validate** - Check job definition
- Schema validation
- Agent types exist
- No port conflicts
- Topology is valid (no cycles)
- Connections are reachable

**3. Plan** - Generate deployment plan
- Build dependency graph
- Determine deployment order
- Resolve agent URLs
- Group into stages

**4. Deploy** - Start agents
- Deploy agents per stage
- Wait for health checks
- Validate connections
- Register in job registry

**5. Monitor** - Continuous health monitoring
- HTTP health checks
- Process monitoring
- Connection validation
- Log collection

**6. Execute** - Workflow runs
- Agents process requests
- Dynamic discovery working
- A2A transport operational

**7. Shutdown** - Graceful termination
- Stop agents in reverse order
- Cleanup resources
- Archive logs

## CLI Commands

```bash
# Validation
uv run deploy validate <job.yaml>

# Deployment
uv run deploy plan <job.yaml>              # Dry run
uv run deploy start <job.yaml>             # Deploy
uv run deploy start <job.yaml> --name foo  # Named deployment

# Monitoring
uv run deploy status <job-name>            # Overall status
uv run deploy status <job-name> --agent id # Agent status
uv run deploy logs <job-name>              # All logs
uv run deploy logs <job-name> --agent id   # Agent logs
uv run deploy logs <job-name> --follow     # Tail logs

# Management
uv run deploy stop <job-name>              # Stop job
uv run deploy stop <job-name> --graceful   # Graceful stop
uv run deploy restart <job-name>           # Restart job
uv run deploy list                          # List all jobs
uv run deploy list --status running        # Filter by status
uv run deploy inspect <job-name>           # Detailed info

# Cleanup
uv run deploy clean <job-name>             # Remove stopped job
uv run deploy clean --all                  # Remove all stopped
```

## MPI-like Features

Inspired by `mpirun`, the deployment engine supports:

```bash
# Deploy using hostfile
uv run deploy start job.yaml --hostfile hosts.txt

# Deploy N agents per host
uv run deploy start job.yaml --agents-per-host 4

# Pass environment variables
uv run deploy start job.yaml --env-file .env

# Synchronized startup
uv run deploy start job.yaml --sync-start

# Specify working directory
uv run deploy start job.yaml --workdir /opt/agents
```

## Connection Resolution

The deployment engine automatically resolves connection URLs:

| Source → Target | Connection URL |
|----------------|----------------|
| Local → Local | `http://localhost:PORT` |
| Local → Remote | `http://REMOTE_HOST:PORT` |
| Remote → Remote (same host) | `http://localhost:PORT` |
| Remote → Remote (diff host) | `http://REMOTE_HOST:PORT` |
| Container → Container | `http://CONTAINER_NAME:PORT` |

Agents receive resolved URLs via `connected_agents` parameter automatically.

## Best Practices

### 1. Start Simple
- Begin with local deployment
- Use hub-spoke topology
- Test with 2-3 agents

### 2. Validate Early
- Always validate jobs before deployment
- Use `plan` command to preview
- Check resource requirements

### 3. Monitor Health
- Enable health checks
- Set appropriate timeouts
- Monitor logs during deployment

### 4. Version Jobs
- Use semantic versioning
- Track job definitions in git
- Document changes

### 5. Resource Planning
- Specify CPU/memory requirements
- Consider port conflicts
- Plan for scaling

### 6. Error Handling
- Set retry policies
- Plan for agent failures
- Have rollback strategy

## Development Roadmap

### Phase 1: MVP (Current)
- ✅ Job specification
- ✅ Example job definitions
- ✅ Deployment engine architecture
- 🚧 Parser and validator
- 🚧 Local deployer
- 🚧 Basic CLI

### Phase 2: Core Features
- ⬜ Health monitoring
- ⬜ Job registry
- ⬜ All topology patterns
- ⬜ Connection validation

### Phase 3: Distributed
- ⬜ Remote deployment (SSH)
- ⬜ Connection resolution
- ⬜ Distributed monitoring

### Phase 4: Production
- ⬜ Container deployment
- ⬜ Kubernetes support
- ⬜ Auto-scaling
- ⬜ Fault tolerance
- ⬜ Metrics and observability

## File Organization

```
jobs/
├── README.md                      # This file
├── JOB_SPECIFICATION.md           # Complete spec
├── DEPLOYMENT_ENGINE.md           # Engine architecture
│
├── examples/                       # Example job definitions
│   ├── simple-weather.yaml        # Hub-spoke
│   ├── pipeline.yaml              # Linear pipeline
│   ├── distributed-dag.yaml       # DAG with parallelism
│   ├── collaborative-mesh.yaml    # Full mesh
│   └── hierarchical-tree.yaml     # Hierarchical tree
│
├── schemas/                        # JSON schemas (TBD)
│   └── job-schema.json
│
└── templates/                      # Job templates (TBD)
    ├── hub-spoke.yaml
    ├── pipeline.yaml
    └── dag.yaml
```

## Getting Started

### 1. Review the Specification
Read [JOB_SPECIFICATION.md](JOB_SPECIFICATION.md) to understand the job format.

### 2. Study Examples
Explore `examples/` directory - each example demonstrates different patterns.

### 3. Try Locally
Start with `examples/simple-weather.yaml` for local testing.

### 4. Customize
Modify examples or create your own job definitions.

### 5. Deploy
Use the deployment engine once implemented.

## Integration with Existing System

The job system builds on the upgraded A2A architecture:

- **Dynamic Discovery** (`src/agent_registry.py`) - Agents discover connections
- **SDK MCP Transport** (`src/a2a_transport.py`) - Efficient communication
- **Base A2A Agent** (`src/base_a2a_agent.py`) - Supports `connected_agents`

Jobs define **what** to deploy, the deployment engine handles **how** to deploy.

## Contributing

When adding new features:

1. Update `JOB_SPECIFICATION.md` if changing job format
2. Update `DEPLOYMENT_ENGINE.md` if changing architecture
3. Add example job definitions for new patterns
4. Update this README with new features

## See Also

- `../ARCHITECTURE_UPGRADE.md` - A2A architecture upgrade
- `../UPGRADE_SUMMARY.md` - Quick reference
- `../src/base_a2a_agent.py` - Base agent implementation
- `../src/a2a_transport.py` - A2A transport layer
- `../src/agent_registry.py` - Dynamic discovery

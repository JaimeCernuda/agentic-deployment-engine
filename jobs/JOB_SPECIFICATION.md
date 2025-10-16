# A2A Job Definition Specification

## Overview

A **Job** defines a complete multi-agent workflow including:
- Agent definitions (types, configurations)
- Connection topology (who connects to whom)
- Deployment targets (where agents run)
- Resource requirements (ports, memory, etc.)

Jobs enable declarative definition of complex agent workflows with automatic deployment and orchestration.

## Design Philosophy

1. **Declarative** - Describe what you want, not how to achieve it
2. **Composable** - Build complex workflows from simple patterns
3. **Portable** - Same job definition works locally or distributed
4. **Verifiable** - Validate jobs before deployment
5. **Observable** - Built-in logging and health checking

## Job Definition Format

Jobs are defined in YAML format with the following structure:

```yaml
# Job metadata
job:
  name: string              # Unique job identifier
  version: string           # Semantic version (e.g., "1.0.0")
  description: string       # Human-readable description
  tags: [string]           # Optional tags for organization

# Agent definitions
agents:
  - id: string             # Unique agent identifier within job
    type: string           # Agent class (e.g., "WeatherAgent", "ControllerAgent")
    module: string         # Python module path (e.g., "agents.weather_agent")
    config:                # Agent-specific configuration
      port: int            # HTTP port for A2A endpoints
      # ... additional agent config
    deployment:
      target: string       # Where to deploy: "localhost", "host:hostname", "container:name"
      host: string         # Hostname/IP (for remote deployment)
      user: string         # SSH user (for remote deployment)
      python: string       # Python interpreter path
      workdir: string      # Working directory
    resources:
      cpu: float           # CPU cores (optional)
      memory: string       # Memory limit (e.g., "1G")

# Connection topology
topology:
  type: string             # Topology pattern: "hub-spoke", "pipeline", "mesh", "dag", "custom"
  connections:
    - from: string         # Source agent ID
      to: string           # Target agent ID (or list)
      type: string         # Connection type: "query", "stream", "bidirectional"

# Deployment configuration
deployment:
  strategy: string         # "sequential", "parallel", "staged"
  timeout: int             # Startup timeout in seconds
  health_check:
    enabled: bool
    interval: int          # Check interval in seconds
    retries: int           # Number of retries before failure

# Optional: Environment variables
environment:
  key: value

# Optional: Workflow execution
execution:
  entry_point: string      # Agent ID that serves as entry point
  auto_start: bool         # Auto-start workflow on deployment
```

## Topology Patterns

### 1. Hub-and-Spoke
Central coordinator connects to multiple worker agents.

```yaml
topology:
  type: hub-spoke
  hub: controller
  spokes: [weather, maps, travel]
```

**Use case:** Coordinator dispatching to specialized services

### 2. Linear Pipeline
Sequential processing chain.

```yaml
topology:
  type: pipeline
  stages: [ingest, process, analyze, output]
```

**Use case:** Data processing pipelines, ETL workflows

### 3. Full Mesh
Every agent connects to every other agent.

```yaml
topology:
  type: mesh
  agents: [agent1, agent2, agent3]
```

**Use case:** Peer-to-peer collaboration, consensus systems

### 4. Directed Acyclic Graph (DAG)
Custom dependency graph.

```yaml
topology:
  type: dag
  connections:
    - from: ingest
      to: [processor1, processor2]
    - from: processor1
      to: aggregator
    - from: processor2
      to: aggregator
    - from: aggregator
      to: output
```

**Use case:** Complex workflows with parallel branches

### 5. Hierarchical Tree
Multi-level hierarchy.

```yaml
topology:
  type: hierarchical
  root: main_controller
  levels:
    - [regional_controller1, regional_controller2]
    - [worker1, worker2, worker3, worker4]
```

**Use case:** Distributed processing, geographic distribution

### 6. Custom
Explicit connection definition.

```yaml
topology:
  type: custom
  connections:
    - from: controller
      to: weather
    - from: controller
      to: maps
    - from: weather
      to: maps  # Weather can also query Maps
```

**Use case:** Complex patterns not covered by standard topologies

## Deployment Targets

### Local Deployment
```yaml
deployment:
  target: localhost
```

### Remote Host (SSH)
```yaml
deployment:
  target: remote
  host: worker-node-1.example.com
  user: agent-user
  python: /usr/bin/python3
  workdir: /opt/agents
```

### Container
```yaml
deployment:
  target: container
  image: agent-runtime:latest
  network: agent-network
```

### Kubernetes
```yaml
deployment:
  target: kubernetes
  namespace: agents
  service_type: ClusterIP
```

## Connection Resolution

The deployment engine automatically resolves connection URLs based on deployment targets:

- **Local → Local:** `http://localhost:PORT`
- **Local → Remote:** `http://REMOTE_HOST:PORT`
- **Remote → Remote:** `http://REMOTE_HOST:PORT`
- **Container → Container:** `http://CONTAINER_NAME:PORT` (on same network)

## Validation Rules

1. **Unique agent IDs** - No duplicate agent IDs within a job
2. **Valid connections** - All `from`/`to` references must exist
3. **Port conflicts** - No port conflicts on same deployment target
4. **Acyclic DAGs** - DAG topologies must be acyclic
5. **Reachable agents** - All agents must be reachable based on network topology
6. **Valid agent types** - Agent classes must exist and be importable

## Job Lifecycle

1. **Definition** - Write job YAML file
2. **Validation** - Validate job definition
3. **Planning** - Generate deployment plan
4. **Deployment** - Start agents on targets
5. **Connection** - Agents discover and connect
6. **Execution** - Workflow runs
7. **Monitoring** - Health checks and logging
8. **Shutdown** - Graceful termination

## Example: Simple Weather Workflow

```yaml
job:
  name: weather-query-workflow
  version: 1.0.0
  description: Simple weather querying with coordinator

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
  health_check:
    enabled: true
    interval: 5
    retries: 3

execution:
  entry_point: controller
  auto_start: true
```

## Example: Distributed Processing Pipeline

```yaml
job:
  name: distributed-analysis
  version: 1.0.0
  description: Multi-stage data analysis pipeline

agents:
  - id: ingest
    type: DataIngestAgent
    module: agents.ingest_agent
    config:
      port: 9001
    deployment:
      target: remote
      host: ingest-node.example.com
      user: pipeline

  - id: processor1
    type: ProcessorAgent
    module: agents.processor_agent
    config:
      port: 9002
      worker_id: 1
    deployment:
      target: remote
      host: worker1.example.com
      user: pipeline

  - id: processor2
    type: ProcessorAgent
    module: agents.processor_agent
    config:
      port: 9002
      worker_id: 2
    deployment:
      target: remote
      host: worker2.example.com
      user: pipeline

  - id: aggregator
    type: AggregatorAgent
    module: agents.aggregator_agent
    config:
      port: 9003
    deployment:
      target: remote
      host: aggregator-node.example.com
      user: pipeline

topology:
  type: pipeline
  stages: [ingest, [processor1, processor2], aggregator]
  # Note: [processor1, processor2] run in parallel

deployment:
  strategy: staged  # Deploy stage by stage
  timeout: 60
  health_check:
    enabled: true
    interval: 10
    retries: 5
```

## Advanced Features

### Environment Variables per Agent
```yaml
agents:
  - id: worker
    type: WorkerAgent
    environment:
      LOG_LEVEL: DEBUG
      API_KEY: ${SECRET_API_KEY}  # From environment
```

### Conditional Connections
```yaml
topology:
  connections:
    - from: controller
      to: worker1
      condition: "worker1.available"
```

### Resource Constraints
```yaml
agents:
  - id: heavy_processor
    resources:
      cpu: 4.0
      memory: 8G
      gpu: 1
```

### Health Check Endpoints
```yaml
agents:
  - id: agent1
    health_check:
      endpoint: /health
      method: GET
      expected_status: 200
```

### Retry Policies
```yaml
deployment:
  retry_policy:
    max_retries: 3
    backoff: exponential
    initial_delay: 5
```

## Deployment Engine Commands

```bash
# Validate job definition
uv run deploy validate jobs/my-job.yaml

# Plan deployment (dry run)
uv run deploy plan jobs/my-job.yaml

# Deploy job
uv run deploy start jobs/my-job.yaml

# Monitor job
uv run deploy status my-job

# Stop job
uv run deploy stop my-job

# List running jobs
uv run deploy list

# Show job logs
uv run deploy logs my-job [agent-id]
```

## MPI-like Features

Inspired by `mpirun`, the deployment engine supports:

- **Hostfile** - Deploy to hosts listed in file
- **Process per node** - Control agent distribution
- **Environment propagation** - Pass environment to all agents
- **Collective startup** - Synchronized agent initialization
- **Rank assignment** - Agents know their position in topology

Example:
```bash
# Deploy to hostfile
uv run deploy start job.yaml --hostfile hosts.txt

# Deploy N agents per host
uv run deploy start job.yaml --agents-per-host 4

# Pass environment
uv run deploy start job.yaml --env-file .env
```

## Security Considerations

1. **Authentication** - SSH keys for remote deployment
2. **Authorization** - Agent-to-agent authentication (future)
3. **Secrets** - Environment variable substitution
4. **Network** - Firewall rules, network policies
5. **Isolation** - Process/container isolation

## Future Extensions

1. **Auto-scaling** - Dynamic agent scaling based on load
2. **Failover** - Automatic recovery from agent failures
3. **Load balancing** - Distribute queries across replicas
4. **Service mesh** - Advanced networking with service mesh integration
5. **Observability** - Metrics, tracing, distributed logging
6. **GitOps** - Job definitions in version control with CD

## File Organization

```
jobs/
├── JOB_SPECIFICATION.md          # This file
├── schemas/
│   └── job-schema.json            # JSON schema for validation
├── examples/
│   ├── simple-weather.yaml        # Hub-spoke example
│   ├── pipeline.yaml              # Linear pipeline
│   ├── distributed-mesh.yaml      # Full mesh
│   └── complex-dag.yaml           # DAG workflow
└── templates/
    ├── hub-spoke.yaml             # Template for hub-spoke
    ├── pipeline.yaml              # Template for pipeline
    └── custom.yaml                # Template for custom topology
```

## See Also

- `ARCHITECTURE_UPGRADE.md` - Dynamic agent discovery system
- `UPGRADE_SUMMARY.md` - A2A transport and connectivity
- Deployment engine implementation (TBD)

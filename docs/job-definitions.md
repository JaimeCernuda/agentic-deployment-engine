# Job definitions

Job definitions are YAML files that declaratively describe multi-agent deployments. This document covers the complete job format and all topology patterns.

## Overview

A job definition specifies:
- **Agents** - What agents to deploy and how
- **Topology** - How agents connect to each other
- **Deployment** - Deployment strategy and health checks
- **Environment** - Global environment variables

## Basic structure

```yaml
job:
  name: my-job
  version: "1.0.0"
  description: "Job description"
  tags: [tag1, tag2]

agents:
  - id: agent-1
    type: WeatherAgent
    module: examples.agents.weather_agent
    config:
      port: 9001
    deployment:
      target: localhost

topology:
  type: hub-spoke
  hub: controller
  spokes: [agent-1, agent-2]

deployment:
  strategy: staged
  timeout: 60

environment:
  GLOBAL_VAR: value
```

## Job metadata

```yaml
job:
  name: unique-job-name      # Required: unique identifier
  version: "1.0.0"           # Required: semantic version
  description: "Description" # Required: human-readable description
  tags: [production, team-a] # Optional: tags for organization
```

## Agent configuration

Each agent requires:

```yaml
agents:
  - id: weather              # Unique ID within job
    type: WeatherAgent       # Python class name
    module: examples.agents.weather_agent  # Module path
    config:
      port: 9001             # Required: port number
      # Additional agent-specific config
    deployment:
      target: localhost      # Where to deploy
    resources:               # Optional: resource requirements
      cpu: 1.0
      memory: "512M"
```

### Deployment targets

#### Localhost
```yaml
deployment:
  target: localhost
```

#### Remote (SSH)
```yaml
deployment:
  target: remote
  host: server.example.com
  user: deploy               # Optional: defaults to current user
  ssh_key: ~/.ssh/id_ed25519 # Optional: defaults to ~/.ssh/id_rsa
  python: python3            # Optional: Python interpreter path
  workdir: /opt/agents       # Optional: working directory
  port: 22                   # Optional: SSH port
```

#### Container (Docker)
```yaml
deployment:
  target: container
  image: my-agent:latest
  network: agent-network     # Optional: Docker network
  container_name: weather    # Optional: container name
```

#### Kubernetes
```yaml
deployment:
  target: kubernetes
  namespace: agents
  service_type: ClusterIP    # ClusterIP, NodePort, LoadBalancer
```

### Environment variables

Per-agent environment variables:
```yaml
agents:
  - id: my-agent
    deployment:
      target: localhost
      environment:
        API_KEY: secret
        DEBUG: "true"
```

## Topology patterns

### Hub-and-spoke

Central coordinator with specialized workers. The hub deploys last after all spokes are ready.

```yaml
topology:
  type: hub-spoke
  hub: controller
  spokes: [weather, maps, database]
```

```
         Controller
         /   |   \
    Weather Maps Database
```

**Use when:** You have a central coordinator that orchestrates specialized agents.

**Example job:**
```yaml
job:
  name: weather-service
  version: "1.0.0"
  description: "Weather service with controller"

agents:
  - id: weather
    type: WeatherAgent
    module: examples.agents.weather_agent
    config:
      port: 9001
    deployment:
      target: localhost

  - id: maps
    type: MapsAgent
    module: examples.agents.maps_agent
    config:
      port: 9002
    deployment:
      target: localhost

  - id: controller
    type: ControllerAgent
    module: examples.agents.controller_agent
    config:
      port: 9000
    deployment:
      target: localhost

topology:
  type: hub-spoke
  hub: controller
  spokes: [weather, maps]
```

### Pipeline

Sequential processing stages. Each stage connects to the next.

```yaml
topology:
  type: pipeline
  stages: [intake, process, validate, output]
```

```
Intake → Process → Validate → Output
```

Stages can also be parallel:
```yaml
topology:
  type: pipeline
  stages:
    - intake                    # Stage 1
    - [worker-a, worker-b]      # Stage 2 (parallel)
    - aggregator                # Stage 3
```

**Use when:** Data flows through sequential processing steps.

**Example job:**
```yaml
job:
  name: data-pipeline
  version: "1.0.0"
  description: "Sequential data processing"

agents:
  - id: intake
    type: IntakeAgent
    module: agents.intake
    config:
      port: 9001
    deployment:
      target: localhost

  - id: transform
    type: TransformAgent
    module: agents.transform
    config:
      port: 9002
    deployment:
      target: localhost

  - id: output
    type: OutputAgent
    module: agents.output
    config:
      port: 9003
    deployment:
      target: localhost

topology:
  type: pipeline
  stages: [intake, transform, output]
```

### DAG (Directed Acyclic Graph)

Explicit connections between agents with parallel branches and convergence.

```yaml
topology:
  type: dag
  connections:
    - from: source
      to: [branch-a, branch-b]
    - from: branch-a
      to: merge
    - from: branch-b
      to: merge
    - from: merge
      to: sink
```

```
       ┌─ Branch-A ─┐
Source ─┤            ├─ Merge → Sink
       └─ Branch-B ─┘
```

**Use when:** You have complex dependencies with parallel branches.

**Example job:**
```yaml
job:
  name: parallel-processing
  version: "1.0.0"
  description: "DAG with parallel branches"

agents:
  - id: source
    type: SourceAgent
    module: agents.source
    config:
      port: 9001
    deployment:
      target: localhost

  - id: fast-path
    type: FastAgent
    module: agents.fast
    config:
      port: 9002
    deployment:
      target: localhost

  - id: slow-path
    type: SlowAgent
    module: agents.slow
    config:
      port: 9003
    deployment:
      target: localhost

  - id: merge
    type: MergeAgent
    module: agents.merge
    config:
      port: 9004
    deployment:
      target: localhost

topology:
  type: dag
  connections:
    - from: source
      to: [fast-path, slow-path]
    - from: fast-path
      to: merge
    - from: slow-path
      to: merge
```

### Mesh

All agents connect to all others. Every agent can communicate with every other agent.

```yaml
topology:
  type: mesh
  agents: [agent-1, agent-2, agent-3, agent-4]
```

```
  1 ←→ 2
  ↕ ╲╱ ↕
  ↕ ╱╲ ↕
  4 ←→ 3
```

**Use when:** Agents need peer-to-peer collaboration without central coordination.

**Example job:**
```yaml
job:
  name: collaborative-agents
  version: "1.0.0"
  description: "Full mesh collaboration"

agents:
  - id: researcher
    type: ResearchAgent
    module: agents.research
    config:
      port: 9001
    deployment:
      target: localhost

  - id: analyst
    type: AnalystAgent
    module: agents.analyst
    config:
      port: 9002
    deployment:
      target: localhost

  - id: writer
    type: WriterAgent
    module: agents.writer
    config:
      port: 9003
    deployment:
      target: localhost

topology:
  type: mesh
  agents: [researcher, analyst, writer]
```

### Hierarchical

Tree structure with multiple levels from root to leaves.

```yaml
topology:
  type: hierarchical
  root: ceo
  levels:
    - [vp-eng, vp-sales]           # Level 1 (reports to root)
    - [team-a, team-b, team-c]     # Level 2 (reports to level 1)
```

```
         CEO
        /   \
   VP-Eng   VP-Sales
   /   \        \
Team-A Team-B  Team-C
```

**Use when:** You have organizational hierarchy or domain decomposition.

**Example job:**
```yaml
job:
  name: hierarchical-system
  version: "1.0.0"
  description: "Multi-level coordination"

agents:
  - id: coordinator
    type: CoordinatorAgent
    module: agents.coordinator
    config:
      port: 9000
    deployment:
      target: localhost

  - id: weather-lead
    type: WeatherLeadAgent
    module: agents.weather_lead
    config:
      port: 9001
    deployment:
      target: localhost

  - id: maps-lead
    type: MapsLeadAgent
    module: agents.maps_lead
    config:
      port: 9002
    deployment:
      target: localhost

  - id: current-weather
    type: CurrentWeatherAgent
    module: agents.current_weather
    config:
      port: 9003
    deployment:
      target: localhost

  - id: forecast
    type: ForecastAgent
    module: agents.forecast
    config:
      port: 9004
    deployment:
      target: localhost

topology:
  type: hierarchical
  root: coordinator
  levels:
    - [weather-lead, maps-lead]
    - [current-weather, forecast]
```

## Deployment configuration

```yaml
deployment:
  strategy: staged           # sequential, parallel, or staged
  timeout: 60                # Overall timeout in seconds

  health_check:
    enabled: true
    interval: 5              # Seconds between checks
    retries: 3               # Retries before failure
    timeout: 5               # Timeout per check

  ssh:
    key_file: ~/.ssh/id_rsa
    timeout: 30

  network:
    allow_cross_host: true
```

### Deployment strategies

- **sequential**: Deploy one agent at a time
- **parallel**: Deploy all agents simultaneously
- **staged**: Deploy in topology-aware stages (recommended)

## Execution configuration

```yaml
execution:
  entry_point: controller    # Agent to receive initial queries
  auto_start: false          # Start workflow automatically
```

## Global environment

```yaml
environment:
  LOG_LEVEL: INFO
  API_ENDPOINT: https://api.example.com
  SHARED_SECRET: ${SECRET_FROM_ENV}
```

## Validation

Validate a job definition before deployment:

```bash
uv run deploy validate my-job.yaml
```

The validator checks:
- Required fields are present
- Agent IDs are unique
- Ports don't conflict on same host
- Topology references valid agent IDs
- DAG has no cycles

## CLI commands

```bash
# Validate job definition
uv run deploy validate job.yaml

# Preview deployment plan
uv run deploy plan job.yaml

# Deploy and run
uv run deploy start job.yaml

# Stop a running job (placeholder)
uv run deploy stop job-name
```

## See also

- [Getting started](getting-started.md) - Quick start guide
- [SSH deployment](ssh-deployment.md) - Remote deployment details
- [Architecture](architecture.md) - Topology patterns explained

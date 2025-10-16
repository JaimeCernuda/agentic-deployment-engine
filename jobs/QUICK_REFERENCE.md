# A2A Jobs System - Quick Reference

## Job Structure (YAML)

```yaml
job:
  name: my-workflow
  version: 1.0.0
  description: Description here

agents:
  - id: unique-id
    type: AgentClass
    module: agents.module_name
    config:
      port: 9001
    deployment:
      target: localhost|remote|container
    resources:
      cpu: 1.0
      memory: 2G

topology:
  type: hub-spoke|pipeline|dag|mesh|hierarchical
  # Pattern-specific config

deployment:
  strategy: sequential|parallel|staged
  timeout: 60

execution:
  entry_point: agent-id
  auto_start: true
```

## Topology Patterns

| Pattern | Use Case | Config |
|---------|----------|--------|
| **hub-spoke** | Coordinator + workers | `hub: id, spokes: [ids]` |
| **pipeline** | Sequential stages | `stages: [id1, id2, ...]` |
| **dag** | Parallel + convergence | `connections: [{from, to}, ...]` |
| **mesh** | Peer-to-peer | `agents: [id1, id2, ...]` |
| **hierarchical** | Multi-level tree | `root: id, levels: [...]` |

## Deployment Targets

```yaml
# Local
deployment:
  target: localhost

# Remote (SSH)
deployment:
  target: remote
  host: hostname.com
  user: username
  python: /usr/bin/python3

# Container
deployment:
  target: container
  image: agent-runtime:latest

# Kubernetes
deployment:
  target: kubernetes
  namespace: agents
```

## CLI Commands

```bash
# Validate
uv run deploy validate <job.yaml>

# Deploy
uv run deploy plan <job.yaml>           # Dry run
uv run deploy start <job.yaml>          # Deploy
uv run deploy start <job.yaml> --name X # Named

# Monitor
uv run deploy status <job-name>
uv run deploy logs <job-name>
uv run deploy logs <job-name> --follow

# Manage
uv run deploy stop <job-name>
uv run deploy restart <job-name>
uv run deploy list
uv run deploy inspect <job-name>

# MPI-like
uv run deploy start <job.yaml> --hostfile hosts.txt
uv run deploy start <job.yaml> --agents-per-host 4
```

## Examples

| File | Pattern | Description |
|------|---------|-------------|
| `simple-weather.yaml` | Hub-spoke | Controller + Weather + Maps (local) |
| `pipeline.yaml` | Pipeline | 4-stage data processing |
| `distributed-dag.yaml` | DAG | Multi-host parallel analysis |
| `collaborative-mesh.yaml` | Mesh | 5-agent collaboration |
| `hierarchical-tree.yaml` | Tree | 3-level geo-distributed |

## Quick Start

```bash
# 1. Navigate to jobs
cd clean_mcp_a2a/jobs

# 2. Validate an example
uv run deploy validate examples/simple-weather.yaml

# 3. Deploy locally
uv run deploy start examples/simple-weather.yaml

# 4. Check status
uv run deploy status simple-weather-workflow

# 5. Stop
uv run deploy stop simple-weather-workflow
```

## Connection Resolution

| Deployment | URL Format |
|------------|------------|
| localhost | `http://localhost:PORT` |
| remote | `http://HOSTNAME:PORT` |
| container | `http://CONTAINER_NAME:PORT` |

## Common Patterns

### Hub-Spoke (Coordinator + Workers)
```yaml
topology:
  type: hub-spoke
  hub: coordinator
  spokes: [worker1, worker2]
```

### Pipeline (Sequential)
```yaml
topology:
  type: pipeline
  stages: [stage1, stage2, stage3]
```

### DAG (Fan-out + Converge)
```yaml
topology:
  type: dag
  connections:
    - from: source
      to: worker1
    - from: source
      to: worker2
    - from: worker1
      to: sink
    - from: worker2
      to: sink
```

### Mesh (All-to-All)
```yaml
topology:
  type: mesh
  agents: [agent1, agent2, agent3]
```

## Files

- **README.md** - User guide
- **JOB_SPECIFICATION.md** - Complete spec
- **DEPLOYMENT_ENGINE.md** - Architecture
- **examples/** - Example jobs
- **schemas/** - JSON schemas

## Integration

Jobs work with:
- `src/agent_registry.py` - Dynamic discovery
- `src/a2a_transport.py` - SDK MCP transport
- `src/base_a2a_agent.py` - `connected_agents` parameter

Agents automatically:
1. Discover connected agents on startup
2. Generate system prompts from capabilities
3. Use SDK MCP for efficient communication

## Implementation Status

✅ Job specification
✅ Example workflows
✅ Deployment architecture
🚧 Parser & validator
🚧 Deployment engine
🚧 CLI tool

## Next Steps

1. Implement data models
2. Build parser & validator
3. Create local deployer
4. Build CLI
5. Test with examples

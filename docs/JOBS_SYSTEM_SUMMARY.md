# A2A Jobs System - Planning Summary

## What We Built

A comprehensive **job definition and deployment system** for multi-agent workflows, inspired by MPI's mpirun approach to distributed computing.

## Goals Achieved

### 1. ✅ Job Definition Format
**Document:** `jobs/JOB_SPECIFICATION.md`

- **Declarative YAML format** for defining agent workflows
- **5 topology patterns:** Hub-spoke, pipeline, DAG, mesh, hierarchical
- **Multiple deployment targets:** Local, remote (SSH), container, Kubernetes
- **Complete specification** with validation rules, examples, and best practices
- **Environment-agnostic** - same job works locally or distributed

### 2. ✅ Example Job Definitions
**Directory:** `jobs/examples/`

Created 5 comprehensive example workflows:

- **simple-weather.yaml** - Hub-and-spoke (controller + workers)
- **pipeline.yaml** - 4-stage linear data processing
- **distributed-dag.yaml** - Parallel branches with convergence across hosts
- **collaborative-mesh.yaml** - 5-agent peer-to-peer collaboration
- **hierarchical-tree.yaml** - 3-level geographic distribution

Each example demonstrates:
- Different topology pattern
- Various deployment strategies
- Real-world use cases
- Best practices

### 3. ✅ Deployment Engine Architecture
**Document:** `jobs/DEPLOYMENT_ENGINE.md`

Complete architectural design including:

**Components:**
- JobParser - YAML → Python objects
- JobValidator - Schema & constraint checking
- DeploymentPlanner - Dependency resolution & ordering
- DeploymentOrchestrator - Execute deployment
- HealthMonitor - Connectivity & health checks
- JobRegistry - Track deployed jobs

**Deployment Strategies:**
- Sequential (one after another)
- Parallel (all at once)
- Staged (by dependency level)
- Top-down (hierarchical)

**Deployers:**
- LocalDeployer (subprocess)
- RemoteDeployer (SSH)
- ContainerDeployer (Docker)
- KubernetesDeployer (K8s)

### 4. ✅ Comprehensive Documentation
**Document:** `jobs/README.md`

Complete user guide covering:
- Quick start guide
- Architecture overview
- All topology patterns with diagrams
- Deployment targets
- CLI commands
- Best practices
- Integration with existing A2A system

## System Architecture

```
┌────────────────────────────────────────────────────────────┐
│                  Job Definition (YAML)                      │
│  Declarative workflow: agents, topology, deployment        │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│               Deployment Engine                             │
│                                                              │
│  Parse → Validate → Plan → Deploy → Monitor                │
│                                                              │
│  • LocalDeployer (subprocess)                               │
│  • RemoteDeployer (SSH)                                     │
│  • ContainerDeployer (Docker)                               │
│  • Health & Connectivity Monitoring                         │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ↓
┌────────────────────────────────────────────────────────────┐
│            Running Agent Workflow                           │
│                                                              │
│  Agents with:                                               │
│  • Dynamic discovery (via AgentRegistry)                    │
│  • SDK MCP A2A transport (fast HTTP)                        │
│  • Auto-configured connections                              │
└────────────────────────────────────────────────────────────┘
```

## Key Features

### Declarative Workflows
```yaml
job:
  name: my-workflow

agents:
  - id: agent1
    type: WeatherAgent
    config: {...}

topology:
  type: hub-spoke
  hub: controller
  spokes: [agent1, agent2]
```

### Multiple Topologies
- **Hub-Spoke:** Coordinator + workers
- **Pipeline:** Sequential stages
- **DAG:** Parallel branches + convergence
- **Mesh:** All-to-all collaboration
- **Hierarchical:** Multi-level tree

### Distributed Deployment
```yaml
deployment:
  target: remote
  host: worker-1.example.com
  user: agent-user
```

### MPI-like Interface
```bash
uv run deploy start job.yaml --hostfile hosts.txt
uv run deploy start job.yaml --agents-per-host 4
```

### Connection Resolution
Automatic URL resolution based on deployment:
- Local → Local: `http://localhost:PORT`
- Local → Remote: `http://HOST:PORT`
- Container → Container: `http://CONTAINER:PORT`

## Integration with A2A Architecture

The jobs system builds on the upgraded A2A architecture:

### 1. Dynamic Discovery (`src/agent_registry.py`)
- Jobs specify `connected_agents` URLs
- Agents discover capabilities on startup
- System prompts auto-generated

### 2. SDK MCP Transport (`src/a2a_transport.py`)
- Fast HTTP-based communication
- No Bash/curl overhead
- Tools: `query_agent`, `discover_agent`

### 3. Enhanced BaseA2AAgent
- Supports `connected_agents` parameter
- Automatic discovery via `agent_registry`
- Reusable with any connections

**Job System Adds:**
- Declarative workflow definition
- Automated deployment orchestration
- Health monitoring
- Lifecycle management

## Workflow Example

### Define (`jobs/my-workflow.yaml`)
```yaml
agents:
  - id: weather
    type: WeatherAgent
    deployment:
      target: remote
      host: worker1.example.com

  - id: controller
    type: ControllerAgent
    deployment:
      target: localhost

topology:
  type: hub-spoke
  hub: controller
  spokes: [weather]
```

### Deploy
```bash
# Validate
uv run deploy validate jobs/my-workflow.yaml

# Deploy
uv run deploy start jobs/my-workflow.yaml

# Engine:
# 1. Parses YAML → JobDefinition
# 2. Validates agents, topology, resources
# 3. Plans: weather first (spoke), then controller (hub)
# 4. Deploys:
#    - SSH to worker1.example.com, start weather agent
#    - Start controller locally with weather_url
# 5. Validates:
#    - Health check weather @ http://worker1.example.com:9001
#    - Health check controller @ http://localhost:9000
#    - Verify controller can reach weather
# 6. Registers job in JobRegistry
# 7. Continuous monitoring
```

### Monitor
```bash
# Check status
uv run deploy status my-workflow

# View logs
uv run deploy logs my-workflow

# Stop
uv run deploy stop my-workflow
```

## File Structure

```
jobs/
├── README.md                      # User guide
├── JOB_SPECIFICATION.md           # Complete spec
├── DEPLOYMENT_ENGINE.md           # Architecture
│
├── examples/
│   ├── simple-weather.yaml        # Hub-spoke
│   ├── pipeline.yaml              # Pipeline
│   ├── distributed-dag.yaml       # DAG
│   ├── collaborative-mesh.yaml    # Mesh
│   └── hierarchical-tree.yaml     # Hierarchical
│
├── schemas/                        # JSON schemas (TBD)
│   └── job-schema.json
│
└── templates/                      # Templates (TBD)
    ├── hub-spoke.yaml
    ├── pipeline.yaml
    └── dag.yaml
```

## Implementation Roadmap

### Phase 1: Core (MVP)
**Status:** Designed, ready to implement

**Tasks:**
1. Implement data models (`src/deployment/models.py`)
2. Implement JobParser (`src/deployment/parser.py`)
3. Implement basic JobValidator (`src/deployment/validator.py`)
4. Implement LocalDeployer (`src/deployment/deployers/local.py`)
5. Implement basic orchestrator for hub-spoke
6. Build CLI (`src/cli/deploy.py`)
7. Test with `simple-weather.yaml`

**Estimate:** 2-3 days

### Phase 2: Monitoring
**Tasks:**
1. Implement HealthMonitor (`src/deployment/monitor.py`)
2. Implement JobRegistry (`src/deployment/registry.py`)
3. Add status/logs/inspect commands
4. Connection validation

**Estimate:** 1-2 days

### Phase 3: Distributed
**Tasks:**
1. Implement RemoteDeployer (SSH)
2. Connection resolution for remote
3. All topology patterns (pipeline, DAG, mesh, hierarchical)
4. Test with distributed examples

**Estimate:** 2-3 days

### Phase 4: Production
**Tasks:**
1. ContainerDeployer
2. KubernetesDeployer
3. Auto-scaling
4. Fault tolerance
5. Metrics & observability

**Estimate:** 1-2 weeks

## Next Steps

### Immediate (Phase 1)
1. **Create directory structure:**
   ```bash
   mkdir -p src/deployment/deployers
   mkdir -p src/cli
   ```

2. **Implement data models:**
   - `JobDefinition`
   - `AgentConfig`
   - `DeploymentPlan`
   - `DeployedJob`

3. **Implement JobParser:**
   - YAML parsing
   - Environment variable substitution
   - Basic validation

4. **Implement LocalDeployer:**
   - Subprocess management
   - Health checking
   - Connection URL resolution

5. **Build CLI:**
   - `validate` command
   - `start` command
   - `stop` command
   - `status` command

6. **Test:**
   - Deploy `simple-weather.yaml` locally
   - Verify agents start
   - Verify connectivity
   - Test stop/restart

### Future Enhancements
- **Job templates** - Pre-built job templates for common patterns
- **Job composition** - Include/extend other job definitions
- **Conditional deployment** - Deploy based on conditions
- **Resource scheduling** - Optimize agent placement
- **Cost estimation** - Estimate resource costs before deployment
- **Visualization** - Graphical job topology view
- **GitOps integration** - Deploy jobs from git commits

## Benefits

### For Developers
- **Declarative** - Define what, not how
- **Reusable** - Same job, different environments
- **Testable** - Validate before deploy
- **Portable** - Local to distributed seamlessly

### For Operations
- **Automated** - No manual agent startup
- **Monitored** - Built-in health checks
- **Reliable** - Consistent deployment process
- **Scalable** - Distribute across nodes

### For Research
- **Reproducible** - Job definitions in version control
- **Configurable** - Easy parameter changes
- **Shareable** - Share job definitions with team
- **Documented** - Self-documenting workflow structure

## Comparison to MPI

| Feature | MPI (mpirun) | A2A Jobs |
|---------|--------------|----------|
| **Definition** | Command-line args | YAML files |
| **Processes** | MPI processes | A2A agents |
| **Topology** | Fixed (rank-based) | Flexible (hub-spoke, DAG, mesh, etc.) |
| **Communication** | MPI primitives | HTTP/A2A protocol |
| **Discovery** | Static ranks | Dynamic discovery |
| **Deployment** | Hostfile, SSH | Hostfile, SSH, containers, K8s |
| **Monitoring** | Limited | Built-in health checks |
| **Use Case** | HPC computing | Multi-agent AI workflows |

**Similarities:**
- Distributed deployment
- Hostfile support
- Process coordination
- Environment propagation

**Differences:**
- A2A is HTTP-based (vs MPI message passing)
- Dynamic agent discovery (vs static ranks)
- Flexible topologies (vs fixed communication patterns)
- AI-first design (vs numerical computing)

## Questions & Answers

**Q: Do I need to modify existing agents?**
A: No, existing agents work as-is. Jobs just configure their `connected_agents` parameter.

**Q: Can I mix local and remote agents?**
A: Yes! Jobs support hybrid deployment. Some agents local, others remote.

**Q: How do agents know how to connect?**
A: The deployment engine resolves URLs and passes them to agents via `connected_agents`.

**Q: What if an agent crashes?**
A: Phase 2 adds restart policies. Phase 4 adds fault tolerance.

**Q: Can I deploy the same job to different environments?**
A: Yes! Same job definition, just change deployment targets (localhost vs prod hosts).

**Q: How do I add a new agent type?**
A: Create the agent class, then reference it in job YAML (`type: MyAgent`, `module: agents.my_agent`).

**Q: Is this production-ready?**
A: Designed yes, implemented not yet. Phase 1-3 get to production-grade.

**Q: Can I use with Kubernetes?**
A: Designed for it (Phase 4). K8s deployment target planned.

## Conclusion

We've designed a comprehensive **job definition and deployment system** that:

✅ Provides declarative workflow definition
✅ Supports 5 common topology patterns
✅ Enables distributed deployment
✅ Integrates with existing A2A architecture
✅ Follows MPI-like interface patterns
✅ Includes complete documentation and examples

**Ready for implementation** - all design work complete, clear roadmap, comprehensive specs.

## References

- **Job Specification:** `jobs/JOB_SPECIFICATION.md`
- **Deployment Engine:** `jobs/DEPLOYMENT_ENGINE.md`
- **User Guide:** `jobs/README.md`
- **Examples:** `jobs/examples/*.yaml`
- **A2A Architecture:** `ARCHITECTURE_UPGRADE.md`
- **Dynamic Discovery:** `src/agent_registry.py`
- **A2A Transport:** `src/a2a_transport.py`

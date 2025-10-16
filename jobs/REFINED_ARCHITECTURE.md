# Refined Deployment Architecture

## Clarified Components

After discussion, here's the refined architecture with clear separation:

```
┌─────────────────────────────────────────────────────────┐
│              Job Definition (YAML)                       │
└────────────────────────┬────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────┐
│  1. JobLoader                                            │
│     - Parse YAML → Python objects (pydantic)            │
│     - Validate schema and constraints                    │
│     - Check agents are importable                        │
└────────────────────────┬────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────┐
│  2. TopologyResolver                                     │
│     - Parse topology pattern (hub-spoke, DAG, etc.)     │
│     - Generate deployment order                          │
│     - Resolve connection URLs                            │
│     - Output: DeploymentPlan                            │
└────────────────────────┬────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────┐
│  3. AgentDeployer                                        │
│     - Execute DeploymentPlan                             │
│     - Start agents via:                                  │
│       • LocalRunner (subprocess)                         │
│       • SSHRunner (remote via SSH)                       │
│       • DockerRunner (containers)                        │
│     - Wait for health checks                             │
│     - Output: DeployedJob                               │
└────────────────────────┬────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────┐
│  4. JobMonitor (Optional)                                │
│     - Heartbeat agents if --monitor flag                │
│     - Report failures                                    │
└─────────────────────────────────────────────────────────┘
```

## Component Details

### 1. JobLoader
**Responsibility:** Parse and validate job file

```python
class JobLoader:
    """Load and validate job definitions."""

    def load(self, yaml_path: str) -> JobDefinition:
        """Load job from YAML."""
        # 1. Parse YAML
        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        # 2. Pydantic validation (schema)
        job = JobDefinition(**data)

        # 3. Validate agents exist
        for agent in job.agents:
            self._check_importable(agent.module, agent.type)

        # 4. Validate topology references
        agent_ids = {a.id for a in job.agents}
        self._validate_topology_refs(job.topology, agent_ids)

        # 5. Check port conflicts
        self._check_port_conflicts(job.agents)

        return job
```

**Output:** Valid `JobDefinition` object

---

### 2. TopologyResolver
**Responsibility:** Understand topology pattern and create deployment plan

This is the "intelligent" component that knows about patterns.

```python
class TopologyResolver:
    """Resolve topology patterns into deployment plans."""

    def resolve(self, job: JobDefinition) -> DeploymentPlan:
        """Generate deployment plan from topology."""

        # 1. Get deployment order based on topology type
        order = self._resolve_order(job.topology, job.agents)

        # 2. Resolve URLs for each agent
        urls = self._resolve_urls(job.agents)

        # 3. Determine connections for each agent
        connections = self._resolve_connections(job.topology, urls)

        return DeploymentPlan(
            stages=order,
            agent_urls=urls,
            connections=connections
        )

    def _resolve_order(self, topology: TopologyConfig, agents: List[AgentConfig]) -> List[List[str]]:
        """Resolve deployment order by topology pattern.

        Returns list of stages, where each stage is list of agent IDs
        that can be deployed in parallel.

        Example: [[agent1, agent2], [agent3]]
                 Stage 1: deploy agent1 and agent2 in parallel
                 Stage 2: deploy agent3 after stage 1 completes
        """

        if topology.type == "hub-spoke":
            # Stage 1: All spokes (parallel)
            # Stage 2: Hub (after spokes ready)
            return [
                topology.spokes,      # Stage 1
                [topology.hub]        # Stage 2
            ]

        elif topology.type == "pipeline":
            # Sequential stages
            return [[stage] for stage in topology.stages]

        elif topology.type == "dag":
            # Topological sort → group by levels
            return self._dag_to_stages(topology.connections)

        elif topology.type == "mesh":
            # All at once (parallel)
            return [topology.agents]

        elif topology.type == "hierarchical":
            # Root first, then level by level
            return self._hierarchical_to_stages(topology)

    def _resolve_urls(self, agents: List[AgentConfig]) -> Dict[str, str]:
        """Resolve URL for each agent based on deployment target."""
        urls = {}

        for agent in agents:
            if agent.deployment.target == "localhost":
                urls[agent.id] = f"http://localhost:{agent.config.port}"

            elif agent.deployment.target == "remote":
                host = agent.deployment.host
                urls[agent.id] = f"http://{host}:{agent.config.port}"

            elif agent.deployment.target == "container":
                container = agent.deployment.container_name
                urls[agent.id] = f"http://{container}:{agent.config.port}"

        return urls

    def _resolve_connections(self, topology: TopologyConfig, urls: Dict[str, str]) -> Dict[str, List[str]]:
        """Determine which URLs each agent should connect to."""
        connections = {}

        if topology.type == "hub-spoke":
            # Hub connects to all spokes
            connections[topology.hub] = [urls[s] for s in topology.spokes]
            # Spokes don't connect to anyone
            for spoke in topology.spokes:
                connections[spoke] = []

        elif topology.type == "pipeline":
            # Each stage connects to next
            for i, stage in enumerate(topology.stages):
                if i < len(topology.stages) - 1:
                    next_stage = topology.stages[i + 1]
                    connections[stage] = [urls[next_stage]]
                else:
                    connections[stage] = []  # Last stage

        elif topology.type == "dag":
            # Based on explicit connections
            connections = self._dag_connections(topology.connections, urls)

        elif topology.type == "mesh":
            # Everyone connects to everyone else
            for agent_id in topology.agents:
                others = [urls[a] for a in topology.agents if a != agent_id]
                connections[agent_id] = others

        elif topology.type == "hierarchical":
            connections = self._hierarchical_connections(topology, urls)

        return connections

    def _dag_to_stages(self, connections: List[Connection]) -> List[List[str]]:
        """Convert DAG connections to deployment stages via topological sort."""
        import networkx as nx

        # Build graph
        G = nx.DiGraph()
        for conn in connections:
            G.add_edge(conn.from_, conn.to)

        # Topological sort → generation levels
        stages = []
        for generation in nx.topological_generations(G):
            stages.append(list(generation))

        return stages
```

**Output:** `DeploymentPlan` with:
- `stages` - Ordered list of agent groups to deploy
- `agent_urls` - URL for each agent
- `connections` - Which URLs each agent should connect to

---

### 3. AgentDeployer
**Responsibility:** Execute the deployment plan using appropriate runners

This component **doesn't care about topology** - it just executes the plan.

```python
class AgentDeployer:
    """Deploy agents according to plan."""

    def __init__(self):
        self.runners = {
            "localhost": LocalRunner(),
            "remote": SSHRunner(),
            "container": DockerRunner()
        }

    async def deploy(self, job: JobDefinition, plan: DeploymentPlan) -> DeployedJob:
        """Execute deployment plan."""
        deployed_agents = {}

        # Deploy stage by stage
        for stage in plan.stages:
            print(f"Deploying stage: {stage}")

            # Deploy all agents in this stage (in parallel)
            tasks = []
            for agent_id in stage:
                task = self._deploy_agent(job, agent_id, plan)
                tasks.append(task)

            # Wait for all agents in stage to be ready
            stage_agents = await asyncio.gather(*tasks)
            deployed_agents.update(dict(zip(stage, stage_agents)))

        return DeployedJob(
            job_id=job.job.name,
            definition=job,
            agents=deployed_agents,
            urls=plan.agent_urls,
            start_time=datetime.now()
        )

    async def _deploy_agent(self, job: JobDefinition, agent_id: str, plan: DeploymentPlan):
        """Deploy a single agent."""
        agent_config = job.get_agent(agent_id)

        # 1. Select appropriate runner
        runner = self.runners[agent_config.deployment.target]

        # 2. Get connected agent URLs for this agent
        connected_urls = plan.connections.get(agent_id, [])

        # 3. Start agent
        print(f"  Starting {agent_id}...")
        process = await runner.start(agent_config, connected_urls)

        # 4. Wait for health check
        agent_url = plan.agent_urls[agent_id]
        await self._wait_for_health(agent_url)
        print(f"  ✓ {agent_id} healthy at {agent_url}")

        return process


class LocalRunner:
    """Run agents locally via subprocess."""

    async def start(self, agent: AgentConfig, connected_urls: List[str]) -> subprocess.Popen:
        """Start agent locally."""

        # Build command
        cmd = [
            "uv", "run",
            agent.module.replace(".", "/").replace("/", "-")  # module → CLI command
        ]

        # Set environment with connected agents
        env = os.environ.copy()
        env.update(agent.deployment.environment or {})

        # Pass connected agents via environment or config
        # (Alternative: agents could read from config file we generate)

        # Start process
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        return process


class SSHRunner:
    """Run agents on remote hosts via SSH."""

    async def start(self, agent: AgentConfig, connected_urls: List[str]):
        """Start agent on remote host via SSH."""
        import paramiko

        # SSH connection
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            agent.deployment.host,
            username=agent.deployment.user,
            key_filename=agent.deployment.ssh_key
        )

        # Build command
        workdir = agent.deployment.workdir or "/opt/agents"
        python = agent.deployment.python or "python3"

        cmd = f"cd {workdir} && {python} -m {agent.module}"

        # Execute in background
        stdin, stdout, stderr = ssh.exec_command(f"nohup {cmd} > /dev/null 2>&1 & echo $!")
        pid = int(stdout.read().decode().strip())

        # Return reference to remote process
        return RemoteProcess(ssh, pid, agent.id)


class DockerRunner:
    """Run agents in Docker containers."""

    async def start(self, agent: AgentConfig, connected_urls: List[str]):
        """Start agent in Docker container."""
        import docker

        client = docker.from_env()

        # Build environment
        env = {
            "AGENT_PORT": str(agent.config.port),
            "CONNECTED_AGENTS": ",".join(connected_urls)
        }
        env.update(agent.deployment.environment or {})

        # Start container
        container = client.containers.run(
            agent.deployment.image,
            command=f"python -m {agent.module}",
            environment=env,
            network=agent.deployment.network,
            detach=True,
            name=f"agent-{agent.id}"
        )

        return container
```

**Output:** `DeployedJob` with running agent processes

---

### 4. JobMonitor (Optional)
**Responsibility:** Monitor running agents

```python
class JobMonitor:
    """Monitor deployed jobs."""

    async def monitor(self, deployed: DeployedJob, interval: int = 10):
        """Monitor job continuously."""
        print(f"Monitoring {deployed.job_id}...")

        while True:
            await asyncio.sleep(interval)

            for agent_id in deployed.agents:
                url = deployed.urls[agent_id]

                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(f"{url}/health", timeout=5)

                        if response.status_code == 200:
                            print(f"✓ {agent_id}: healthy")
                        else:
                            print(f"⚠️  {agent_id}: status {response.status_code}")

                except Exception as e:
                    print(f"✗ {agent_id}: {e}")
```

---

## Data Flow

```python
# CLI entry point
def deploy_command(yaml_path: str, monitor: bool = False):
    # 1. Load and validate
    loader = JobLoader()
    job = loader.load(yaml_path)
    print("✓ Job valid")

    # 2. Resolve topology → deployment plan
    resolver = TopologyResolver()
    plan = resolver.resolve(job)
    print(f"✓ Deployment plan: {len(plan.stages)} stages")

    # 3. Execute deployment
    deployer = AgentDeployer()
    deployed = await deployer.deploy(job, plan)
    print(f"✓ Deployed {len(deployed.agents)} agents")

    # 4. Monitor (optional)
    if monitor:
        monitor = JobMonitor()
        await monitor.monitor(deployed)
```

## Topology Examples

### Hub-Spoke
```python
# Input topology:
topology:
  type: hub-spoke
  hub: controller
  spokes: [weather, maps]

# TopologyResolver output:
DeploymentPlan(
    stages=[
        ["weather", "maps"],  # Stage 1: spokes in parallel
        ["controller"]        # Stage 2: hub after spokes
    ],
    agent_urls={
        "weather": "http://localhost:9001",
        "maps": "http://localhost:9002",
        "controller": "http://localhost:9000"
    },
    connections={
        "weather": [],
        "maps": [],
        "controller": ["http://localhost:9001", "http://localhost:9002"]
    }
)
```

### DAG
```python
# Input topology:
topology:
  type: dag
  connections:
    - from: ingest
      to: processor1
    - from: ingest
      to: processor2
    - from: processor1
      to: output
    - from: processor2
      to: output

# TopologyResolver output:
DeploymentPlan(
    stages=[
        ["ingest"],                      # Stage 1
        ["processor1", "processor2"],    # Stage 2 (parallel)
        ["output"]                       # Stage 3
    ],
    connections={
        "ingest": [],
        "processor1": ["http://localhost:9003"],  # → output
        "processor2": ["http://localhost:9003"],  # → output
        "output": []
    }
)
```

## Summary

**4 Clear Components:**

1. **JobLoader** - Parse YAML, validate schema
2. **TopologyResolver** - Understand patterns, create plan (this was your "planner")
3. **AgentDeployer** - Execute plan via runners (this was your "deployer")
4. **JobMonitor** - Optional heartbeat

**Separation of Concerns:**
- TopologyResolver: "What to deploy and in what order?"
- AgentDeployer: "How to start agents?" (subprocess, SSH, Docker)

**Clean Interface:**
```python
job = JobLoader().load(yaml_path)           # Parse
plan = TopologyResolver().resolve(job)       # Plan
deployed = AgentDeployer().deploy(job, plan) # Deploy
JobMonitor().monitor(deployed)               # Monitor (optional)
```

Does this clarification make sense? The TopologyResolver is the "smart" component that understands patterns, while AgentDeployer is the "execution" component that just starts processes.

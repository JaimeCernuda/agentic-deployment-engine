"""Topology resolver - convert topology patterns to deployment plans."""

from typing import List, Dict, Set
from .models import JobDefinition, DeploymentPlan, TopologyConfig, AgentConfig


class TopologyResolver:
    """Resolve topology patterns into deployment plans."""

    def resolve(self, job: JobDefinition) -> DeploymentPlan:
        """Generate deployment plan from job topology.

        Args:
            job: Job definition

        Returns:
            DeploymentPlan with stages, URLs, and connections
        """
        # 1. Resolve deployment order (stages)
        stages = self._resolve_stages(job.topology, job.agents)

        # 2. Resolve URLs for each agent
        agent_urls = self._resolve_urls(job.agents)

        # 3. Resolve connections for each agent
        connections = self._resolve_connections(job.topology, agent_urls)

        return DeploymentPlan(
            job_name=job.job.name,
            stages=stages,
            agent_urls=agent_urls,
            connections=connections
        )

    def _resolve_stages(self, topology: TopologyConfig, agents: List[AgentConfig]) -> List[List[str]]:
        """Resolve deployment order based on topology type.

        Returns list of stages, where each stage is list of agent IDs
        that can be deployed in parallel.

        Example: [["agent1", "agent2"], ["agent3"]]
                 Stage 1: deploy agent1 and agent2 in parallel
                 Stage 2: deploy agent3 after stage 1 completes
        """
        if topology.type == "hub-spoke":
            return self._hub_spoke_stages(topology)

        elif topology.type == "pipeline":
            return self._pipeline_stages(topology)

        elif topology.type == "dag":
            return self._dag_stages(topology)

        elif topology.type == "mesh":
            return self._mesh_stages(topology)

        elif topology.type == "hierarchical":
            return self._hierarchical_stages(topology)

        else:
            raise ValueError(f"Unknown topology type: {topology.type}")

    def _hub_spoke_stages(self, topology: TopologyConfig) -> List[List[str]]:
        """Hub-spoke: spokes first (parallel), then hub."""
        return [
            topology.spokes,      # Stage 1: all spokes in parallel
            [topology.hub]        # Stage 2: hub after spokes
        ]

    def _pipeline_stages(self, topology: TopologyConfig) -> List[List[str]]:
        """Pipeline: sequential stages."""
        return [[stage] for stage in topology.stages]

    def _dag_stages(self, topology: TopologyConfig) -> List[List[str]]:
        """DAG: topological sort into levels."""
        # Build dependency graph
        graph = {}  # agent_id -> list of dependencies
        all_agents = set()

        for conn in topology.connections:
            all_agents.add(conn.from_)

            # Handle 'to' as string or list
            to_agents = [conn.to] if isinstance(conn.to, str) else conn.to
            for to_agent in to_agents:
                all_agents.add(to_agent)
                if to_agent not in graph:
                    graph[to_agent] = []
                graph[to_agent].append(conn.from_)

        # Agents with no dependencies
        for agent in all_agents:
            if agent not in graph:
                graph[agent] = []

        # Topological sort by levels
        stages = []
        remaining = set(all_agents)

        while remaining:
            # Find agents with no unsatisfied dependencies
            ready = []
            for agent in remaining:
                deps = graph[agent]
                if all(dep not in remaining for dep in deps):
                    ready.append(agent)

            if not ready:
                raise ValueError("Circular dependency detected in DAG")

            stages.append(ready)
            remaining -= set(ready)

        return stages

    def _mesh_stages(self, topology: TopologyConfig) -> List[List[str]]:
        """Mesh: all agents in parallel."""
        return [topology.agents]

    def _hierarchical_stages(self, topology: TopologyConfig) -> List[List[str]]:
        """Hierarchical: root first, then level by level."""
        stages = [[topology.root]]  # Root first

        # Process levels
        for level in topology.levels:
            children = level.get("children", [])
            if children:
                stages.append(children)

        return stages

    def _resolve_urls(self, agents: List[AgentConfig]) -> Dict[str, str]:
        """Resolve URL for each agent based on deployment target."""
        urls = {}

        for agent in agents:
            port = agent.config.get("port")
            if not port:
                raise ValueError(f"Agent {agent.id} missing 'port' in config")

            if agent.deployment.target == "localhost":
                urls[agent.id] = f"http://localhost:{port}"

            elif agent.deployment.target == "remote":
                host = agent.deployment.host
                if not host:
                    raise ValueError(f"Agent {agent.id} missing 'host' for remote deployment")
                urls[agent.id] = f"http://{host}:{port}"

            elif agent.deployment.target == "container":
                container = agent.deployment.container_name or agent.id
                urls[agent.id] = f"http://{container}:{port}"

            else:
                raise ValueError(f"Unknown deployment target: {agent.deployment.target}")

        return urls

    def _resolve_connections(self, topology: TopologyConfig, urls: Dict[str, str]) -> Dict[str, List[str]]:
        """Determine which URLs each agent should connect to.

        Returns dict mapping agent_id to list of URLs to connect to.
        """
        connections = {}

        if topology.type == "hub-spoke":
            connections = self._hub_spoke_connections(topology, urls)

        elif topology.type == "pipeline":
            connections = self._pipeline_connections(topology, urls)

        elif topology.type == "dag":
            connections = self._dag_connections(topology, urls)

        elif topology.type == "mesh":
            connections = self._mesh_connections(topology, urls)

        elif topology.type == "hierarchical":
            connections = self._hierarchical_connections(topology, urls)

        return connections

    def _hub_spoke_connections(self, topology: TopologyConfig, urls: Dict[str, str]) -> Dict[str, List[str]]:
        """Hub connects to all spokes, spokes don't connect to anyone."""
        connections = {}

        # Hub connects to all spokes
        connections[topology.hub] = [urls[spoke] for spoke in topology.spokes]

        # Spokes don't connect to anyone
        for spoke in topology.spokes:
            connections[spoke] = []

        return connections

    def _pipeline_connections(self, topology: TopologyConfig, urls: Dict[str, str]) -> Dict[str, List[str]]:
        """Each stage connects to next stage."""
        connections = {}

        for i, stage in enumerate(topology.stages):
            if i < len(topology.stages) - 1:
                next_stage = topology.stages[i + 1]
                connections[stage] = [urls[next_stage]]
            else:
                connections[stage] = []  # Last stage

        return connections

    def _dag_connections(self, topology: TopologyConfig, urls: Dict[str, str]) -> Dict[str, List[str]]:
        """Based on explicit connections in DAG."""
        connections = {}

        # Initialize all agents with empty connections
        all_agents = set()
        for conn in topology.connections:
            all_agents.add(conn.from_)
            to_agents = [conn.to] if isinstance(conn.to, str) else conn.to
            all_agents.update(to_agents)

        for agent in all_agents:
            connections[agent] = []

        # Build connections: who connects to whom
        # In DAG, if A → B, then A should connect to B
        for conn in topology.connections:
            to_agents = [conn.to] if isinstance(conn.to, str) else conn.to
            for to_agent in to_agents:
                if conn.from_ not in connections:
                    connections[conn.from_] = []
                connections[conn.from_].append(urls[to_agent])

        return connections

    def _mesh_connections(self, topology: TopologyConfig, urls: Dict[str, str]) -> Dict[str, List[str]]:
        """Everyone connects to everyone else."""
        connections = {}

        for agent_id in topology.agents:
            # Connect to all other agents
            other_urls = [urls[other] for other in topology.agents if other != agent_id]
            connections[agent_id] = other_urls

        return connections

    def _hierarchical_connections(self, topology: TopologyConfig, urls: Dict[str, str]) -> Dict[str, List[str]]:
        """Parent connects to children."""
        connections = {}

        # Root has no connections up
        connections[topology.root] = []

        # Process levels
        for level in topology.levels:
            parent = level.get("parent")
            children = level.get("children", [])

            if parent:
                # Parent connects to children
                connections[parent] = [urls[child] for child in children]

            # Children don't connect down (they report up)
            for child in children:
                if child not in connections:
                    connections[child] = []

        return connections

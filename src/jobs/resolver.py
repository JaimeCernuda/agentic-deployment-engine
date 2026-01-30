"""Topology resolver - Generate deployment plans from topology patterns."""

from .models import DeploymentPlan, JobDefinition


class TopologyResolver:
    """Resolve topology patterns into deployment plans."""

    def resolve(self, job: JobDefinition) -> DeploymentPlan:
        """Generate deployment plan from job topology.

        Args:
            job: Job definition

        Returns:
            Deployment plan with stages, URLs, and connections
        """
        # 1. Resolve deployment order
        stages = self._resolve_order(job)

        # 2. Resolve agent URLs
        agent_urls = self._resolve_urls(job)

        # 3. Resolve connections
        connections = self._resolve_connections(job, agent_urls)

        return DeploymentPlan(
            stages=stages, agent_urls=agent_urls, connections=connections
        )

    def _resolve_order(self, job: JobDefinition) -> list[list[str]]:
        """Resolve deployment order based on topology pattern.

        Returns list of stages, where each stage is a list of agent IDs
        that can be deployed in parallel.

        Args:
            job: Job definition

        Returns:
            List of deployment stages
        """
        topology = job.topology

        if topology.type == "hub-spoke":
            # Stage 1: All spokes (parallel)
            # Stage 2: Hub (after spokes ready)
            return [
                topology.spokes or [],  # Stage 1: spokes
                [topology.hub] if topology.hub else [],  # Stage 2: hub
            ]

        elif topology.type == "pipeline":
            # Sequential or parallel stages
            stages = []
            for stage in topology.stages or []:
                if isinstance(stage, list):
                    # Parallel stage
                    stages.append(stage)
                else:
                    # Single agent stage
                    stages.append([stage])
            return stages

        elif topology.type == "dag":
            # Topological sort → group by levels
            return self._dag_to_stages(job)

        elif topology.type == "mesh":
            # All agents at once (parallel)
            return [topology.agents or []]

        elif topology.type == "hierarchical":
            # Root first, then level by level
            stages = []
            if topology.root:
                stages.append([topology.root])
            if topology.levels:
                stages.extend(topology.levels)
            return stages

        return []

    def _resolve_urls(self, job: JobDefinition) -> dict[str, str]:
        """Resolve URL for each agent based on deployment target.

        Args:
            job: Job definition

        Returns:
            Dictionary mapping agent ID to URL
        """
        urls: dict[str, str] = {}

        for agent in job.agents:
            port = agent.config.get("port")
            if not port:
                continue

            if agent.deployment.target == "localhost":
                urls[agent.id] = f"http://localhost:{port}"

            elif agent.deployment.target == "remote":
                host = agent.deployment.host
                urls[agent.id] = f"http://{host}:{port}"

            elif agent.deployment.target == "container":
                container = agent.deployment.container_name or agent.id
                urls[agent.id] = f"http://{container}:{port}"

            elif agent.deployment.target == "kubernetes":
                namespace = agent.deployment.namespace or "default"
                service = agent.id
                urls[agent.id] = (
                    f"http://{service}.{namespace}.svc.cluster.local:{port}"
                )

        return urls

    def _resolve_connections(
        self, job: JobDefinition, urls: dict[str, str]
    ) -> dict[str, list[str]]:
        """Determine which URLs each agent should connect to.

        Args:
            job: Job definition
            urls: Resolved agent URLs

        Returns:
            Dictionary mapping agent ID to list of connected agent URLs
        """
        connections: dict[str, list[str]] = {agent.id: [] for agent in job.agents}
        topology = job.topology

        if topology.type == "hub-spoke":
            # Hub connects to all spokes
            if topology.hub and topology.spokes:
                connections[topology.hub] = [
                    urls[s] for s in topology.spokes if s in urls
                ]
                # Spokes don't connect to anyone (or optionally to hub)
                for spoke in topology.spokes:
                    connections[spoke] = []

        elif topology.type == "pipeline":
            # Each stage connects to next stage
            if topology.stages:
                stages = topology.stages
                for i in range(len(stages)):
                    current_stage = stages[i]
                    current_agents = (
                        current_stage
                        if isinstance(current_stage, list)
                        else [current_stage]
                    )

                    if i < len(stages) - 1:
                        # Connect to next stage
                        next_stage = stages[i + 1]
                        next_agents = (
                            next_stage if isinstance(next_stage, list) else [next_stage]
                        )
                        next_urls = [urls[a] for a in next_agents if a in urls]

                        for agent_id in current_agents:
                            connections[agent_id] = next_urls
                    else:
                        # Last stage - no connections
                        for agent_id in current_agents:
                            connections[agent_id] = []

        elif topology.type == "dag":
            # Based on explicit connections
            if topology.connections:
                for conn in topology.connections:
                    from_id = conn.from_
                    to_ids = conn.to if isinstance(conn.to, list) else [conn.to]

                    # Add URLs to connections
                    for to_id in to_ids:
                        if to_id in urls and to_id not in [
                            u.split("://")[1].split(":")[0]
                            for u in connections[from_id]
                        ]:
                            # Avoid duplicates
                            url = urls[to_id]
                            if url not in connections[from_id]:
                                connections[from_id].append(url)

        elif topology.type == "mesh":
            # Everyone connects to everyone else
            if topology.agents:
                for agent_id in topology.agents:
                    others = [
                        urls[a] for a in topology.agents if a != agent_id and a in urls
                    ]
                    connections[agent_id] = others

        elif topology.type == "hierarchical":
            # Root connects to first level
            # Each level connects to next level
            if topology.root and topology.levels:
                # Root → first level
                first_level = topology.levels[0]
                connections[topology.root] = [urls[a] for a in first_level if a in urls]

                # Each level → next level
                for i in range(len(topology.levels)):
                    current_level = topology.levels[i]

                    if i < len(topology.levels) - 1:
                        next_level = topology.levels[i + 1]
                        next_urls = [urls[a] for a in next_level if a in urls]

                        for agent_id in current_level:
                            connections[agent_id] = next_urls
                    else:
                        # Last level
                        for agent_id in current_level:
                            connections[agent_id] = []

        return connections

    def _dag_to_stages(self, job: JobDefinition) -> list[list[str]]:
        """Convert DAG connections to deployment stages via topological sort.

        Args:
            job: Job definition with DAG topology

        Returns:
            List of deployment stages
        """
        if not job.topology.connections:
            return []

        # Build adjacency list and in-degree count
        graph: dict[str, set[str]] = {}
        in_degree: dict[str, int] = {}

        # Initialize all agents
        for agent in job.agents:
            graph[agent.id] = set()
            in_degree[agent.id] = 0

        # Build graph
        for conn in job.topology.connections:
            from_id = conn.from_
            to_ids = conn.to if isinstance(conn.to, list) else [conn.to]

            for to_id in to_ids:
                graph[from_id].add(to_id)
                in_degree[to_id] += 1

        # Topological sort with level assignment
        stages: list[list[str]] = []
        remaining = set(in_degree.keys())

        while remaining:
            # Find all nodes with in-degree 0 (can be deployed in parallel)
            current_stage = [node for node in remaining if in_degree[node] == 0]

            if not current_stage:
                # Cycle detected (shouldn't happen after validation)
                break

            stages.append(current_stage)

            # Remove these nodes and update in-degrees
            for node in current_stage:
                remaining.remove(node)
                for neighbor in graph[node]:
                    in_degree[neighbor] -= 1

        return stages

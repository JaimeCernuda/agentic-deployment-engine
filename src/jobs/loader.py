"""Job loader - Parse and validate job definitions."""

import importlib
import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import JobDefinition

logger = logging.getLogger(__name__)


class JobLoadError(Exception):
    """Error loading or validating job definition."""

    pass


class JobLoader:
    """Load and validate job definitions from YAML files."""

    def load(self, yaml_path: str | Path) -> JobDefinition:
        """Load job definition from YAML file.

        Args:
            yaml_path: Path to job YAML file

        Returns:
            Validated JobDefinition

        Raises:
            JobLoadError: If loading or validation fails
        """
        yaml_path = Path(yaml_path)

        if not yaml_path.exists():
            raise JobLoadError(f"Job file not found: {yaml_path}")

        # 1. Parse YAML
        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise JobLoadError(f"Invalid YAML: {e}") from e

        if not isinstance(data, dict):
            raise JobLoadError("Job file must contain a dictionary")

        # 2. Pydantic validation (schema)
        try:
            job = JobDefinition(**data)
        except ValidationError as e:
            raise JobLoadError(f"Validation error:\n{e}") from e

        # 3. Validate agents exist and are importable
        self._validate_agents_importable(job)

        # 4. Validate topology references
        self._validate_topology_references(job)

        # 5. Validate topology structure
        self._validate_topology_structure(job)

        # 6. Validate deployment configurations
        self._validate_deployment_configs(job)

        return job

    def _validate_agents_importable(self, job: JobDefinition) -> None:
        """Check that all agent modules and types are importable.

        Args:
            job: Job definition to validate

        Raises:
            JobLoadError: If any agent is not importable
        """
        for agent in job.agents:
            try:
                # Try to import the module
                module = importlib.import_module(agent.module)

                # Try to get the agent class
                if not hasattr(module, agent.type):
                    raise JobLoadError(
                        f"Agent type '{agent.type}' not found in module '{agent.module}'"
                    )
            except ImportError as e:
                raise JobLoadError(
                    f"Cannot import agent module '{agent.module}': {e}"
                ) from e

    def _validate_topology_references(self, job: JobDefinition) -> None:
        """Validate that topology references valid agent IDs.

        Args:
            job: Job definition to validate

        Raises:
            JobLoadError: If topology references invalid agents
        """
        agent_ids = job.get_agent_ids()
        topology = job.topology

        def check_agent_id(agent_id: str, context: str) -> None:
            if agent_id not in agent_ids:
                raise JobLoadError(
                    f"Topology references unknown agent '{agent_id}' in {context}"
                )

        # Hub-spoke
        if topology.type == "hub-spoke":
            if not topology.hub or not topology.spokes:
                raise JobLoadError("Hub-spoke topology requires 'hub' and 'spokes'")

            check_agent_id(topology.hub, "hub")
            for spoke in topology.spokes:
                check_agent_id(spoke, "spokes")

        # Pipeline
        elif topology.type == "pipeline":
            if not topology.stages:
                raise JobLoadError("Pipeline topology requires 'stages'")

            for i, stage in enumerate(topology.stages):
                if isinstance(stage, list):
                    for agent_id in stage:
                        check_agent_id(agent_id, f"stage {i}")
                else:
                    check_agent_id(stage, f"stage {i}")

        # DAG
        elif topology.type == "dag":
            if not topology.connections:
                raise JobLoadError("DAG topology requires 'connections'")

            for conn in topology.connections:
                check_agent_id(conn.from_, "connection.from")

                if isinstance(conn.to, list):
                    for to_id in conn.to:
                        check_agent_id(to_id, "connection.to")
                else:
                    check_agent_id(conn.to, "connection.to")

        # Mesh
        elif topology.type == "mesh":
            if not topology.agents:
                raise JobLoadError("Mesh topology requires 'agents'")

            for agent_id in topology.agents:
                check_agent_id(agent_id, "mesh.agents")

        # Hierarchical
        elif topology.type == "hierarchical":
            if not topology.root or not topology.levels:
                raise JobLoadError("Hierarchical topology requires 'root' and 'levels'")

            check_agent_id(topology.root, "root")
            for level_idx, level in enumerate(topology.levels):
                for agent_id in level:
                    check_agent_id(agent_id, f"level {level_idx}")

    def _validate_topology_structure(self, job: JobDefinition) -> None:
        """Validate topology structure (e.g., DAG is acyclic).

        Args:
            job: Job definition to validate

        Raises:
            JobLoadError: If topology structure is invalid
        """
        topology = job.topology

        # Validate DAG is acyclic
        if topology.type == "dag":
            if not topology.connections:
                return

            # Build adjacency list
            graph: dict[str, set[str]] = {}

            for conn in topology.connections:
                from_id = conn.from_
                to_ids = conn.to if isinstance(conn.to, list) else [conn.to]

                if from_id not in graph:
                    graph[from_id] = set()

                for to_id in to_ids:
                    graph[to_id] = graph.get(to_id, set())
                    graph[from_id].add(to_id)

            # Check for cycles using DFS
            def has_cycle(node: str, visited: set[str], rec_stack: set[str]) -> bool:
                visited.add(node)
                rec_stack.add(node)

                for neighbor in graph.get(node, []):
                    if neighbor not in visited:
                        if has_cycle(neighbor, visited, rec_stack):
                            return True
                    elif neighbor in rec_stack:
                        return True

                rec_stack.remove(node)
                return False

            visited: set[str] = set()
            for node in graph:
                if node not in visited:
                    if has_cycle(node, visited, set()):
                        raise JobLoadError("DAG topology contains cycles")

        # Validate pipeline stages are non-empty
        if topology.type == "pipeline":
            if topology.stages:
                for i, stage in enumerate(topology.stages):
                    if isinstance(stage, list) and len(stage) == 0:
                        raise JobLoadError(f"Pipeline stage {i} is empty")

        # Validate mesh has at least 2 agents
        if topology.type == "mesh":
            if topology.agents and len(topology.agents) < 2:
                raise JobLoadError("Mesh topology requires at least 2 agents")

        # Validate hierarchical structure
        if topology.type == "hierarchical":
            if topology.levels:
                # Check root is not in levels
                all_level_agents = set()
                for level in topology.levels:
                    all_level_agents.update(level)

                if topology.root in all_level_agents:
                    raise JobLoadError(
                        "Root agent cannot appear in hierarchical levels"
                    )

    def _validate_deployment_configs(self, job: JobDefinition) -> None:
        """Validate deployment configurations for agents.

        Args:
            job: Job definition to validate

        Raises:
            JobLoadError: If deployment configuration is invalid
        """
        import os

        for agent in job.agents:
            deployment = agent.deployment

            # Validate remote deployment
            if deployment.target == "remote":
                if not deployment.host:
                    raise JobLoadError(
                        f"Agent {agent.id}: Remote deployment requires 'host'"
                    )

                # Check SSH key if specified
                if deployment.ssh_key:
                    ssh_key_path = os.path.expanduser(deployment.ssh_key)
                    if not os.path.exists(ssh_key_path):
                        raise JobLoadError(
                            f"Agent {agent.id}: SSH key not found: {deployment.ssh_key}"
                        )

                # Warn if using password (not recommended)
                if deployment.password:
                    logger.warning(
                        "Agent %s using password authentication. "
                        "SSH keys are recommended for security.",
                        agent.id,
                    )

            # Validate container deployment
            elif deployment.target == "container":
                if not deployment.image:
                    raise JobLoadError(
                        f"Agent {agent.id}: Container deployment requires 'image'"
                    )

            # Validate kubernetes deployment
            elif deployment.target == "kubernetes":
                if not deployment.namespace:
                    raise JobLoadError(
                        f"Agent {agent.id}: Kubernetes deployment requires 'namespace'"
                    )

    def validate_only(self, yaml_path: str | Path) -> str | None:
        """Validate job file and return error message if invalid.

        Args:
            yaml_path: Path to job YAML file

        Returns:
            Error message if validation fails, None if valid
        """
        try:
            self.load(yaml_path)
            return None
        except JobLoadError as e:
            return str(e)

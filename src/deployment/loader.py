"""Job loader - parse and validate job definitions."""

import yaml
import importlib
from pathlib import Path
from typing import Dict, Set
from .models import JobDefinition


class JobLoader:
    """Load and validate job definitions from YAML."""

    def load(self, yaml_path: str) -> JobDefinition:
        """Load job definition from YAML file.

        Args:
            yaml_path: Path to YAML job definition file

        Returns:
            Validated JobDefinition object

        Raises:
            FileNotFoundError: If YAML file not found
            ValueError: If job definition is invalid
        """
        # 1. Load YAML
        yaml_file = Path(yaml_path)
        if not yaml_file.exists():
            raise FileNotFoundError(f"Job file not found: {yaml_path}")

        with open(yaml_file) as f:
            data = yaml.safe_load(f)

        # 2. Parse with pydantic (automatic validation)
        try:
            job = JobDefinition(**data)
        except Exception as e:
            raise ValueError(f"Invalid job definition: {e}")

        # 3. Additional validation
        self._validate_agents_importable(job)
        self._validate_topology_references(job)
        self._validate_port_conflicts(job)

        return job

    def _validate_agents_importable(self, job: JobDefinition):
        """Validate that agent modules and classes exist."""
        for agent in job.agents:
            try:
                # Try to import module
                module = importlib.import_module(agent.module)

                # Try to get class
                if not hasattr(module, agent.type):
                    raise ValueError(
                        f"Agent {agent.id}: class '{agent.type}' not found in module '{agent.module}'"
                    )

            except ImportError as e:
                raise ValueError(
                    f"Agent {agent.id}: cannot import module '{agent.module}': {e}"
                )

    def _validate_topology_references(self, job: JobDefinition):
        """Validate that topology references valid agent IDs."""
        agent_ids = job.get_agent_ids()
        topology = job.topology

        # Validate based on topology type
        if topology.type == "hub-spoke":
            self._validate_hub_spoke(topology, agent_ids)

        elif topology.type == "pipeline":
            self._validate_pipeline(topology, agent_ids)

        elif topology.type == "dag":
            self._validate_dag(topology, agent_ids)

        elif topology.type == "mesh":
            self._validate_mesh(topology, agent_ids)

        elif topology.type == "hierarchical":
            self._validate_hierarchical(topology, agent_ids)

    def _validate_hub_spoke(self, topology, agent_ids: Set[str]):
        """Validate hub-spoke topology."""
        if not topology.hub:
            raise ValueError("Hub-spoke topology requires 'hub' field")
        if not topology.spokes:
            raise ValueError("Hub-spoke topology requires 'spokes' field")

        if topology.hub not in agent_ids:
            raise ValueError(f"Hub agent '{topology.hub}' not defined")

        for spoke in topology.spokes:
            if spoke not in agent_ids:
                raise ValueError(f"Spoke agent '{spoke}' not defined")

    def _validate_pipeline(self, topology, agent_ids: Set[str]):
        """Validate pipeline topology."""
        if not topology.stages:
            raise ValueError("Pipeline topology requires 'stages' field")

        for stage in topology.stages:
            if stage not in agent_ids:
                raise ValueError(f"Pipeline stage '{stage}' not defined")

    def _validate_dag(self, topology, agent_ids: Set[str]):
        """Validate DAG topology."""
        if not topology.connections:
            raise ValueError("DAG topology requires 'connections' field")

        for conn in topology.connections:
            if conn.from_ not in agent_ids:
                raise ValueError(f"DAG connection from '{conn.from_}' not defined")

            # Handle 'to' as string or list
            to_agents = [conn.to] if isinstance(conn.to, str) else conn.to
            for to_agent in to_agents:
                if to_agent not in agent_ids:
                    raise ValueError(f"DAG connection to '{to_agent}' not defined")

    def _validate_mesh(self, topology, agent_ids: Set[str]):
        """Validate mesh topology."""
        if not topology.agents:
            raise ValueError("Mesh topology requires 'agents' field")

        for agent_id in topology.agents:
            if agent_id not in agent_ids:
                raise ValueError(f"Mesh agent '{agent_id}' not defined")

    def _validate_hierarchical(self, topology, agent_ids: Set[str]):
        """Validate hierarchical topology."""
        if not topology.root:
            raise ValueError("Hierarchical topology requires 'root' field")
        if not topology.levels:
            raise ValueError("Hierarchical topology requires 'levels' field")

        if topology.root not in agent_ids:
            raise ValueError(f"Root agent '{topology.root}' not defined")

        # Validate all agents in levels
        for level in topology.levels:
            if "parent" in level and level["parent"] not in agent_ids:
                raise ValueError(f"Parent agent '{level['parent']}' not defined")

            if "children" in level:
                for child in level["children"]:
                    if child not in agent_ids:
                        raise ValueError(f"Child agent '{child}' not defined")

    def _validate_port_conflicts(self, job: JobDefinition):
        """Validate no port conflicts on same host."""
        # Group agents by deployment target
        host_ports: Dict[str, Set[int]] = {}

        for agent in job.agents:
            # Determine host
            if agent.deployment.target == "localhost":
                host = "localhost"
            elif agent.deployment.target == "remote":
                host = agent.deployment.host or "unknown"
            else:
                # Containers/k8s can have port conflicts, skip for now
                continue

            # Get port
            port = agent.config.get("port")
            if not port:
                continue

            # Check for conflict
            if host not in host_ports:
                host_ports[host] = set()

            if port in host_ports[host]:
                raise ValueError(
                    f"Port conflict: Multiple agents using port {port} on {host}"
                )

            host_ports[host].add(port)

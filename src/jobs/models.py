"""Pydantic models for A2A job definitions."""

from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr, field_validator

# ============================================================================
# Job Metadata
# ============================================================================


class JobMetadata(BaseModel):
    """Job metadata and identification."""

    name: str = Field(..., description="Unique job identifier")
    version: str = Field(..., description="Semantic version (e.g., '1.0.0')")
    description: str = Field(..., description="Human-readable description")
    tags: list[str] = Field(default_factory=list, description="Optional tags")


# ============================================================================
# Agent Configuration
# ============================================================================


class AgentDeploymentConfig(BaseModel):
    """Agent deployment configuration."""

    target: Literal["localhost", "remote", "container", "kubernetes"] = Field(
        ..., description="Deployment target type"
    )

    # Remote deployment (SSH)
    host: str | None = Field(None, description="Hostname/IP for remote deployment")
    user: str | None = Field(None, description="SSH user (defaults to current user)")
    ssh_key: str | None = Field(
        None, description="Path to SSH private key (defaults to ~/.ssh/id_rsa)"
    )
    password: SecretStr | None = Field(
        None, description="SSH password (not recommended, use keys)"
    )
    python: str | None = Field(
        "python3", description="Python interpreter path on remote host"
    )
    workdir: str | None = Field(None, description="Working directory on target")
    port: int | None = Field(22, description="SSH port")

    # Container deployment
    image: str | None = Field(None, description="Docker image for container deployment")
    network: str | None = Field(None, description="Docker network name")
    container_name: str | None = Field(None, description="Container name")

    # Kubernetes deployment
    namespace: str | None = Field(None, description="Kubernetes namespace")
    service_type: str | None = Field(None, description="Kubernetes service type")

    # Environment variables
    environment: dict[str, str] | None = Field(
        default_factory=dict, description="Environment variables"
    )


class AgentResourceConfig(BaseModel):
    """Agent resource requirements."""

    cpu: float | None = Field(None, description="CPU cores")
    memory: str | None = Field(None, description="Memory limit (e.g., '1G', '512M')")
    gpu: int | None = Field(None, description="Number of GPUs")


class AgentConfig(BaseModel):
    """Agent definition."""

    id: str = Field(..., description="Unique agent identifier within job")
    type: str = Field(..., description="Agent class name")
    module: str = Field(..., description="Python module path")
    config: dict[str, Any] = Field(
        default_factory=dict, description="Agent-specific configuration"
    )
    deployment: AgentDeploymentConfig = Field(
        ..., description="Deployment configuration"
    )
    resources: AgentResourceConfig | None = Field(
        None, description="Resource requirements"
    )

    @field_validator("config")
    @classmethod
    def validate_port(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Ensure port is specified in config."""
        if "port" not in v:
            raise ValueError("Agent config must include 'port'")
        return v


# ============================================================================
# Topology Configuration
# ============================================================================


class Connection(BaseModel):
    """A connection between two agents."""

    from_: str = Field(..., alias="from", description="Source agent ID")
    to: str | list[str] = Field(..., description="Target agent ID(s)")
    type: str | None = Field(
        "query", description="Connection type: query, stream, bidirectional"
    )


class TopologyConfig(BaseModel):
    """Network topology configuration."""

    type: Literal["hub-spoke", "pipeline", "dag", "mesh", "hierarchical", "dynamic"] = (
        Field(..., description="Topology pattern type")
    )

    # Hub-spoke specific
    hub: str | None = Field(None, description="Hub agent ID (for hub-spoke)")
    spokes: list[str] | None = Field(
        None, description="Spoke agent IDs (for hub-spoke)"
    )

    # Pipeline specific
    stages: list[str | list[str]] | None = Field(
        None, description="Pipeline stages (for pipeline)"
    )

    # DAG specific
    connections: list[Connection] | None = Field(
        None, description="Explicit connections (for DAG)"
    )

    # Mesh specific
    agents: list[str] | None = Field(None, description="Agent IDs (for mesh)")

    # Hierarchical specific
    root: str | None = Field(None, description="Root agent ID (for hierarchical)")
    levels: list[list[str]] | None = Field(
        None, description="Hierarchical levels (for hierarchical)"
    )

    @field_validator("type")
    @classmethod
    def validate_topology_fields(cls, v: str, info) -> str:
        """Validate that required fields are present for topology type."""
        # Note: This will be called before other fields are validated
        # Full validation happens in JobDefinition
        return v


# ============================================================================
# Deployment Configuration
# ============================================================================


class HealthCheckConfig(BaseModel):
    """Health check configuration."""

    enabled: bool = True
    interval: int = 5
    retries: int = 3
    timeout: int = 5


class SSHConfig(BaseModel):
    """SSH configuration for remote deployment."""

    key_file: str | None = Field(None, description="SSH key file path")
    timeout: int = Field(30, description="SSH connection timeout")


class NetworkConfig(BaseModel):
    """Network configuration."""

    allow_cross_host: bool = Field(True, description="Allow cross-host communication")
    firewall_rules: list[dict[str, Any]] | None = Field(
        None, description="Firewall rules"
    )


class DeploymentConfig(BaseModel):
    """Deployment strategy configuration."""

    strategy: Literal["sequential", "parallel", "staged"] = "staged"
    timeout: int = 60
    health_check: HealthCheckConfig = Field(default_factory=HealthCheckConfig)
    ssh: SSHConfig | None = None
    network: NetworkConfig | None = None


# ============================================================================
# Execution Configuration
# ============================================================================


class ExecutionConfig(BaseModel):
    """Workflow execution configuration."""

    entry_point: str | None = Field(None, description="Entry point agent ID")
    auto_start: bool = Field(False, description="Auto-start workflow on deployment")


# ============================================================================
# Complete Job Definition
# ============================================================================


class JobDefinition(BaseModel):
    """Complete job definition."""

    job: JobMetadata = Field(..., description="Job metadata")
    agents: list[AgentConfig] = Field(..., description="Agent definitions")
    topology: TopologyConfig = Field(..., description="Network topology")
    deployment: DeploymentConfig = Field(default_factory=DeploymentConfig)
    execution: ExecutionConfig | None = None
    environment: dict[str, str] = Field(default_factory=dict)

    @field_validator("agents")
    @classmethod
    def validate_unique_agent_ids(cls, v: list[AgentConfig]) -> list[AgentConfig]:
        """Ensure agent IDs are unique."""
        agent_ids = [agent.id for agent in v]
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("Agent IDs must be unique")
        return v

    @field_validator("agents")
    @classmethod
    def validate_no_port_conflicts(cls, v: list[AgentConfig]) -> list[AgentConfig]:
        """Check for port conflicts on same deployment target."""
        # Group by deployment target
        target_ports: dict[str, list[int]] = {}

        for agent in v:
            # Construct target key
            if agent.deployment.target == "localhost":
                target_key = "localhost"
            elif agent.deployment.target == "remote":
                target_key = f"remote:{agent.deployment.host}"
            elif agent.deployment.target == "container":
                continue  # Containers can use same ports (different namespaces)
            else:
                continue

            port = agent.config.get("port")
            if port:
                if target_key not in target_ports:
                    target_ports[target_key] = []

                if port in target_ports[target_key]:
                    raise ValueError(
                        f"Port conflict: {port} already in use on {target_key}"
                    )
                target_ports[target_key].append(port)

        return v

    def get_agent(self, agent_id: str) -> AgentConfig | None:
        """Get agent configuration by ID."""
        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        return None

    def get_agent_ids(self) -> set[str]:
        """Get set of all agent IDs."""
        return {agent.id for agent in self.agents}


# ============================================================================
# Deployment Plan (output of TopologyResolver)
# ============================================================================


class DeploymentPlan(BaseModel):
    """Deployment plan generated by TopologyResolver."""

    stages: list[list[str]] = Field(
        ..., description="Ordered stages of agent IDs to deploy"
    )
    agent_urls: dict[str, str] = Field(..., description="Resolved URL for each agent")
    connections: dict[str, list[str]] = Field(
        ..., description="Connected agent URLs for each agent"
    )


# ============================================================================
# Deployed Job (output of AgentDeployer)
# ============================================================================


class DeployedAgent(BaseModel):
    """Information about a deployed agent."""

    agent_id: str
    url: str
    process_id: int | None = None
    container_id: str | None = None
    host: str | None = None  # SSH host for remote agents
    status: Literal["starting", "healthy", "unhealthy", "stopped"] = "starting"


class DeployedJob(BaseModel):
    """A deployed job with running agents."""

    job_id: str
    definition: JobDefinition
    plan: DeploymentPlan
    agents: dict[str, DeployedAgent]
    start_time: str
    status: Literal["deploying", "running", "stopping", "stopped", "failed"] = (
        "deploying"
    )

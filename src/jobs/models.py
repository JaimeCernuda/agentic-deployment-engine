"""Pydantic models for A2A job definitions."""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Job Metadata
# ============================================================================

class JobMetadata(BaseModel):
    """Job metadata and identification."""

    name: str = Field(..., description="Unique job identifier")
    version: str = Field(..., description="Semantic version (e.g., '1.0.0')")
    description: str = Field(..., description="Human-readable description")
    tags: List[str] = Field(default_factory=list, description="Optional tags")


# ============================================================================
# Agent Configuration
# ============================================================================

class AgentDeploymentConfig(BaseModel):
    """Agent deployment configuration."""

    target: Literal["localhost", "remote", "container", "kubernetes"] = Field(
        ..., description="Deployment target type"
    )

    # Remote deployment (SSH)
    host: Optional[str] = Field(None, description="Hostname/IP for remote deployment")
    user: Optional[str] = Field(None, description="SSH user (defaults to current user)")
    ssh_key: Optional[str] = Field(None, description="Path to SSH private key (defaults to ~/.ssh/id_rsa)")
    password: Optional[str] = Field(None, description="SSH password (not recommended, use keys)")
    python: Optional[str] = Field(
        "python3", description="Python interpreter path on remote host"
    )
    workdir: Optional[str] = Field(None, description="Working directory on target")
    port: Optional[int] = Field(22, description="SSH port")

    # Container deployment
    image: Optional[str] = Field(None, description="Docker image for container deployment")
    network: Optional[str] = Field(None, description="Docker network name")
    container_name: Optional[str] = Field(None, description="Container name")

    # Kubernetes deployment
    namespace: Optional[str] = Field(None, description="Kubernetes namespace")
    service_type: Optional[str] = Field(None, description="Kubernetes service type")

    # Environment variables
    environment: Optional[Dict[str, str]] = Field(
        default_factory=dict, description="Environment variables"
    )


class AgentResourceConfig(BaseModel):
    """Agent resource requirements."""

    cpu: Optional[float] = Field(None, description="CPU cores")
    memory: Optional[str] = Field(None, description="Memory limit (e.g., '1G', '512M')")
    gpu: Optional[int] = Field(None, description="Number of GPUs")


class AgentConfig(BaseModel):
    """Agent definition."""

    id: str = Field(..., description="Unique agent identifier within job")
    type: str = Field(..., description="Agent class name")
    module: str = Field(..., description="Python module path")
    config: Dict[str, Any] = Field(
        default_factory=dict, description="Agent-specific configuration"
    )
    deployment: AgentDeploymentConfig = Field(..., description="Deployment configuration")
    resources: Optional[AgentResourceConfig] = Field(
        None, description="Resource requirements"
    )

    @field_validator("config")
    @classmethod
    def validate_port(cls, v: Dict[str, Any]) -> Dict[str, Any]:
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
    to: Union[str, List[str]] = Field(..., description="Target agent ID(s)")
    type: Optional[str] = Field(
        "query", description="Connection type: query, stream, bidirectional"
    )


class TopologyConfig(BaseModel):
    """Network topology configuration."""

    type: Literal["hub-spoke", "pipeline", "dag", "mesh", "hierarchical"] = Field(
        ..., description="Topology pattern type"
    )

    # Hub-spoke specific
    hub: Optional[str] = Field(None, description="Hub agent ID (for hub-spoke)")
    spokes: Optional[List[str]] = Field(None, description="Spoke agent IDs (for hub-spoke)")

    # Pipeline specific
    stages: Optional[List[Union[str, List[str]]]] = Field(
        None, description="Pipeline stages (for pipeline)"
    )

    # DAG specific
    connections: Optional[List[Connection]] = Field(
        None, description="Explicit connections (for DAG)"
    )

    # Mesh specific
    agents: Optional[List[str]] = Field(None, description="Agent IDs (for mesh)")

    # Hierarchical specific
    root: Optional[str] = Field(None, description="Root agent ID (for hierarchical)")
    levels: Optional[List[List[str]]] = Field(
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

    enabled: bool = Field(True, description="Enable health checks")
    interval: int = Field(5, description="Check interval in seconds")
    retries: int = Field(3, description="Number of retries before failure")
    timeout: int = Field(5, description="Timeout per check in seconds")


class SSHConfig(BaseModel):
    """SSH configuration for remote deployment."""

    key_file: Optional[str] = Field(None, description="SSH key file path")
    timeout: int = Field(30, description="SSH connection timeout")


class NetworkConfig(BaseModel):
    """Network configuration."""

    allow_cross_host: bool = Field(True, description="Allow cross-host communication")
    firewall_rules: Optional[List[Dict[str, Any]]] = Field(
        None, description="Firewall rules"
    )


class DeploymentConfig(BaseModel):
    """Deployment strategy configuration."""

    strategy: Literal["sequential", "parallel", "staged"] = Field(
        "staged", description="Deployment strategy"
    )
    timeout: int = Field(60, description="Deployment timeout in seconds")
    health_check: HealthCheckConfig = Field(
        default_factory=HealthCheckConfig, description="Health check configuration"
    )
    ssh: Optional[SSHConfig] = Field(None, description="SSH configuration")
    network: Optional[NetworkConfig] = Field(None, description="Network configuration")


# ============================================================================
# Execution Configuration
# ============================================================================

class ExecutionConfig(BaseModel):
    """Workflow execution configuration."""

    entry_point: Optional[str] = Field(None, description="Entry point agent ID")
    auto_start: bool = Field(False, description="Auto-start workflow on deployment")


# ============================================================================
# Complete Job Definition
# ============================================================================

class JobDefinition(BaseModel):
    """Complete job definition."""

    job: JobMetadata = Field(..., description="Job metadata")
    agents: List[AgentConfig] = Field(..., description="Agent definitions")
    topology: TopologyConfig = Field(..., description="Network topology")
    deployment: DeploymentConfig = Field(
        default_factory=DeploymentConfig, description="Deployment configuration"
    )
    execution: Optional[ExecutionConfig] = Field(
        None, description="Execution configuration"
    )
    environment: Optional[Dict[str, str]] = Field(
        default_factory=dict, description="Global environment variables"
    )

    @field_validator("agents")
    @classmethod
    def validate_unique_agent_ids(cls, v: List[AgentConfig]) -> List[AgentConfig]:
        """Ensure agent IDs are unique."""
        agent_ids = [agent.id for agent in v]
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("Agent IDs must be unique")
        return v

    @field_validator("agents")
    @classmethod
    def validate_no_port_conflicts(cls, v: List[AgentConfig]) -> List[AgentConfig]:
        """Check for port conflicts on same deployment target."""
        # Group by deployment target
        target_ports: Dict[str, List[int]] = {}

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

    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
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

    stages: List[List[str]] = Field(
        ..., description="Ordered stages of agent IDs to deploy"
    )
    agent_urls: Dict[str, str] = Field(
        ..., description="Resolved URL for each agent"
    )
    connections: Dict[str, List[str]] = Field(
        ..., description="Connected agent URLs for each agent"
    )


# ============================================================================
# Deployed Job (output of AgentDeployer)
# ============================================================================

class DeployedAgent(BaseModel):
    """Information about a deployed agent."""

    agent_id: str
    url: str
    process_id: Optional[int] = None
    container_id: Optional[str] = None
    status: Literal["starting", "healthy", "unhealthy", "stopped"] = "starting"


class DeployedJob(BaseModel):
    """A deployed job with running agents."""

    job_id: str
    definition: JobDefinition
    plan: DeploymentPlan
    agents: Dict[str, DeployedAgent]
    start_time: str
    status: Literal["deploying", "running", "stopping", "stopped", "failed"] = "deploying"

"""Comprehensive tests for Pydantic models in src/jobs/models.py.

Tests cover:
- JobMetadata validation
- AgentConfig validation (port requirement, unique IDs, port conflicts)
- TopologyConfig validation (all 5 topology types)
- DeploymentConfig defaults and validation
- Connection model with alias handling
- Complete JobDefinition validation
"""

import sys
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.jobs.models import (
    AgentConfig,
    AgentDeploymentConfig,
    AgentResourceConfig,
    Connection,
    DeployedAgent,
    DeployedJob,
    DeploymentConfig,
    DeploymentPlan,
    ExecutionConfig,
    HealthCheckConfig,
    JobDefinition,
    JobMetadata,
    TopologyConfig,
)


class TestJobMetadata:
    """Tests for JobMetadata model."""

    def test_valid_metadata(self) -> None:
        """Valid metadata should be accepted."""
        meta = JobMetadata(
            name="test-job",
            version="1.0.0",
            description="A test job",
        )
        assert meta.name == "test-job"
        assert meta.version == "1.0.0"
        assert meta.description == "A test job"
        assert meta.tags == []  # default

    def test_metadata_with_tags(self) -> None:
        """Metadata with tags should work."""
        meta = JobMetadata(
            name="test-job",
            version="1.0.0",
            description="A test job",
            tags=["production", "ml"],
        )
        assert meta.tags == ["production", "ml"]

    def test_missing_required_fields(self) -> None:
        """Missing required fields should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            JobMetadata(name="test")  # missing version and description

        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "version" in field_names
        assert "description" in field_names

    def test_empty_name_allowed(self) -> None:
        """Empty name is technically allowed by Pydantic (just str)."""
        meta = JobMetadata(name="", version="1.0.0", description="test")
        assert meta.name == ""


class TestAgentDeploymentConfig:
    """Tests for AgentDeploymentConfig model."""

    def test_localhost_deployment(self) -> None:
        """Localhost deployment with minimal config."""
        config = AgentDeploymentConfig(target="localhost")
        assert config.target == "localhost"
        assert config.host is None
        assert config.python == "python3"  # default

    def test_remote_deployment_with_host(self) -> None:
        """Remote deployment requires host."""
        config = AgentDeploymentConfig(
            target="remote",
            host="192.168.1.100",
            user="admin",
            ssh_key="~/.ssh/id_rsa",
        )
        assert config.target == "remote"
        assert config.host == "192.168.1.100"
        assert config.user == "admin"

    def test_remote_deployment_with_password(self) -> None:
        """Remote deployment with password (SecretStr)."""
        config = AgentDeploymentConfig(
            target="remote",
            host="192.168.1.100",
            password="secret123",
        )
        # Password should be SecretStr
        assert isinstance(config.password, SecretStr)
        assert config.password.get_secret_value() == "secret123"

    def test_container_deployment(self) -> None:
        """Container deployment with image."""
        config = AgentDeploymentConfig(
            target="container",
            image="my-agent:latest",
            network="agent-network",
            container_name="weather-agent",
        )
        assert config.target == "container"
        assert config.image == "my-agent:latest"

    def test_kubernetes_deployment(self) -> None:
        """Kubernetes deployment with namespace."""
        config = AgentDeploymentConfig(
            target="kubernetes",
            namespace="agents",
            service_type="ClusterIP",
        )
        assert config.target == "kubernetes"
        assert config.namespace == "agents"

    def test_invalid_target(self) -> None:
        """Invalid target should raise ValidationError."""
        with pytest.raises(ValidationError):
            AgentDeploymentConfig(target="invalid")

    def test_environment_variables(self) -> None:
        """Environment variables should be a dict."""
        config = AgentDeploymentConfig(
            target="localhost",
            environment={"API_KEY": "secret", "DEBUG": "true"},
        )
        assert config.environment == {"API_KEY": "secret", "DEBUG": "true"}

    def test_default_ssh_port(self) -> None:
        """Default SSH port should be 22."""
        config = AgentDeploymentConfig(target="remote", host="example.com")
        assert config.port == 22


class TestAgentResourceConfig:
    """Tests for AgentResourceConfig model."""

    def test_all_resources(self) -> None:
        """All resource fields."""
        config = AgentResourceConfig(cpu=2.0, memory="4G", gpu=1)
        assert config.cpu == 2.0
        assert config.memory == "4G"
        assert config.gpu == 1

    def test_partial_resources(self) -> None:
        """Partial resource specification."""
        config = AgentResourceConfig(memory="512M")
        assert config.cpu is None
        assert config.memory == "512M"
        assert config.gpu is None

    def test_empty_resources(self) -> None:
        """Empty resource config is valid."""
        config = AgentResourceConfig()
        assert config.cpu is None


class TestAgentConfig:
    """Tests for AgentConfig model."""

    def test_valid_agent_config(self) -> None:
        """Valid agent configuration."""
        config = AgentConfig(
            id="weather-agent",
            type="WeatherAgent",
            module="examples.agents.weather_agent",
            config={"port": 9001},
            deployment=AgentDeploymentConfig(target="localhost"),
        )
        assert config.id == "weather-agent"
        assert config.type == "WeatherAgent"
        assert config.config["port"] == 9001

    def test_missing_port_in_config(self) -> None:
        """Agent config without port should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            AgentConfig(
                id="test",
                type="TestAgent",
                module="test.module",
                config={},  # missing port
                deployment=AgentDeploymentConfig(target="localhost"),
            )

        # Should have error about port
        assert "port" in str(exc_info.value).lower()

    def test_agent_with_resources(self) -> None:
        """Agent with resource requirements."""
        config = AgentConfig(
            id="gpu-agent",
            type="GPUAgent",
            module="examples.agents.gpu",
            config={"port": 9010},
            deployment=AgentDeploymentConfig(target="localhost"),
            resources=AgentResourceConfig(cpu=4.0, memory="8G", gpu=1),
        )
        assert config.resources.gpu == 1

    def test_agent_config_extra_fields(self) -> None:
        """Extra fields in config dict should be preserved."""
        config = AgentConfig(
            id="test",
            type="TestAgent",
            module="test",
            config={"port": 9001, "custom_setting": "value", "timeout": 30},
            deployment=AgentDeploymentConfig(target="localhost"),
        )
        assert config.config["custom_setting"] == "value"
        assert config.config["timeout"] == 30


class TestConnection:
    """Tests for Connection model (DAG topology)."""

    def test_single_target_connection(self) -> None:
        """Connection to single target."""
        conn = Connection(**{"from": "agent-a", "to": "agent-b"})
        assert conn.from_ == "agent-a"
        assert conn.to == "agent-b"

    def test_multiple_target_connection(self) -> None:
        """Connection to multiple targets."""
        conn = Connection(**{"from": "hub", "to": ["spoke1", "spoke2", "spoke3"]})
        assert conn.from_ == "hub"
        assert conn.to == ["spoke1", "spoke2", "spoke3"]

    def test_connection_with_type(self) -> None:
        """Connection with explicit type."""
        conn = Connection(**{"from": "producer", "to": "consumer", "type": "stream"})
        assert conn.type == "stream"

    def test_default_connection_type(self) -> None:
        """Default connection type is 'query'."""
        conn = Connection(**{"from": "a", "to": "b"})
        assert conn.type == "query"


class TestTopologyConfig:
    """Tests for TopologyConfig model."""

    def test_hub_spoke_topology(self) -> None:
        """Hub-spoke topology config."""
        config = TopologyConfig(
            type="hub-spoke",
            hub="controller",
            spokes=["weather", "maps", "travel"],
        )
        assert config.type == "hub-spoke"
        assert config.hub == "controller"
        assert len(config.spokes) == 3

    def test_pipeline_topology_simple(self) -> None:
        """Simple pipeline with single agents per stage."""
        config = TopologyConfig(
            type="pipeline",
            stages=["intake", "process", "output"],
        )
        assert config.type == "pipeline"
        assert config.stages == ["intake", "process", "output"]

    def test_pipeline_topology_parallel_stages(self) -> None:
        """Pipeline with parallel agents in some stages."""
        config = TopologyConfig(
            type="pipeline",
            stages=["intake", ["worker1", "worker2"], "aggregator"],
        )
        assert config.stages[1] == ["worker1", "worker2"]

    def test_dag_topology(self) -> None:
        """DAG topology with explicit connections."""
        config = TopologyConfig(
            type="dag",
            connections=[
                Connection(**{"from": "a", "to": ["b", "c"]}),
                Connection(**{"from": "b", "to": "d"}),
                Connection(**{"from": "c", "to": "d"}),
            ],
        )
        assert config.type == "dag"
        assert len(config.connections) == 3

    def test_mesh_topology(self) -> None:
        """Mesh topology (all-to-all)."""
        config = TopologyConfig(
            type="mesh",
            agents=["agent1", "agent2", "agent3"],
        )
        assert config.type == "mesh"
        assert config.agents == ["agent1", "agent2", "agent3"]

    def test_hierarchical_topology(self) -> None:
        """Hierarchical topology with root and levels."""
        config = TopologyConfig(
            type="hierarchical",
            root="root-coordinator",
            levels=[["level1-a", "level1-b"], ["level2-a", "level2-b", "level2-c"]],
        )
        assert config.type == "hierarchical"
        assert config.root == "root-coordinator"
        assert len(config.levels) == 2

    def test_invalid_topology_type(self) -> None:
        """Invalid topology type should fail."""
        with pytest.raises(ValidationError):
            TopologyConfig(type="invalid-type")


class TestDeploymentConfig:
    """Tests for DeploymentConfig model."""

    def test_default_values(self) -> None:
        """Default deployment configuration."""
        config = DeploymentConfig()
        assert config.strategy == "staged"
        assert config.timeout == 60
        assert config.health_check.enabled is True

    def test_sequential_strategy(self) -> None:
        """Sequential deployment strategy."""
        config = DeploymentConfig(strategy="sequential", timeout=120)
        assert config.strategy == "sequential"
        assert config.timeout == 120

    def test_parallel_strategy(self) -> None:
        """Parallel deployment strategy."""
        config = DeploymentConfig(strategy="parallel")
        assert config.strategy == "parallel"

    def test_invalid_strategy(self) -> None:
        """Invalid strategy should fail."""
        with pytest.raises(ValidationError):
            DeploymentConfig(strategy="invalid")

    def test_custom_health_check(self) -> None:
        """Custom health check settings."""
        config = DeploymentConfig(
            health_check=HealthCheckConfig(
                enabled=True,
                interval=10,
                retries=5,
                timeout=3,
            )
        )
        assert config.health_check.interval == 10
        assert config.health_check.retries == 5


class TestHealthCheckConfig:
    """Tests for HealthCheckConfig model."""

    def test_default_health_check(self) -> None:
        """Default health check values."""
        config = HealthCheckConfig()
        assert config.enabled is True
        assert config.interval == 5
        assert config.retries == 3
        assert config.timeout == 5

    def test_disabled_health_check(self) -> None:
        """Disabled health check."""
        config = HealthCheckConfig(enabled=False)
        assert config.enabled is False

    def test_custom_intervals(self) -> None:
        """Custom check intervals."""
        config = HealthCheckConfig(interval=1, retries=10, timeout=2)
        assert config.interval == 1
        assert config.retries == 10


class TestJobDefinition:
    """Tests for complete JobDefinition model."""

    def _make_agent(
        self, agent_id: str, port: int, target: str = "localhost"
    ) -> AgentConfig:
        """Helper to create agent config."""
        return AgentConfig(
            id=agent_id,
            type="TestAgent",
            module="test.agent",
            config={"port": port},
            deployment=AgentDeploymentConfig(target=target),
        )

    def test_minimal_job_definition(self) -> None:
        """Minimal valid job definition."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[self._make_agent("agent1", 9001)],
            topology=TopologyConfig(type="mesh", agents=["agent1"]),
        )
        assert job.job.name == "test"
        assert len(job.agents) == 1

    def test_duplicate_agent_ids_rejected(self) -> None:
        """Duplicate agent IDs should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            JobDefinition(
                job=JobMetadata(name="test", version="1.0.0", description="Test"),
                agents=[
                    self._make_agent("same-id", 9001),
                    self._make_agent("same-id", 9002),  # duplicate ID
                ],
                topology=TopologyConfig(type="mesh", agents=["same-id"]),
            )
        assert "unique" in str(exc_info.value).lower()

    def test_port_conflict_on_localhost_rejected(self) -> None:
        """Port conflicts on same host should fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            JobDefinition(
                job=JobMetadata(name="test", version="1.0.0", description="Test"),
                agents=[
                    self._make_agent("agent1", 9001, "localhost"),
                    self._make_agent("agent2", 9001, "localhost"),  # same port
                ],
                topology=TopologyConfig(type="mesh", agents=["agent1", "agent2"]),
            )
        assert "port" in str(exc_info.value).lower()

    def test_same_port_different_hosts_allowed(self) -> None:
        """Same port on different hosts should be allowed."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[
                self._make_agent("agent1", 9001, "localhost"),
                AgentConfig(
                    id="agent2",
                    type="TestAgent",
                    module="test.agent",
                    config={"port": 9001},  # same port
                    deployment=AgentDeploymentConfig(
                        target="remote", host="192.168.1.100"
                    ),
                ),
            ],
            topology=TopologyConfig(type="mesh", agents=["agent1", "agent2"]),
        )
        assert len(job.agents) == 2

    def test_get_agent_by_id(self) -> None:
        """get_agent should return correct agent."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[
                self._make_agent("weather", 9001),
                self._make_agent("maps", 9002),
            ],
            topology=TopologyConfig(type="mesh", agents=["weather", "maps"]),
        )

        weather = job.get_agent("weather")
        assert weather is not None
        assert weather.id == "weather"
        assert weather.config["port"] == 9001

        unknown = job.get_agent("unknown")
        assert unknown is None

    def test_get_agent_ids(self) -> None:
        """get_agent_ids should return all IDs."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[
                self._make_agent("a", 9001),
                self._make_agent("b", 9002),
                self._make_agent("c", 9003),
            ],
            topology=TopologyConfig(type="mesh", agents=["a", "b", "c"]),
        )

        ids = job.get_agent_ids()
        assert ids == {"a", "b", "c"}

    def test_full_job_definition(self) -> None:
        """Complete job definition with all fields."""
        job = JobDefinition(
            job=JobMetadata(
                name="full-job",
                version="2.0.0",
                description="Full job",
                tags=["production"],
            ),
            agents=[
                self._make_agent("controller", 9000),
                self._make_agent("weather", 9001),
                self._make_agent("maps", 9002),
            ],
            topology=TopologyConfig(
                type="hub-spoke",
                hub="controller",
                spokes=["weather", "maps"],
            ),
            deployment=DeploymentConfig(
                strategy="staged",
                timeout=120,
            ),
            execution=ExecutionConfig(
                entry_point="controller",
                auto_start=True,
            ),
            environment={"GLOBAL_VAR": "value"},
        )

        assert job.execution.entry_point == "controller"
        assert job.environment["GLOBAL_VAR"] == "value"


class TestDeploymentPlan:
    """Tests for DeploymentPlan model."""

    def test_valid_deployment_plan(self) -> None:
        """Valid deployment plan."""
        plan = DeploymentPlan(
            stages=[["worker1", "worker2"], ["aggregator"]],
            agent_urls={
                "worker1": "http://localhost:9001",
                "worker2": "http://localhost:9002",
                "aggregator": "http://localhost:9000",
            },
            connections={
                "worker1": ["http://localhost:9000"],
                "worker2": ["http://localhost:9000"],
                "aggregator": [],
            },
        )
        assert len(plan.stages) == 2
        assert plan.agent_urls["worker1"] == "http://localhost:9001"


class TestDeployedAgent:
    """Tests for DeployedAgent model."""

    def test_deployed_agent(self) -> None:
        """Deployed agent with process ID."""
        agent = DeployedAgent(
            agent_id="weather",
            url="http://localhost:9001",
            process_id=12345,
            status="healthy",
        )
        assert agent.agent_id == "weather"
        assert agent.process_id == 12345
        assert agent.status == "healthy"

    def test_deployed_agent_default_status(self) -> None:
        """Default status should be 'starting'."""
        agent = DeployedAgent(
            agent_id="test",
            url="http://localhost:9000",
        )
        assert agent.status == "starting"

    def test_container_deployment(self) -> None:
        """Deployed agent in container."""
        agent = DeployedAgent(
            agent_id="test",
            url="http://test:9000",
            container_id="abc123def456",
            status="healthy",
        )
        assert agent.container_id == "abc123def456"


class TestDeployedJob:
    """Tests for DeployedJob model."""

    def test_deployed_job(self) -> None:
        """Complete deployed job."""
        job_def = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[
                AgentConfig(
                    id="agent1",
                    type="TestAgent",
                    module="test",
                    config={"port": 9001},
                    deployment=AgentDeploymentConfig(target="localhost"),
                )
            ],
            topology=TopologyConfig(type="mesh", agents=["agent1"]),
        )

        plan = DeploymentPlan(
            stages=[["agent1"]],
            agent_urls={"agent1": "http://localhost:9001"},
            connections={"agent1": []},
        )

        deployed = DeployedJob(
            job_id="job-123",
            definition=job_def,
            plan=plan,
            agents={
                "agent1": DeployedAgent(
                    agent_id="agent1",
                    url="http://localhost:9001",
                    process_id=12345,
                    status="healthy",
                )
            },
            start_time="2024-01-28T12:00:00",
            status="running",
        )

        assert deployed.job_id == "job-123"
        assert deployed.status == "running"
        assert deployed.agents["agent1"].status == "healthy"

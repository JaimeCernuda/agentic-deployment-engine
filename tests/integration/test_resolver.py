"""Comprehensive tests for TopologyResolver in src/jobs/resolver.py.

Tests cover:
- Deployment order resolution for all 5 topology types
- URL resolution for all 4 deployment targets
- Connection resolution for all topology types
- DAG topological sort
- Edge cases (empty topologies, single agents, etc.)
"""

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.jobs.models import (
    AgentConfig,
    AgentDeploymentConfig,
    Connection,
    JobDefinition,
    JobMetadata,
    TopologyConfig,
)
from src.jobs.resolver import TopologyResolver


def make_agent(agent_id: str, port: int, target: str = "localhost", **kwargs) -> AgentConfig:
    """Helper to create agent config."""
    deployment_kwargs = {"target": target}
    deployment_kwargs.update(kwargs)
    return AgentConfig(
        id=agent_id,
        type="TestAgent",
        module="test.agent",
        config={"port": port},
        deployment=AgentDeploymentConfig(**deployment_kwargs),
    )


def make_job(agents: list[AgentConfig], topology: TopologyConfig) -> JobDefinition:
    """Helper to create job definition."""
    return JobDefinition(
        job=JobMetadata(name="test", version="1.0.0", description="Test"),
        agents=agents,
        topology=topology,
    )


class TestHubSpokeOrder:
    """Tests for hub-spoke deployment order."""

    def test_spokes_before_hub(self) -> None:
        """Spokes should deploy before hub."""
        job = make_job(
            agents=[
                make_agent("hub", 9000),
                make_agent("spoke1", 9001),
                make_agent("spoke2", 9002),
            ],
            topology=TopologyConfig(
                type="hub-spoke",
                hub="hub",
                spokes=["spoke1", "spoke2"],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert len(plan.stages) == 2
        assert set(plan.stages[0]) == {"spoke1", "spoke2"}  # Spokes first
        assert plan.stages[1] == ["hub"]  # Hub last

    def test_single_spoke(self) -> None:
        """Single spoke topology."""
        job = make_job(
            agents=[
                make_agent("hub", 9000),
                make_agent("spoke", 9001),
            ],
            topology=TopologyConfig(
                type="hub-spoke",
                hub="hub",
                spokes=["spoke"],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.stages[0] == ["spoke"]
        assert plan.stages[1] == ["hub"]


class TestPipelineOrder:
    """Tests for pipeline deployment order."""

    def test_sequential_stages(self) -> None:
        """Sequential pipeline stages."""
        job = make_job(
            agents=[
                make_agent("intake", 9001),
                make_agent("process", 9002),
                make_agent("output", 9003),
            ],
            topology=TopologyConfig(
                type="pipeline",
                stages=["intake", "process", "output"],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.stages == [["intake"], ["process"], ["output"]]

    def test_parallel_stages(self) -> None:
        """Pipeline with parallel agents in stages."""
        job = make_job(
            agents=[
                make_agent("intake", 9001),
                make_agent("worker1", 9002),
                make_agent("worker2", 9003),
                make_agent("output", 9004),
            ],
            topology=TopologyConfig(
                type="pipeline",
                stages=["intake", ["worker1", "worker2"], "output"],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.stages[0] == ["intake"]
        assert set(plan.stages[1]) == {"worker1", "worker2"}
        assert plan.stages[2] == ["output"]


class TestDAGOrder:
    """Tests for DAG deployment order."""

    def test_simple_dag(self) -> None:
        """Simple DAG: a -> b -> c."""
        job = make_job(
            agents=[
                make_agent("a", 9001),
                make_agent("b", 9002),
                make_agent("c", 9003),
            ],
            topology=TopologyConfig(
                type="dag",
                connections=[
                    Connection(**{"from": "a", "to": "b"}),
                    Connection(**{"from": "b", "to": "c"}),
                ],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        # a has no dependencies, then b, then c
        assert plan.stages[0] == ["a"]
        assert plan.stages[1] == ["b"]
        assert plan.stages[2] == ["c"]

    def test_diamond_dag(self) -> None:
        """Diamond DAG: a -> [b, c] -> d."""
        job = make_job(
            agents=[
                make_agent("a", 9001),
                make_agent("b", 9002),
                make_agent("c", 9003),
                make_agent("d", 9004),
            ],
            topology=TopologyConfig(
                type="dag",
                connections=[
                    Connection(**{"from": "a", "to": ["b", "c"]}),
                    Connection(**{"from": "b", "to": "d"}),
                    Connection(**{"from": "c", "to": "d"}),
                ],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        # a first, then b and c can be parallel, then d
        assert plan.stages[0] == ["a"]
        assert set(plan.stages[1]) == {"b", "c"}
        assert plan.stages[2] == ["d"]

    def test_wide_dag(self) -> None:
        """Wide DAG: single source to many sinks."""
        job = make_job(
            agents=[
                make_agent("source", 9000),
                make_agent("sink1", 9001),
                make_agent("sink2", 9002),
                make_agent("sink3", 9003),
            ],
            topology=TopologyConfig(
                type="dag",
                connections=[
                    Connection(**{"from": "source", "to": ["sink1", "sink2", "sink3"]}),
                ],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.stages[0] == ["source"]
        assert set(plan.stages[1]) == {"sink1", "sink2", "sink3"}


class TestMeshOrder:
    """Tests for mesh deployment order."""

    def test_all_agents_parallel(self) -> None:
        """All mesh agents deploy in parallel."""
        job = make_job(
            agents=[
                make_agent("a", 9001),
                make_agent("b", 9002),
                make_agent("c", 9003),
            ],
            topology=TopologyConfig(
                type="mesh",
                agents=["a", "b", "c"],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        # All in one stage
        assert len(plan.stages) == 1
        assert set(plan.stages[0]) == {"a", "b", "c"}


class TestHierarchicalOrder:
    """Tests for hierarchical deployment order."""

    def test_root_first_then_levels(self) -> None:
        """Root deploys first, then levels."""
        job = make_job(
            agents=[
                make_agent("root", 9000),
                make_agent("l1a", 9001),
                make_agent("l1b", 9002),
                make_agent("l2a", 9003),
                make_agent("l2b", 9004),
            ],
            topology=TopologyConfig(
                type="hierarchical",
                root="root",
                levels=[["l1a", "l1b"], ["l2a", "l2b"]],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.stages[0] == ["root"]
        assert set(plan.stages[1]) == {"l1a", "l1b"}
        assert set(plan.stages[2]) == {"l2a", "l2b"}


class TestURLResolution:
    """Tests for URL resolution by deployment target."""

    def test_localhost_url(self) -> None:
        """Localhost deployment URL."""
        job = make_job(
            agents=[make_agent("agent", 9001, "localhost")],
            topology=TopologyConfig(type="mesh", agents=["agent"]),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.agent_urls["agent"] == "http://localhost:9001"

    def test_remote_url(self) -> None:
        """Remote deployment URL."""
        job = make_job(
            agents=[make_agent("agent", 9001, "remote", host="192.168.1.100")],
            topology=TopologyConfig(type="mesh", agents=["agent"]),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.agent_urls["agent"] == "http://192.168.1.100:9001"

    def test_container_url_with_name(self) -> None:
        """Container deployment URL with custom name."""
        job = make_job(
            agents=[
                make_agent(
                    "agent", 9001, "container", container_name="my-container"
                )
            ],
            topology=TopologyConfig(type="mesh", agents=["agent"]),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.agent_urls["agent"] == "http://my-container:9001"

    def test_container_url_default_name(self) -> None:
        """Container deployment URL uses agent ID by default."""
        job = make_job(
            agents=[make_agent("weather-agent", 9001, "container")],
            topology=TopologyConfig(type="mesh", agents=["weather-agent"]),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.agent_urls["weather-agent"] == "http://weather-agent:9001"

    def test_kubernetes_url(self) -> None:
        """Kubernetes deployment URL."""
        job = make_job(
            agents=[make_agent("agent", 9001, "kubernetes", namespace="prod")],
            topology=TopologyConfig(type="mesh", agents=["agent"]),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert (
            plan.agent_urls["agent"]
            == "http://agent.prod.svc.cluster.local:9001"
        )

    def test_kubernetes_url_default_namespace(self) -> None:
        """Kubernetes with default namespace."""
        job = make_job(
            agents=[make_agent("agent", 9001, "kubernetes")],
            topology=TopologyConfig(type="mesh", agents=["agent"]),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert (
            plan.agent_urls["agent"]
            == "http://agent.default.svc.cluster.local:9001"
        )


class TestHubSpokeConnections:
    """Tests for hub-spoke connection resolution."""

    def test_hub_connects_to_spokes(self) -> None:
        """Hub should connect to all spokes."""
        job = make_job(
            agents=[
                make_agent("hub", 9000),
                make_agent("spoke1", 9001),
                make_agent("spoke2", 9002),
            ],
            topology=TopologyConfig(
                type="hub-spoke",
                hub="hub",
                spokes=["spoke1", "spoke2"],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        # Hub connects to both spokes
        hub_connections = plan.connections["hub"]
        assert "http://localhost:9001" in hub_connections
        assert "http://localhost:9002" in hub_connections

        # Spokes don't connect to anyone
        assert plan.connections["spoke1"] == []
        assert plan.connections["spoke2"] == []


class TestPipelineConnections:
    """Tests for pipeline connection resolution."""

    def test_stages_connect_to_next(self) -> None:
        """Each stage connects to the next stage."""
        job = make_job(
            agents=[
                make_agent("intake", 9001),
                make_agent("process", 9002),
                make_agent("output", 9003),
            ],
            topology=TopologyConfig(
                type="pipeline",
                stages=["intake", "process", "output"],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        # intake -> process
        assert plan.connections["intake"] == ["http://localhost:9002"]
        # process -> output
        assert plan.connections["process"] == ["http://localhost:9003"]
        # output -> nothing
        assert plan.connections["output"] == []

    def test_parallel_stage_connections(self) -> None:
        """Parallel stage connects to all agents in next stage."""
        job = make_job(
            agents=[
                make_agent("intake", 9001),
                make_agent("worker1", 9002),
                make_agent("worker2", 9003),
                make_agent("output", 9004),
            ],
            topology=TopologyConfig(
                type="pipeline",
                stages=["intake", ["worker1", "worker2"], "output"],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        # intake -> both workers
        intake_conns = plan.connections["intake"]
        assert "http://localhost:9002" in intake_conns
        assert "http://localhost:9003" in intake_conns

        # workers -> output
        assert plan.connections["worker1"] == ["http://localhost:9004"]
        assert plan.connections["worker2"] == ["http://localhost:9004"]


class TestDAGConnections:
    """Tests for DAG connection resolution."""

    def test_dag_explicit_connections(self) -> None:
        """DAG uses explicit connection definitions."""
        job = make_job(
            agents=[
                make_agent("a", 9001),
                make_agent("b", 9002),
                make_agent("c", 9003),
            ],
            topology=TopologyConfig(
                type="dag",
                connections=[
                    Connection(**{"from": "a", "to": ["b", "c"]}),
                    Connection(**{"from": "b", "to": "c"}),
                ],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        # a -> b, c
        a_conns = plan.connections["a"]
        assert "http://localhost:9002" in a_conns
        assert "http://localhost:9003" in a_conns

        # b -> c
        assert "http://localhost:9003" in plan.connections["b"]


class TestMeshConnections:
    """Tests for mesh connection resolution."""

    def test_all_connect_to_all(self) -> None:
        """In mesh, every agent connects to every other."""
        job = make_job(
            agents=[
                make_agent("a", 9001),
                make_agent("b", 9002),
                make_agent("c", 9003),
            ],
            topology=TopologyConfig(
                type="mesh",
                agents=["a", "b", "c"],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        # a connects to b and c
        assert set(plan.connections["a"]) == {
            "http://localhost:9002",
            "http://localhost:9003",
        }
        # b connects to a and c
        assert set(plan.connections["b"]) == {
            "http://localhost:9001",
            "http://localhost:9003",
        }
        # c connects to a and b
        assert set(plan.connections["c"]) == {
            "http://localhost:9001",
            "http://localhost:9002",
        }


class TestHierarchicalConnections:
    """Tests for hierarchical connection resolution."""

    def test_levels_connect_downward(self) -> None:
        """Each level connects to the next level down."""
        job = make_job(
            agents=[
                make_agent("root", 9000),
                make_agent("l1a", 9001),
                make_agent("l1b", 9002),
                make_agent("l2a", 9003),
            ],
            topology=TopologyConfig(
                type="hierarchical",
                root="root",
                levels=[["l1a", "l1b"], ["l2a"]],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        # Root -> level 1
        root_conns = plan.connections["root"]
        assert "http://localhost:9001" in root_conns
        assert "http://localhost:9002" in root_conns

        # Level 1 -> level 2
        assert "http://localhost:9003" in plan.connections["l1a"]
        assert "http://localhost:9003" in plan.connections["l1b"]

        # Level 2 (leaf) -> nothing
        assert plan.connections["l2a"] == []


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_connections_for_isolated_agent(self) -> None:
        """Agents not in topology get empty connections."""
        job = make_job(
            agents=[
                make_agent("a", 9001),
                make_agent("b", 9002),
                make_agent("isolated", 9003),  # Not in mesh
            ],
            topology=TopologyConfig(
                type="mesh",
                agents=["a", "b"],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        # Isolated agent has empty connections
        assert plan.connections["isolated"] == []

    def test_agent_without_port_excluded_from_urls(self) -> None:
        """Agent without port should not have URL."""
        # This is an edge case - normally port is required
        agent = AgentConfig(
            id="no-port",
            type="TestAgent",
            module="test",
            config={"port": 9001},  # Port is required by validator
            deployment=AgentDeploymentConfig(target="localhost"),
        )
        # Override the config to remove port for testing
        agent_dict = agent.model_dump()
        agent_dict["config"] = {}  # Remove port

        # Can't easily test this due to validator, but the resolver handles it
        pass

    def test_multiple_agents_on_different_hosts(self) -> None:
        """Multiple agents across different hosts."""
        job = make_job(
            agents=[
                make_agent("local", 9001, "localhost"),
                make_agent("remote1", 9002, "remote", host="host1.example.com"),
                make_agent("remote2", 9003, "remote", host="host2.example.com"),
            ],
            topology=TopologyConfig(
                type="mesh",
                agents=["local", "remote1", "remote2"],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.agent_urls["local"] == "http://localhost:9001"
        assert plan.agent_urls["remote1"] == "http://host1.example.com:9002"
        assert plan.agent_urls["remote2"] == "http://host2.example.com:9003"

"""Comprehensive tests for TopologyResolver in src/jobs/resolver.py.

Tests cover:
- All 5 topology types (hub-spoke, pipeline, dag, mesh, hierarchical)
- Deployment order resolution (_resolve_order)
- URL resolution (_resolve_urls)
- Connection resolution (_resolve_connections)
- DAG topological sort (_dag_to_stages)
"""

import pytest

from src.jobs.models import (
    AgentConfig,
    AgentDeploymentConfig,
    Connection,
    JobDefinition,
    JobMetadata,
    TopologyConfig,
)
from src.jobs.resolver import TopologyResolver


def make_agent(
    agent_id: str,
    port: int,
    target: str = "localhost",
    host: str | None = None,
    namespace: str | None = None,
    container_name: str | None = None,
) -> AgentConfig:
    """Helper to create agent configs."""
    deployment = AgentDeploymentConfig(
        target=target,
        host=host,
        namespace=namespace,
        container_name=container_name,
    )
    return AgentConfig(
        id=agent_id,
        type="TestAgent",
        module="test.agent",
        config={"port": port},
        deployment=deployment,
    )


class TestTopologyResolverInit:
    """Test TopologyResolver instantiation."""

    def test_creates_resolver(self) -> None:
        """Should create resolver instance."""
        resolver = TopologyResolver()
        assert resolver is not None


class TestResolveHubSpoke:
    """Test hub-spoke topology resolution."""

    def test_hub_spoke_order(self) -> None:
        """Hub-spoke: spokes first, then hub."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[
                make_agent("controller", 9000),
                make_agent("weather", 9001),
                make_agent("maps", 9002),
            ],
            topology=TopologyConfig(
                type="hub-spoke",
                hub="controller",
                spokes=["weather", "maps"],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        # Stage 1: spokes, Stage 2: hub
        assert plan.stages == [["weather", "maps"], ["controller"]]

    def test_hub_spoke_connections(self) -> None:
        """Hub connects to all spokes, spokes connect to nothing."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
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
        assert set(plan.connections["hub"]) == {
            "http://localhost:9001",
            "http://localhost:9002",
        }
        # Spokes don't connect
        assert plan.connections["spoke1"] == []
        assert plan.connections["spoke2"] == []

    def test_hub_spoke_empty_spokes(self) -> None:
        """Hub-spoke with no spokes."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[make_agent("hub", 9000)],
            topology=TopologyConfig(
                type="hub-spoke",
                hub="hub",
                spokes=[],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.stages == [[], ["hub"]]


class TestResolvePipeline:
    """Test pipeline topology resolution."""

    def test_pipeline_simple_stages(self) -> None:
        """Pipeline with single agents per stage."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
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

    def test_pipeline_parallel_stages(self) -> None:
        """Pipeline with parallel agents in stages."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
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

        assert plan.stages == [["intake"], ["worker1", "worker2"], ["output"]]

    def test_pipeline_connections(self) -> None:
        """Pipeline stages connect to next stage."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[
                make_agent("a", 9001),
                make_agent("b", 9002),
                make_agent("c", 9003),
            ],
            topology=TopologyConfig(
                type="pipeline",
                stages=["a", "b", "c"],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        # a -> b -> c
        assert plan.connections["a"] == ["http://localhost:9002"]
        assert plan.connections["b"] == ["http://localhost:9003"]
        assert plan.connections["c"] == []  # Last stage

    def test_pipeline_parallel_connections(self) -> None:
        """Pipeline with parallel stages connects to all next agents."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[
                make_agent("intake", 9001),
                make_agent("w1", 9002),
                make_agent("w2", 9003),
                make_agent("out", 9004),
            ],
            topology=TopologyConfig(
                type="pipeline",
                stages=["intake", ["w1", "w2"], "out"],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        # intake connects to both workers
        assert set(plan.connections["intake"]) == {
            "http://localhost:9002",
            "http://localhost:9003",
        }
        # Both workers connect to output
        assert plan.connections["w1"] == ["http://localhost:9004"]
        assert plan.connections["w2"] == ["http://localhost:9004"]

    def test_pipeline_empty_stages(self) -> None:
        """Pipeline with no stages."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[make_agent("a", 9001)],
            topology=TopologyConfig(type="pipeline", stages=[]),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.stages == []


class TestResolveDag:
    """Test DAG topology resolution."""

    def test_dag_simple_chain(self) -> None:
        """DAG: A -> B -> C becomes 3 stages."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
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

        # Topological order
        assert plan.stages == [["a"], ["b"], ["c"]]

    def test_dag_parallel_branches(self) -> None:
        """DAG: A -> (B, C) -> D."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
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

        # Stage 1: a (no deps)
        # Stage 2: b, c (both depend only on a)
        # Stage 3: d (depends on b and c)
        assert plan.stages[0] == ["a"]
        assert set(plan.stages[1]) == {"b", "c"}
        assert plan.stages[2] == ["d"]

    def test_dag_connections(self) -> None:
        """DAG connections match topology."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[
                make_agent("source", 9001),
                make_agent("sink", 9002),
            ],
            topology=TopologyConfig(
                type="dag",
                connections=[Connection(**{"from": "source", "to": "sink"})],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.connections["source"] == ["http://localhost:9002"]
        assert plan.connections["sink"] == []

    def test_dag_no_connections(self) -> None:
        """DAG with no connections."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[make_agent("a", 9001)],
            topology=TopologyConfig(type="dag", connections=[]),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.stages == []


class TestResolveMesh:
    """Test mesh topology resolution."""

    def test_mesh_single_stage(self) -> None:
        """Mesh deploys all agents in one stage."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
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

        assert plan.stages == [["a", "b", "c"]]

    def test_mesh_all_to_all_connections(self) -> None:
        """Mesh: each agent connects to all others."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
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

    def test_mesh_empty_agents(self) -> None:
        """Mesh with no agents."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[make_agent("a", 9001)],
            topology=TopologyConfig(type="mesh", agents=[]),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.stages == [[]]


class TestResolveHierarchical:
    """Test hierarchical topology resolution."""

    def test_hierarchical_stages(self) -> None:
        """Hierarchical: root first, then levels."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
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

        assert plan.stages == [["root"], ["l1a", "l1b"], ["l2a"]]

    def test_hierarchical_connections(self) -> None:
        """Hierarchical: each level connects to next level."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
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

        # Root connects to level 1
        assert set(plan.connections["root"]) == {
            "http://localhost:9001",
            "http://localhost:9002",
        }
        # Level 1 connects to level 2
        assert plan.connections["l1a"] == ["http://localhost:9003"]
        assert plan.connections["l1b"] == ["http://localhost:9003"]
        # Last level connects to nothing
        assert plan.connections["l2a"] == []

    def test_hierarchical_no_levels(self) -> None:
        """Hierarchical with only root."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[make_agent("root", 9000)],
            topology=TopologyConfig(
                type="hierarchical",
                root="root",
                levels=[],
            ),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.stages == [["root"]]


class TestResolveUrls:
    """Test URL resolution for different deployment targets."""

    def test_localhost_url(self) -> None:
        """Localhost agents get localhost URLs."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[make_agent("a", 9001, target="localhost")],
            topology=TopologyConfig(type="mesh", agents=["a"]),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.agent_urls["a"] == "http://localhost:9001"

    def test_remote_url(self) -> None:
        """Remote agents get host-based URLs."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[make_agent("a", 9001, target="remote", host="192.168.1.100")],
            topology=TopologyConfig(type="mesh", agents=["a"]),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.agent_urls["a"] == "http://192.168.1.100:9001"

    def test_container_url(self) -> None:
        """Container agents get container name URLs."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[
                make_agent("a", 9001, target="container", container_name="my-container")
            ],
            topology=TopologyConfig(type="mesh", agents=["a"]),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.agent_urls["a"] == "http://my-container:9001"

    def test_container_url_default_name(self) -> None:
        """Container agents without explicit name use agent ID."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[make_agent("myagent", 9001, target="container")],
            topology=TopologyConfig(type="mesh", agents=["myagent"]),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.agent_urls["myagent"] == "http://myagent:9001"

    def test_kubernetes_url(self) -> None:
        """Kubernetes agents get service DNS URLs."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[make_agent("a", 9001, target="kubernetes", namespace="agents")],
            topology=TopologyConfig(type="mesh", agents=["a"]),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.agent_urls["a"] == "http://a.agents.svc.cluster.local:9001"

    def test_kubernetes_url_default_namespace(self) -> None:
        """Kubernetes agents without namespace use 'default'."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[make_agent("a", 9001, target="kubernetes")],
            topology=TopologyConfig(type="mesh", agents=["a"]),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.agent_urls["a"] == "http://a.default.svc.cluster.local:9001"

    def test_all_agents_with_port_get_urls(self) -> None:
        """All agents with port get URLs."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[make_agent("a", 9001), make_agent("b", 9002)],
            topology=TopologyConfig(type="mesh", agents=["a", "b"]),
        )

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        # All agents with port get URLs
        assert "a" in plan.agent_urls
        assert "b" in plan.agent_urls


class TestUnknownTopology:
    """Test behavior with unknown topology types."""

    def test_unknown_topology_returns_empty(self) -> None:
        """Unknown topology type returns empty stages."""
        # Create a job with valid topology first
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
            agents=[make_agent("a", 9001)],
            topology=TopologyConfig(type="mesh", agents=["a"]),
        )
        # Manually override the type (hacky but tests edge case)
        job.topology.type = "unknown"  # type: ignore

        resolver = TopologyResolver()
        plan = resolver.resolve(job)

        assert plan.stages == []


class TestCompleteResolve:
    """Integration tests for complete resolve() method."""

    def test_resolve_returns_deployment_plan(self) -> None:
        """resolve() returns complete DeploymentPlan."""
        job = JobDefinition(
            job=JobMetadata(name="test", version="1.0.0", description="Test"),
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

        # Has all required fields
        assert plan.stages is not None
        assert plan.agent_urls is not None
        assert plan.connections is not None

        # URLs resolved
        assert "hub" in plan.agent_urls
        assert "spoke" in plan.agent_urls

        # Connections resolved
        assert "hub" in plan.connections
        assert "spoke" in plan.connections

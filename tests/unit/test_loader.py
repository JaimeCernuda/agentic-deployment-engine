"""Comprehensive tests for JobLoader in src/jobs/loader.py.

Tests cover:
- YAML loading and parsing
- Pydantic validation
- Agent import validation
- Topology reference validation
- Topology structure validation (DAG cycles, etc.)
- Deployment configuration validation
- validate_only() method
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.jobs.loader import JobLoadError, JobLoader


def write_yaml(path: Path, data: dict) -> None:
    """Helper to write YAML files."""
    with open(path, "w") as f:
        yaml.dump(data, f)


def make_minimal_job(
    agents: list[dict] | None = None,
    topology: dict | None = None,
) -> dict:
    """Create minimal valid job definition."""
    default_agents = [
        {
            "id": "test-agent",
            "type": "WeatherAgent",
            "module": "examples.agents.weather_agent",
            "config": {"port": 9001},
            "deployment": {"target": "localhost"},
        },
        {
            "id": "test-agent-2",
            "type": "WeatherAgent",
            "module": "examples.agents.weather_agent",
            "config": {"port": 9002},
            "deployment": {"target": "localhost"},
        },
    ]
    return {
        "job": {
            "name": "test-job",
            "version": "1.0.0",
            "description": "Test job",
        },
        "agents": agents or default_agents,
        "topology": topology or {"type": "mesh", "agents": ["test-agent", "test-agent-2"]},
    }


class TestJobLoaderInit:
    """Test JobLoader instantiation."""

    def test_creates_loader(self) -> None:
        """Should create loader instance."""
        loader = JobLoader()
        assert loader is not None


class TestLoadYamlFile:
    """Test YAML file loading."""

    def test_load_valid_yaml(self) -> None:
        """Should load valid YAML file."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            write_yaml(path, make_minimal_job())

            job = loader.load(path)

            assert job.job.name == "test-job"
            assert job.job.version == "1.0.0"

    def test_file_not_found(self) -> None:
        """Should raise error for missing file."""
        loader = JobLoader()

        with pytest.raises(JobLoadError) as exc_info:
            loader.load("/nonexistent/path/job.yaml")

        assert "not found" in str(exc_info.value)

    def test_invalid_yaml_syntax(self) -> None:
        """Should raise error for invalid YAML."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            with open(path, "w") as f:
                f.write("invalid: yaml: syntax: [")

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "Invalid YAML" in str(exc_info.value)

    def test_yaml_not_dict(self) -> None:
        """Should raise error if YAML is not a dictionary."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            with open(path, "w") as f:
                f.write("- item1\n- item2")  # List, not dict

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "dictionary" in str(exc_info.value)

    def test_accepts_path_object(self) -> None:
        """Should accept Path object."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            write_yaml(path, make_minimal_job())

            job = loader.load(path)
            assert job is not None

    def test_accepts_string_path(self) -> None:
        """Should accept string path."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            write_yaml(path, make_minimal_job())

            job = loader.load(str(path))
            assert job is not None


class TestPydanticValidation:
    """Test Pydantic schema validation."""

    def test_missing_required_fields(self) -> None:
        """Should raise error for missing required fields."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            write_yaml(path, {"job": {"name": "test"}})  # Missing version, description

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "Validation error" in str(exc_info.value)

    def test_invalid_field_types(self) -> None:
        """Should raise error for invalid field types."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            # Use an invalid topology type which must be one of the enum values
            data = make_minimal_job()
            data["topology"]["type"] = "invalid-topology-type"

            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "Validation error" in str(exc_info.value)


class TestAgentImportValidation:
    """Test agent module/type import validation."""

    def test_valid_agent_import(self) -> None:
        """Should accept valid, importable agent."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            write_yaml(path, make_minimal_job())

            # Should not raise
            job = loader.load(path)
            assert len(job.agents) == 2

    def test_invalid_module(self) -> None:
        """Should raise error for non-importable module."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job()
            data["agents"][0]["module"] = "nonexistent.module.that.doesnt.exist"

            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "Cannot import" in str(exc_info.value)

    def test_invalid_agent_type(self) -> None:
        """Should raise error for missing agent type in module."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job()
            data["agents"][0]["type"] = "NonExistentAgentClass"

            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "not found in module" in str(exc_info.value)


class TestTopologyReferenceValidation:
    """Test that topology references valid agent IDs."""

    def test_hub_spoke_invalid_hub(self) -> None:
        """Should raise error for invalid hub ID."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                topology={
                    "type": "hub-spoke",
                    "hub": "nonexistent-hub",
                    "spokes": ["test-agent"],
                }
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "unknown agent" in str(exc_info.value).lower()

    def test_hub_spoke_invalid_spoke(self) -> None:
        """Should raise error for invalid spoke ID."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                topology={
                    "type": "hub-spoke",
                    "hub": "test-agent",
                    "spokes": ["nonexistent-spoke"],
                }
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "unknown agent" in str(exc_info.value).lower()

    def test_hub_spoke_missing_hub(self) -> None:
        """Should raise error when hub-spoke missing hub."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                topology={
                    "type": "hub-spoke",
                    "spokes": ["test-agent"],
                }
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "requires" in str(exc_info.value).lower()

    def test_pipeline_invalid_stage_agent(self) -> None:
        """Should raise error for invalid agent in pipeline stage."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                topology={
                    "type": "pipeline",
                    "stages": ["test-agent", "nonexistent-agent"],
                }
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "unknown agent" in str(exc_info.value).lower()

    def test_pipeline_missing_stages(self) -> None:
        """Should raise error when pipeline missing stages."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                topology={
                    "type": "pipeline",
                }
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "requires" in str(exc_info.value).lower()

    def test_dag_invalid_from_agent(self) -> None:
        """Should raise error for invalid 'from' in DAG connection."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                topology={
                    "type": "dag",
                    "connections": [{"from": "nonexistent", "to": "test-agent"}],
                }
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "unknown agent" in str(exc_info.value).lower()

    def test_dag_invalid_to_agent(self) -> None:
        """Should raise error for invalid 'to' in DAG connection."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                topology={
                    "type": "dag",
                    "connections": [{"from": "test-agent", "to": "nonexistent"}],
                }
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "unknown agent" in str(exc_info.value).lower()

    def test_dag_missing_connections(self) -> None:
        """Should raise error when DAG missing connections."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                topology={
                    "type": "dag",
                }
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "requires" in str(exc_info.value).lower()

    def test_mesh_invalid_agent(self) -> None:
        """Should raise error for invalid agent in mesh."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                topology={
                    "type": "mesh",
                    "agents": ["test-agent", "nonexistent"],
                }
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "unknown agent" in str(exc_info.value).lower()

    def test_mesh_missing_agents(self) -> None:
        """Should raise error when mesh missing agents list."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                topology={
                    "type": "mesh",
                }
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "requires" in str(exc_info.value).lower()

    def test_hierarchical_invalid_root(self) -> None:
        """Should raise error for invalid root in hierarchical."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                topology={
                    "type": "hierarchical",
                    "root": "nonexistent",
                    "levels": [["test-agent"]],
                }
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "unknown agent" in str(exc_info.value).lower()

    def test_hierarchical_invalid_level_agent(self) -> None:
        """Should raise error for invalid agent in hierarchical level."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                topology={
                    "type": "hierarchical",
                    "root": "test-agent",
                    "levels": [["nonexistent"]],
                }
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "unknown agent" in str(exc_info.value).lower()

    def test_hierarchical_missing_root(self) -> None:
        """Should raise error when hierarchical missing root."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                topology={
                    "type": "hierarchical",
                    "levels": [["test-agent"]],
                }
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "requires" in str(exc_info.value).lower()


class TestTopologyStructureValidation:
    """Test topology structure validation (cycles, etc.)."""

    def test_dag_cycle_detection(self) -> None:
        """Should detect cycles in DAG topology."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                agents=[
                    {
                        "id": "a",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9001},
                        "deployment": {"target": "localhost"},
                    },
                    {
                        "id": "b",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9002},
                        "deployment": {"target": "localhost"},
                    },
                    {
                        "id": "c",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9003},
                        "deployment": {"target": "localhost"},
                    },
                ],
                topology={
                    "type": "dag",
                    "connections": [
                        {"from": "a", "to": "b"},
                        {"from": "b", "to": "c"},
                        {"from": "c", "to": "a"},  # Cycle!
                    ],
                },
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "cycle" in str(exc_info.value).lower()

    def test_dag_no_connections_is_valid(self) -> None:
        """DAG with empty connections should pass structure validation."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                topology={
                    "type": "dag",
                    "connections": [],
                }
            )
            write_yaml(path, data)

            # This fails at reference validation (requires connections),
            # not structure validation
            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "requires" in str(exc_info.value).lower()

    def test_pipeline_empty_stage_rejected(self) -> None:
        """Empty pipeline stage should be rejected."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                topology={
                    "type": "pipeline",
                    "stages": ["test-agent", [], "test-agent"],  # Empty stage
                }
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "empty" in str(exc_info.value).lower()

    def test_mesh_single_agent_rejected(self) -> None:
        """Mesh with single agent should be rejected."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                topology={
                    "type": "mesh",
                    "agents": ["test-agent"],  # Only one agent
                }
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "at least 2" in str(exc_info.value).lower()

    def test_hierarchical_root_in_levels_rejected(self) -> None:
        """Root cannot appear in hierarchical levels."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                agents=[
                    {
                        "id": "root",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9001},
                        "deployment": {"target": "localhost"},
                    },
                    {
                        "id": "child",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9002},
                        "deployment": {"target": "localhost"},
                    },
                ],
                topology={
                    "type": "hierarchical",
                    "root": "root",
                    "levels": [["root", "child"]],  # Root in levels!
                },
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "cannot appear" in str(exc_info.value).lower()


class TestDeploymentConfigValidation:
    """Test deployment configuration validation."""

    def test_remote_missing_host(self) -> None:
        """Remote deployment requires host."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                agents=[
                    {
                        "id": "hub",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9001},
                        "deployment": {"target": "remote"},  # No host
                    },
                    {
                        "id": "spoke",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9002},
                        "deployment": {"target": "localhost"},
                    },
                ],
                topology={"type": "hub-spoke", "hub": "hub", "spokes": ["spoke"]},
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "host" in str(exc_info.value).lower()

    def test_remote_with_valid_host(self) -> None:
        """Remote deployment with valid host should pass."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                agents=[
                    {
                        "id": "hub",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9001},
                        "deployment": {"target": "remote", "host": "192.168.1.100"},
                    },
                    {
                        "id": "spoke",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9002},
                        "deployment": {"target": "localhost"},
                    },
                ],
                topology={"type": "hub-spoke", "hub": "hub", "spokes": ["spoke"]},
            )
            write_yaml(path, data)

            job = loader.load(path)
            assert job.agents[0].deployment.host == "192.168.1.100"

    def test_container_missing_image(self) -> None:
        """Container deployment requires image."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                agents=[
                    {
                        "id": "hub",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9001},
                        "deployment": {"target": "container"},  # No image
                    },
                    {
                        "id": "spoke",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9002},
                        "deployment": {"target": "localhost"},
                    },
                ],
                topology={"type": "hub-spoke", "hub": "hub", "spokes": ["spoke"]},
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "image" in str(exc_info.value).lower()

    def test_kubernetes_missing_namespace(self) -> None:
        """Kubernetes deployment requires namespace."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                agents=[
                    {
                        "id": "hub",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9001},
                        "deployment": {"target": "kubernetes"},  # No namespace
                    },
                    {
                        "id": "spoke",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9002},
                        "deployment": {"target": "localhost"},
                    },
                ],
                topology={"type": "hub-spoke", "hub": "hub", "spokes": ["spoke"]},
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "namespace" in str(exc_info.value).lower()

    def test_ssh_key_not_found(self) -> None:
        """Non-existent SSH key should be rejected."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                agents=[
                    {
                        "id": "hub",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9001},
                        "deployment": {
                            "target": "remote",
                            "host": "192.168.1.100",
                            "ssh_key": "/nonexistent/ssh/key",
                        },
                    },
                    {
                        "id": "spoke",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9002},
                        "deployment": {"target": "localhost"},
                    },
                ],
                topology={"type": "hub-spoke", "hub": "hub", "spokes": ["spoke"]},
            )
            write_yaml(path, data)

            with pytest.raises(JobLoadError) as exc_info:
                loader.load(path)

            assert "ssh key not found" in str(exc_info.value).lower()

    def test_password_auth_logs_warning(self) -> None:
        """Password authentication should log warning."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                agents=[
                    {
                        "id": "hub",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9001},
                        "deployment": {
                            "target": "remote",
                            "host": "192.168.1.100",
                            "password": "secret",
                        },
                    },
                    {
                        "id": "spoke",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9002},
                        "deployment": {"target": "localhost"},
                    },
                ],
                topology={"type": "hub-spoke", "hub": "hub", "spokes": ["spoke"]},
            )
            write_yaml(path, data)

            with patch("src.jobs.loader.logger") as mock_logger:
                loader.load(path)
                # Should have logged a warning about password auth
                mock_logger.warning.assert_called()
                assert "password" in str(mock_logger.warning.call_args).lower()


class TestValidateOnly:
    """Test validate_only() method."""

    def test_validate_only_returns_none_for_valid(self) -> None:
        """validate_only returns None for valid job."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            write_yaml(path, make_minimal_job())

            result = loader.validate_only(path)
            assert result is None

    def test_validate_only_returns_error_message(self) -> None:
        """validate_only returns error message for invalid job."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            write_yaml(path, {"invalid": "data"})

            result = loader.validate_only(path)
            assert result is not None
            assert "Validation error" in result

    def test_validate_only_returns_file_not_found(self) -> None:
        """validate_only returns error for missing file."""
        loader = JobLoader()

        result = loader.validate_only("/nonexistent/file.yaml")
        assert result is not None
        assert "not found" in result


class TestMultipleAgents:
    """Test validation with multiple agents."""

    def test_multiple_valid_agents(self) -> None:
        """Should accept multiple valid agents."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                agents=[
                    {
                        "id": "weather",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9001},
                        "deployment": {"target": "localhost"},
                    },
                    {
                        "id": "maps",
                        "type": "MapsAgent",
                        "module": "examples.agents.maps_agent",
                        "config": {"port": 9002},
                        "deployment": {"target": "localhost"},
                    },
                ],
                topology={
                    "type": "mesh",
                    "agents": ["weather", "maps"],
                },
            )
            write_yaml(path, data)

            job = loader.load(path)
            assert len(job.agents) == 2

    def test_dag_with_list_to_targets(self) -> None:
        """DAG with list of 'to' targets should validate."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                agents=[
                    {
                        "id": "source",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9001},
                        "deployment": {"target": "localhost"},
                    },
                    {
                        "id": "sink1",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9002},
                        "deployment": {"target": "localhost"},
                    },
                    {
                        "id": "sink2",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9003},
                        "deployment": {"target": "localhost"},
                    },
                ],
                topology={
                    "type": "dag",
                    "connections": [{"from": "source", "to": ["sink1", "sink2"]}],
                },
            )
            write_yaml(path, data)

            job = loader.load(path)
            assert len(job.agents) == 3

    def test_pipeline_with_parallel_stage(self) -> None:
        """Pipeline with parallel stage should validate agent refs."""
        loader = JobLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.yaml"
            data = make_minimal_job(
                agents=[
                    {
                        "id": "intake",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9001},
                        "deployment": {"target": "localhost"},
                    },
                    {
                        "id": "worker1",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9002},
                        "deployment": {"target": "localhost"},
                    },
                    {
                        "id": "worker2",
                        "type": "WeatherAgent",
                        "module": "examples.agents.weather_agent",
                        "config": {"port": 9003},
                        "deployment": {"target": "localhost"},
                    },
                ],
                topology={
                    "type": "pipeline",
                    "stages": ["intake", ["worker1", "worker2"]],
                },
            )
            write_yaml(path, data)

            job = loader.load(path)
            assert len(job.agents) == 3

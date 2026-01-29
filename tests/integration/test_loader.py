"""Comprehensive tests for JobLoader in src/jobs/loader.py.

Tests cover:
- YAML loading and parsing
- Pydantic validation errors
- Agent importability validation
- Topology reference validation (all 5 types)
- Topology structure validation (cycles, empty stages, etc.)
- Deployment configuration validation
- Error message quality
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.integration

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.jobs.loader import JobLoader, JobLoadError


class TestYAMLLoading:
    """Tests for YAML file loading."""

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Non-existent file should raise JobLoadError."""
        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(tmp_path / "nonexistent.yaml")

        assert "not found" in str(exc_info.value)

    def test_invalid_yaml_syntax(self, tmp_path: Path) -> None:
        """Invalid YAML should raise JobLoadError."""
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text("""
job:
  name: test
  invalid: yaml: syntax:
  - unmatched bracket [
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "Invalid YAML" in str(exc_info.value)

    def test_non_dict_yaml(self, tmp_path: Path) -> None:
        """YAML that's not a dict should raise JobLoadError."""
        yaml_file = tmp_path / "list.yaml"
        yaml_file.write_text("- item1\n- item2\n- item3\n")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "dictionary" in str(exc_info.value)

    def test_empty_yaml(self, tmp_path: Path) -> None:
        """Empty YAML file should raise JobLoadError."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "dictionary" in str(exc_info.value)


class TestPydanticValidation:
    """Tests for Pydantic schema validation."""

    def test_missing_job_metadata(self, tmp_path: Path) -> None:
        """Missing job metadata should fail validation."""
        yaml_file = tmp_path / "missing_job.yaml"
        yaml_file.write_text("""
agents:
  - id: test
    type: TestAgent
    module: test
    config:
      port: 9001
    deployment:
      target: localhost
topology:
  type: mesh
  agents: [test]
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "Validation error" in str(exc_info.value)

    def test_missing_agents(self, tmp_path: Path) -> None:
        """Missing agents should fail validation."""
        yaml_file = tmp_path / "missing_agents.yaml"
        yaml_file.write_text("""
job:
  name: test
  version: "1.0.0"
  description: Test
topology:
  type: mesh
  agents: []
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "Validation error" in str(exc_info.value)

    def test_missing_topology(self, tmp_path: Path) -> None:
        """Missing topology should fail validation."""
        yaml_file = tmp_path / "missing_topology.yaml"
        yaml_file.write_text("""
job:
  name: test
  version: "1.0.0"
  description: Test
agents:
  - id: test
    type: TestAgent
    module: test
    config:
      port: 9001
    deployment:
      target: localhost
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "Validation error" in str(exc_info.value)


class TestAgentImportability:
    """Tests for agent module/class import validation."""

    @patch("importlib.import_module")
    def test_nonexistent_module(self, mock_import, tmp_path: Path) -> None:
        """Non-importable module should fail."""
        mock_import.side_effect = ImportError("No module named 'fake.module'")

        yaml_file = tmp_path / "bad_module.yaml"
        yaml_file.write_text("""
job:
  name: test
  version: "1.0.0"
  description: Test
agents:
  - id: agent1
    type: FakeAgent
    module: fake.module
    config:
      port: 9001
    deployment:
      target: localhost
topology:
  type: mesh
  agents: [agent1]
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "Cannot import" in str(exc_info.value)

    @patch("importlib.import_module")
    def test_missing_agent_class(self, mock_import, tmp_path: Path) -> None:
        """Module exists but agent class doesn't."""
        # Mock module without the agent class
        mock_module = type("MockModule", (), {})()
        mock_import.return_value = mock_module

        yaml_file = tmp_path / "missing_class.yaml"
        yaml_file.write_text("""
job:
  name: test
  version: "1.0.0"
  description: Test
agents:
  - id: agent1
    type: NonexistentAgent
    module: real.module
    config:
      port: 9001
    deployment:
      target: localhost
topology:
  type: mesh
  agents: [agent1]
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "not found in module" in str(exc_info.value)


class TestHubSpokeTopologyValidation:
    """Tests for hub-spoke topology validation."""

    @patch("importlib.import_module")
    def test_missing_hub(self, mock_import, tmp_path: Path) -> None:
        """Hub-spoke without hub should fail."""
        mock_module = type("MockModule", (), {"TestAgent": object})()
        mock_import.return_value = mock_module

        yaml_file = tmp_path / "no_hub.yaml"
        yaml_file.write_text("""
job:
  name: test
  version: "1.0.0"
  description: Test
agents:
  - id: spoke1
    type: TestAgent
    module: test
    config:
      port: 9001
    deployment:
      target: localhost
topology:
  type: hub-spoke
  spokes: [spoke1]
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "hub" in str(exc_info.value).lower()

    @patch("importlib.import_module")
    def test_hub_references_unknown_agent(self, mock_import, tmp_path: Path) -> None:
        """Hub referencing unknown agent should fail."""
        mock_module = type("MockModule", (), {"TestAgent": object})()
        mock_import.return_value = mock_module

        yaml_file = tmp_path / "bad_hub.yaml"
        yaml_file.write_text("""
job:
  name: test
  version: "1.0.0"
  description: Test
agents:
  - id: spoke1
    type: TestAgent
    module: test
    config:
      port: 9001
    deployment:
      target: localhost
topology:
  type: hub-spoke
  hub: unknown-hub
  spokes: [spoke1]
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "unknown agent" in str(exc_info.value).lower()


class TestPipelineTopologyValidation:
    """Tests for pipeline topology validation."""

    @patch("importlib.import_module")
    def test_missing_stages(self, mock_import, tmp_path: Path) -> None:
        """Pipeline without stages should fail."""
        mock_module = type("MockModule", (), {"TestAgent": object})()
        mock_import.return_value = mock_module

        yaml_file = tmp_path / "no_stages.yaml"
        yaml_file.write_text("""
job:
  name: test
  version: "1.0.0"
  description: Test
agents:
  - id: agent1
    type: TestAgent
    module: test
    config:
      port: 9001
    deployment:
      target: localhost
topology:
  type: pipeline
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "stages" in str(exc_info.value).lower()

    @patch("importlib.import_module")
    def test_empty_stage_in_pipeline(self, mock_import, tmp_path: Path) -> None:
        """Empty stage in pipeline should fail."""
        mock_module = type("MockModule", (), {"TestAgent": object})()
        mock_import.return_value = mock_module

        yaml_file = tmp_path / "empty_stage.yaml"
        yaml_file.write_text("""
job:
  name: test
  version: "1.0.0"
  description: Test
agents:
  - id: agent1
    type: TestAgent
    module: test
    config:
      port: 9001
    deployment:
      target: localhost
topology:
  type: pipeline
  stages:
    - agent1
    - []
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "empty" in str(exc_info.value).lower()


class TestDAGTopologyValidation:
    """Tests for DAG topology validation."""

    @patch("importlib.import_module")
    def test_missing_connections(self, mock_import, tmp_path: Path) -> None:
        """DAG without connections should fail."""
        mock_module = type("MockModule", (), {"TestAgent": object})()
        mock_import.return_value = mock_module

        yaml_file = tmp_path / "no_connections.yaml"
        yaml_file.write_text("""
job:
  name: test
  version: "1.0.0"
  description: Test
agents:
  - id: agent1
    type: TestAgent
    module: test
    config:
      port: 9001
    deployment:
      target: localhost
topology:
  type: dag
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "connections" in str(exc_info.value).lower()

    @patch("importlib.import_module")
    def test_dag_with_cycle(self, mock_import, tmp_path: Path) -> None:
        """DAG with cycle should fail."""
        mock_module = type("MockModule", (), {"TestAgent": object})()
        mock_import.return_value = mock_module

        yaml_file = tmp_path / "cyclic_dag.yaml"
        yaml_file.write_text("""
job:
  name: test
  version: "1.0.0"
  description: Test
agents:
  - id: a
    type: TestAgent
    module: test
    config:
      port: 9001
    deployment:
      target: localhost
  - id: b
    type: TestAgent
    module: test
    config:
      port: 9002
    deployment:
      target: localhost
  - id: c
    type: TestAgent
    module: test
    config:
      port: 9003
    deployment:
      target: localhost
topology:
  type: dag
  connections:
    - from: a
      to: b
    - from: b
      to: c
    - from: c
      to: a
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "cycle" in str(exc_info.value).lower()


class TestMeshTopologyValidation:
    """Tests for mesh topology validation."""

    @patch("importlib.import_module")
    def test_missing_agents_in_mesh(self, mock_import, tmp_path: Path) -> None:
        """Mesh without agents should fail."""
        mock_module = type("MockModule", (), {"TestAgent": object})()
        mock_import.return_value = mock_module

        yaml_file = tmp_path / "no_mesh_agents.yaml"
        yaml_file.write_text("""
job:
  name: test
  version: "1.0.0"
  description: Test
agents:
  - id: agent1
    type: TestAgent
    module: test
    config:
      port: 9001
    deployment:
      target: localhost
topology:
  type: mesh
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "agents" in str(exc_info.value).lower()

    @patch("importlib.import_module")
    def test_mesh_with_single_agent(self, mock_import, tmp_path: Path) -> None:
        """Mesh with single agent should fail (need at least 2)."""
        mock_module = type("MockModule", (), {"TestAgent": object})()
        mock_import.return_value = mock_module

        yaml_file = tmp_path / "single_mesh.yaml"
        yaml_file.write_text("""
job:
  name: test
  version: "1.0.0"
  description: Test
agents:
  - id: agent1
    type: TestAgent
    module: test
    config:
      port: 9001
    deployment:
      target: localhost
topology:
  type: mesh
  agents: [agent1]
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "at least 2" in str(exc_info.value).lower()


class TestHierarchicalTopologyValidation:
    """Tests for hierarchical topology validation."""

    @patch("importlib.import_module")
    def test_missing_root(self, mock_import, tmp_path: Path) -> None:
        """Hierarchical without root should fail."""
        mock_module = type("MockModule", (), {"TestAgent": object})()
        mock_import.return_value = mock_module

        yaml_file = tmp_path / "no_root.yaml"
        yaml_file.write_text("""
job:
  name: test
  version: "1.0.0"
  description: Test
agents:
  - id: level1
    type: TestAgent
    module: test
    config:
      port: 9001
    deployment:
      target: localhost
topology:
  type: hierarchical
  levels:
    - [level1]
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "root" in str(exc_info.value).lower()

    @patch("importlib.import_module")
    def test_root_in_levels(self, mock_import, tmp_path: Path) -> None:
        """Root agent appearing in levels should fail."""
        mock_module = type("MockModule", (), {"TestAgent": object})()
        mock_import.return_value = mock_module

        yaml_file = tmp_path / "root_in_levels.yaml"
        yaml_file.write_text("""
job:
  name: test
  version: "1.0.0"
  description: Test
agents:
  - id: root
    type: TestAgent
    module: test
    config:
      port: 9000
    deployment:
      target: localhost
  - id: level1
    type: TestAgent
    module: test
    config:
      port: 9001
    deployment:
      target: localhost
topology:
  type: hierarchical
  root: root
  levels:
    - [root, level1]
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "root" in str(exc_info.value).lower()


class TestDeploymentConfigValidation:
    """Tests for deployment configuration validation."""

    @patch("importlib.import_module")
    def test_remote_without_host(self, mock_import, tmp_path: Path) -> None:
        """Remote deployment without host should fail."""
        mock_module = type("MockModule", (), {"TestAgent": object})()
        mock_import.return_value = mock_module

        yaml_file = tmp_path / "remote_no_host.yaml"
        yaml_file.write_text("""
job:
  name: test
  version: "1.0.0"
  description: Test
agents:
  - id: agent1
    type: TestAgent
    module: test
    config:
      port: 9001
    deployment:
      target: remote
topology:
  type: mesh
  agents: [agent1, agent1]
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "host" in str(exc_info.value).lower()

    @patch("importlib.import_module")
    def test_container_without_image(self, mock_import, tmp_path: Path) -> None:
        """Container deployment without image should fail."""
        mock_module = type("MockModule", (), {"TestAgent": object})()
        mock_import.return_value = mock_module

        yaml_file = tmp_path / "container_no_image.yaml"
        yaml_file.write_text("""
job:
  name: test
  version: "1.0.0"
  description: Test
agents:
  - id: agent1
    type: TestAgent
    module: test
    config:
      port: 9001
    deployment:
      target: container
  - id: agent2
    type: TestAgent
    module: test
    config:
      port: 9002
    deployment:
      target: container
topology:
  type: mesh
  agents: [agent1, agent2]
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "image" in str(exc_info.value).lower()

    @patch("importlib.import_module")
    def test_kubernetes_without_namespace(self, mock_import, tmp_path: Path) -> None:
        """Kubernetes deployment without namespace should fail."""
        mock_module = type("MockModule", (), {"TestAgent": object})()
        mock_import.return_value = mock_module

        yaml_file = tmp_path / "k8s_no_ns.yaml"
        yaml_file.write_text("""
job:
  name: test
  version: "1.0.0"
  description: Test
agents:
  - id: agent1
    type: TestAgent
    module: test
    config:
      port: 9001
    deployment:
      target: kubernetes
  - id: agent2
    type: TestAgent
    module: test
    config:
      port: 9002
    deployment:
      target: kubernetes
topology:
  type: mesh
  agents: [agent1, agent2]
""")

        loader = JobLoader()
        with pytest.raises(JobLoadError) as exc_info:
            loader.load(yaml_file)

        assert "namespace" in str(exc_info.value).lower()


class TestValidateOnly:
    """Tests for validate_only method."""

    @patch("importlib.import_module")
    def test_validate_only_returns_none_on_success(
        self, mock_import, tmp_path: Path
    ) -> None:
        """validate_only returns None for valid file."""
        mock_module = type("MockModule", (), {"TestAgent": object})()
        mock_import.return_value = mock_module

        yaml_file = tmp_path / "valid.yaml"
        yaml_file.write_text("""
job:
  name: test
  version: "1.0.0"
  description: Test
agents:
  - id: agent1
    type: TestAgent
    module: test
    config:
      port: 9001
    deployment:
      target: localhost
  - id: agent2
    type: TestAgent
    module: test
    config:
      port: 9002
    deployment:
      target: localhost
topology:
  type: mesh
  agents: [agent1, agent2]
""")

        loader = JobLoader()
        result = loader.validate_only(yaml_file)
        assert result is None

    def test_validate_only_returns_error_on_failure(self, tmp_path: Path) -> None:
        """validate_only returns error message for invalid file."""
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text("invalid: yaml: [")

        loader = JobLoader()
        result = loader.validate_only(yaml_file)

        assert result is not None
        assert "YAML" in result or "Invalid" in result


class TestSuccessfulLoading:
    """Tests for successful job loading."""

    @patch("importlib.import_module")
    def test_load_valid_hub_spoke_job(self, mock_import, tmp_path: Path) -> None:
        """Load valid hub-spoke job."""
        mock_module = type(
            "MockModule", (), {"ControllerAgent": object, "WorkerAgent": object}
        )()
        mock_import.return_value = mock_module

        yaml_file = tmp_path / "hub_spoke.yaml"
        yaml_file.write_text("""
job:
  name: hub-spoke-job
  version: "1.0.0"
  description: Hub-spoke topology test
agents:
  - id: controller
    type: ControllerAgent
    module: agents.controller
    config:
      port: 9000
    deployment:
      target: localhost
  - id: worker1
    type: WorkerAgent
    module: agents.worker
    config:
      port: 9001
    deployment:
      target: localhost
  - id: worker2
    type: WorkerAgent
    module: agents.worker
    config:
      port: 9002
    deployment:
      target: localhost
topology:
  type: hub-spoke
  hub: controller
  spokes: [worker1, worker2]
deployment:
  strategy: staged
  timeout: 60
""")

        loader = JobLoader()
        job = loader.load(yaml_file)

        assert job.job.name == "hub-spoke-job"
        assert len(job.agents) == 3
        assert job.topology.type == "hub-spoke"
        assert job.topology.hub == "controller"

    @patch("importlib.import_module")
    def test_load_valid_pipeline_job(self, mock_import, tmp_path: Path) -> None:
        """Load valid pipeline job."""
        mock_module = type("MockModule", (), {"StageAgent": object})()
        mock_import.return_value = mock_module

        yaml_file = tmp_path / "pipeline.yaml"
        yaml_file.write_text("""
job:
  name: pipeline-job
  version: "1.0.0"
  description: Pipeline topology test
agents:
  - id: intake
    type: StageAgent
    module: agents.stage
    config:
      port: 9001
    deployment:
      target: localhost
  - id: process
    type: StageAgent
    module: agents.stage
    config:
      port: 9002
    deployment:
      target: localhost
  - id: output
    type: StageAgent
    module: agents.stage
    config:
      port: 9003
    deployment:
      target: localhost
topology:
  type: pipeline
  stages:
    - intake
    - process
    - output
""")

        loader = JobLoader()
        job = loader.load(yaml_file)

        assert job.topology.type == "pipeline"
        assert job.topology.stages == ["intake", "process", "output"]

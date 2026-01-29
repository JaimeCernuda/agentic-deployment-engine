"""Comprehensive tests for the CLI module (src/jobs/cli.py).

Tests all CLI commands:
- validate: Job definition validation
- plan: Deployment plan generation
- start: Job deployment
- status: Job status display
- stop: Job stopping
- list: Job listing
- logs: Log viewing
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.jobs.cli import app
from src.jobs.models import (
    AgentConfig,
    AgentDeploymentConfig,
    DeploymentConfig,
    DeploymentPlan,
    HealthCheckConfig,
    JobDefinition,
    JobMetadata,
    TopologyConfig,
)
from src.jobs.registry import AgentState, JobState

runner = CliRunner()


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def valid_job_yaml(tmp_path: Path) -> Path:
    """Create a valid job YAML file for testing."""
    job_content = """
job:
  name: test-job
  version: "1.0.0"
  description: Test job for CLI testing

agents:
  - id: agent1
    type: TestAgent
    module: agents.test_agent
    config:
      port: 9001
    deployment:
      target: localhost

topology:
  type: hub-spoke
  hub: agent1
"""
    job_file = tmp_path / "test-job.yaml"
    job_file.write_text(job_content)
    return job_file


@pytest.fixture
def invalid_job_yaml(tmp_path: Path) -> Path:
    """Create an invalid job YAML file."""
    job_file = tmp_path / "invalid-job.yaml"
    job_file.write_text("invalid: yaml: content:")
    return job_file


@pytest.fixture
def mock_job_definition() -> JobDefinition:
    """Create a mock JobDefinition."""
    return JobDefinition(
        job=JobMetadata(
            name="test-job",
            version="1.0.0",
            description="Test job",
        ),
        agents=[
            AgentConfig(
                id="agent1",
                type="TestAgent",
                module="agents.test_agent",
                config={"port": 9001},
                deployment=AgentDeploymentConfig(target="localhost"),
            ),
        ],
        topology=TopologyConfig(type="hub-spoke", hub="agent1"),
        deployment=DeploymentConfig(
            strategy="staged",
            timeout=30,
            health_check=HealthCheckConfig(retries=3, interval=5),
        ),
    )


@pytest.fixture
def mock_deployment_plan() -> DeploymentPlan:
    """Create a mock DeploymentPlan."""
    return DeploymentPlan(
        stages=[["agent1"]],
        agent_urls={"agent1": "http://localhost:9001"},
        connections={"agent1": []},
    )


@pytest.fixture
def mock_job_state() -> JobState:
    """Create a mock JobState for testing."""
    return JobState(
        job_id="test-job",
        job_file="/path/to/test-job.yaml",
        status="running",
        start_time=datetime.now().isoformat(),
        topology_type="hub-spoke",
        agents={
            "agent1": AgentState(
                agent_id="agent1",
                url="http://localhost:9001",
                process_id=12345,
                status="running",
            ),
        },
    )


# ============================================================================
# Validate Command Tests
# ============================================================================


class TestValidateCommand:
    """Tests for the validate command."""

    def test_validate_valid_job_succeeds(self, valid_job_yaml: Path) -> None:
        """Validating a valid job file should succeed."""
        with patch("src.jobs.cli.JobLoader") as MockLoader:
            mock_loader = MockLoader.return_value
            mock_loader.load.return_value = MagicMock()

            result = runner.invoke(app, ["validate", str(valid_job_yaml)])

            assert result.exit_code == 0
            assert "valid" in result.stdout.lower()

    def test_validate_invalid_job_fails(self, invalid_job_yaml: Path) -> None:
        """Validating an invalid job file should fail."""
        from src.jobs.loader import JobLoadError

        with patch("src.jobs.cli.JobLoader") as MockLoader:
            mock_loader = MockLoader.return_value
            mock_loader.load.side_effect = JobLoadError("Invalid YAML")

            result = runner.invoke(app, ["validate", str(invalid_job_yaml)])

            assert result.exit_code == 1
            assert "failed" in result.stdout.lower()

    def test_validate_nonexistent_file_fails(self, tmp_path: Path) -> None:
        """Validating a nonexistent file should fail."""
        nonexistent = tmp_path / "nonexistent.yaml"

        from src.jobs.loader import JobLoadError

        with patch("src.jobs.cli.JobLoader") as MockLoader:
            mock_loader = MockLoader.return_value
            mock_loader.load.side_effect = JobLoadError("File not found")

            result = runner.invoke(app, ["validate", str(nonexistent)])

            assert result.exit_code == 1

    def test_validate_verbose_shows_details(
        self, valid_job_yaml: Path, mock_job_definition: JobDefinition
    ) -> None:
        """Verbose validation should show job details."""
        with patch("src.jobs.cli.JobLoader") as MockLoader:
            mock_loader = MockLoader.return_value
            mock_loader.load.return_value = mock_job_definition

            result = runner.invoke(app, ["validate", str(valid_job_yaml), "-v"])

            assert result.exit_code == 0
            assert "test-job" in result.stdout
            assert "1.0.0" in result.stdout

    def test_validate_verbose_shows_agent_table(
        self, valid_job_yaml: Path, mock_job_definition: JobDefinition
    ) -> None:
        """Verbose validation should show agent table."""
        with patch("src.jobs.cli.JobLoader") as MockLoader:
            mock_loader = MockLoader.return_value
            mock_loader.load.return_value = mock_job_definition

            result = runner.invoke(app, ["validate", str(valid_job_yaml), "--verbose"])

            assert result.exit_code == 0
            assert "agent1" in result.stdout


# ============================================================================
# Plan Command Tests
# ============================================================================


class TestPlanCommand:
    """Tests for the plan command."""

    def test_plan_generates_table_output(
        self,
        valid_job_yaml: Path,
        mock_job_definition: JobDefinition,
        mock_deployment_plan: DeploymentPlan,
    ) -> None:
        """Plan command should generate table output by default."""
        with (
            patch("src.jobs.cli.JobLoader") as MockLoader,
            patch("src.jobs.cli.TopologyResolver") as MockResolver,
        ):
            MockLoader.return_value.load.return_value = mock_job_definition
            MockResolver.return_value.resolve.return_value = mock_deployment_plan

            result = runner.invoke(app, ["plan", str(valid_job_yaml)])

            assert result.exit_code == 0
            assert "Plan" in result.stdout or "Stage" in result.stdout

    def test_plan_generates_json_output(
        self,
        valid_job_yaml: Path,
        mock_job_definition: JobDefinition,
        mock_deployment_plan: DeploymentPlan,
    ) -> None:
        """Plan command with --format json should output JSON."""
        with (
            patch("src.jobs.cli.JobLoader") as MockLoader,
            patch("src.jobs.cli.TopologyResolver") as MockResolver,
        ):
            MockLoader.return_value.load.return_value = mock_job_definition
            MockResolver.return_value.resolve.return_value = mock_deployment_plan

            result = runner.invoke(app, ["plan", str(valid_job_yaml), "-f", "json"])

            assert result.exit_code == 0
            # JSON output should contain job name
            assert "test-job" in result.stdout

    def test_plan_invalid_job_fails(self, invalid_job_yaml: Path) -> None:
        """Plan command should fail for invalid job."""
        from src.jobs.loader import JobLoadError

        with patch("src.jobs.cli.JobLoader") as MockLoader:
            MockLoader.return_value.load.side_effect = JobLoadError("Invalid")

            result = runner.invoke(app, ["plan", str(invalid_job_yaml)])

            assert result.exit_code == 1
            assert "failed" in result.stdout.lower()

    def test_plan_shows_stages(
        self,
        valid_job_yaml: Path,
        mock_job_definition: JobDefinition,
    ) -> None:
        """Plan command should show deployment stages."""
        plan = DeploymentPlan(
            stages=[["agent1"], ["agent2", "agent3"]],
            agent_urls={
                "agent1": "http://localhost:9001",
                "agent2": "http://localhost:9002",
                "agent3": "http://localhost:9003",
            },
            connections={
                "agent1": [],
                "agent2": ["http://localhost:9001"],
                "agent3": ["http://localhost:9001"],
            },
        )

        with (
            patch("src.jobs.cli.JobLoader") as MockLoader,
            patch("src.jobs.cli.TopologyResolver") as MockResolver,
        ):
            MockLoader.return_value.load.return_value = mock_job_definition
            MockResolver.return_value.resolve.return_value = plan

            result = runner.invoke(app, ["plan", str(valid_job_yaml)])

            assert result.exit_code == 0
            assert "2 stages" in result.stdout.lower()

    def test_plan_shows_connections(
        self,
        valid_job_yaml: Path,
        mock_job_definition: JobDefinition,
        mock_deployment_plan: DeploymentPlan,
    ) -> None:
        """Plan command should show agent connections."""
        with (
            patch("src.jobs.cli.JobLoader") as MockLoader,
            patch("src.jobs.cli.TopologyResolver") as MockResolver,
        ):
            MockLoader.return_value.load.return_value = mock_job_definition
            MockResolver.return_value.resolve.return_value = mock_deployment_plan

            result = runner.invoke(app, ["plan", str(valid_job_yaml)])

            assert result.exit_code == 0
            # Should show some form of connection info
            assert "agent1" in result.stdout


# ============================================================================
# Start Command Tests
# ============================================================================


class TestStartCommand:
    """Tests for the start command."""

    def test_start_invalid_job_fails(self, invalid_job_yaml: Path) -> None:
        """Start command should fail for invalid job."""
        from src.jobs.loader import JobLoadError

        with patch("src.jobs.cli.JobLoader") as MockLoader:
            MockLoader.return_value.load.side_effect = JobLoadError("Invalid")

            result = runner.invoke(app, ["start", str(invalid_job_yaml)])

            assert result.exit_code == 1
            assert "failed" in result.stdout.lower()

    def test_start_deployment_error_fails(
        self,
        valid_job_yaml: Path,
        mock_job_definition: JobDefinition,
        mock_deployment_plan: DeploymentPlan,
    ) -> None:
        """Start command should fail on deployment error."""
        from src.jobs.deployer import DeploymentError

        with (
            patch("src.jobs.cli.JobLoader") as MockLoader,
            patch("src.jobs.cli.TopologyResolver") as MockResolver,
            patch("src.jobs.cli.AgentDeployer") as MockDeployer,
        ):
            MockLoader.return_value.load.return_value = mock_job_definition
            MockResolver.return_value.resolve.return_value = mock_deployment_plan
            MockDeployer.return_value.deploy = AsyncMock(
                side_effect=DeploymentError("Connection refused")
            )

            result = runner.invoke(app, ["start", str(valid_job_yaml)])

            assert result.exit_code == 1
            assert "failed" in result.stdout.lower()


# ============================================================================
# Status Command Tests
# ============================================================================


class TestStatusCommand:
    """Tests for the status command."""

    def test_status_nonexistent_job_fails(self) -> None:
        """Status for nonexistent job should fail."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = None
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["status", "nonexistent-job"])

            assert result.exit_code == 1
            assert "not found" in result.stdout.lower()

    def test_status_running_job_shows_info(
        self, mock_job_state: JobState
    ) -> None:
        """Status for running job should show info."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = mock_job_state
            mock_get_registry.return_value = mock_registry

            # Mock the health check
            with patch("src.jobs.cli.asyncio.run") as mock_run:
                mock_run.return_value = {"agent1": "[green]healthy[/green]"}

                result = runner.invoke(app, ["status", "test-job"])

            assert result.exit_code == 0
            assert "test-job" in result.stdout

    def test_status_shows_agent_details(
        self, mock_job_state: JobState
    ) -> None:
        """Status should show agent URL and PID."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = mock_job_state
            mock_get_registry.return_value = mock_registry

            with patch("src.jobs.cli.asyncio.run") as mock_run:
                mock_run.return_value = {"agent1": "[green]healthy[/green]"}

                result = runner.invoke(app, ["status", "test-job"])

            assert result.exit_code == 0
            assert "9001" in result.stdout or "localhost" in result.stdout


# ============================================================================
# Stop Command Tests
# ============================================================================


class TestStopCommand:
    """Tests for the stop command."""

    def test_stop_nonexistent_job_fails(self) -> None:
        """Stop for nonexistent job should fail."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = None
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["stop", "nonexistent-job"])

            assert result.exit_code == 1
            assert "not found" in result.stdout.lower()

    def test_stop_already_stopped_job_exits_clean(
        self,
    ) -> None:
        """Stop for already stopped job should exit cleanly."""
        stopped_job = JobState(
            job_id="stopped-job",
            job_file="/path/to/job.yaml",
            status="stopped",
            start_time=datetime.now().isoformat(),
            agents={},
        )

        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = stopped_job
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["stop", "stopped-job"])

            assert result.exit_code == 0
            assert "not running" in result.stdout.lower()

    def test_stop_running_job_kills_processes(
        self, mock_job_state: JobState
    ) -> None:
        """Stop should kill running agent processes."""
        with (
            patch("src.jobs.cli.get_registry") as mock_get_registry,
            patch("os.kill") as mock_kill,
        ):
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = mock_job_state
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["stop", "test-job"])

            assert result.exit_code == 0
            # os.kill should have been called with the agent PID
            mock_kill.assert_called()

    @pytest.mark.skipif(sys.platform == "win32", reason="SIGKILL not available on Windows")
    def test_stop_force_uses_sigkill(
        self, mock_job_state: JobState
    ) -> None:
        """Stop with --force should use SIGKILL."""
        import signal

        with (
            patch("src.jobs.cli.get_registry") as mock_get_registry,
            patch("os.kill") as mock_kill,
        ):
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = mock_job_state
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["stop", "test-job", "--force"])

            assert result.exit_code == 0
            # Should have used SIGKILL
            mock_kill.assert_called_with(12345, signal.SIGKILL)

    def test_stop_handles_process_not_found(
        self, mock_job_state: JobState
    ) -> None:
        """Stop should handle ProcessLookupError gracefully."""
        with (
            patch("src.jobs.cli.get_registry") as mock_get_registry,
            patch("os.kill") as mock_kill,
        ):
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = mock_job_state
            mock_get_registry.return_value = mock_registry
            mock_kill.side_effect = ProcessLookupError()

            result = runner.invoke(app, ["stop", "test-job"])

            assert result.exit_code == 0
            assert "already stopped" in result.stdout.lower()

    def test_stop_handles_permission_error(
        self, mock_job_state: JobState
    ) -> None:
        """Stop should handle PermissionError gracefully."""
        with (
            patch("src.jobs.cli.get_registry") as mock_get_registry,
            patch("os.kill") as mock_kill,
        ):
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = mock_job_state
            mock_get_registry.return_value = mock_registry
            mock_kill.side_effect = PermissionError()

            result = runner.invoke(app, ["stop", "test-job"])

            # Should still complete but note the failure
            assert "permission" in result.stdout.lower()


# ============================================================================
# List Command Tests
# ============================================================================


class TestListCommand:
    """Tests for the list command."""

    def test_list_empty_registry_shows_message(self) -> None:
        """List with no jobs should show informative message."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.list_jobs.return_value = []
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["list"])

            assert result.exit_code == 0
            assert "no" in result.stdout.lower()

    def test_list_shows_running_jobs_by_default(
        self, mock_job_state: JobState
    ) -> None:
        """List should show running jobs by default."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.list_jobs.return_value = [mock_job_state]
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["list"])

            assert result.exit_code == 0
            mock_registry.list_jobs.assert_called_with(status="running", limit=20)

    def test_list_all_shows_all_jobs(
        self, mock_job_state: JobState
    ) -> None:
        """List with --all should show all jobs."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.list_jobs.return_value = [mock_job_state]
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["list", "--all"])

            assert result.exit_code == 0
            mock_registry.list_jobs.assert_called_with(status=None, limit=20)

    def test_list_limit_parameter(self) -> None:
        """List should respect --limit parameter."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.list_jobs.return_value = []
            mock_get_registry.return_value = mock_registry

            runner.invoke(app, ["list", "--limit", "5"])

            mock_registry.list_jobs.assert_called_with(status="running", limit=5)

    def test_list_shows_job_details(
        self, mock_job_state: JobState
    ) -> None:
        """List should show job ID, status, and agent count."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.list_jobs.return_value = [mock_job_state]
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["list"])

            assert result.exit_code == 0
            assert "test-job" in result.stdout


# ============================================================================
# Logs Command Tests
# ============================================================================


class TestLogsCommand:
    """Tests for the logs command."""

    def test_logs_nonexistent_job_fails(self) -> None:
        """Logs for nonexistent job should fail."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = None
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["logs", "nonexistent-job"])

            assert result.exit_code == 1
            assert "not found" in result.stdout.lower()

    def test_logs_shows_agent_logs(
        self, mock_job_state: JobState, tmp_path: Path
    ) -> None:
        """Logs should show agent log files."""
        # Create mock log files
        log_dir = tmp_path / "logs" / "jobs"
        log_dir.mkdir(parents=True)
        stdout_log = log_dir / "agent1.stdout.log"
        stdout_log.write_text("Agent started\nProcessing query\n")

        with (
            patch("src.jobs.cli.get_registry") as mock_get_registry,
            patch("src.jobs.cli.Path.cwd") as mock_cwd,
        ):
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = mock_job_state
            mock_get_registry.return_value = mock_registry
            mock_cwd.return_value = tmp_path

            result = runner.invoke(app, ["logs", "test-job"])

            assert result.exit_code == 0
            assert "agent1" in result.stdout

    def test_logs_tail_limits_output(
        self, mock_job_state: JobState, tmp_path: Path
    ) -> None:
        """Logs --tail should limit lines shown."""
        # Create mock log with many lines
        log_dir = tmp_path / "logs" / "jobs"
        log_dir.mkdir(parents=True)
        stdout_log = log_dir / "agent1.stdout.log"
        stdout_log.write_text("\n".join([f"Line {i}" for i in range(100)]))

        with (
            patch("src.jobs.cli.get_registry") as mock_get_registry,
            patch("src.jobs.cli.Path.cwd") as mock_cwd,
        ):
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = mock_job_state
            mock_get_registry.return_value = mock_registry
            mock_cwd.return_value = tmp_path

            result = runner.invoke(app, ["logs", "test-job", "--tail", "10"])

            assert result.exit_code == 0
            # Should only show last 10 lines
            assert "Line 99" in result.stdout

    def test_logs_specific_agent(
        self, mock_job_state: JobState, tmp_path: Path
    ) -> None:
        """Logs --agent should show specific agent logs."""
        # Create mock log files
        log_dir = tmp_path / "logs" / "jobs"
        log_dir.mkdir(parents=True)
        stdout_log = log_dir / "agent1.stdout.log"
        stdout_log.write_text("Agent1 log content\n")

        with (
            patch("src.jobs.cli.get_registry") as mock_get_registry,
            patch("src.jobs.cli.Path.cwd") as mock_cwd,
        ):
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = mock_job_state
            mock_get_registry.return_value = mock_registry
            mock_cwd.return_value = tmp_path

            result = runner.invoke(app, ["logs", "test-job", "--agent", "agent1"])

            assert result.exit_code == 0
            assert "agent1" in result.stdout.lower()

    def test_logs_nonexistent_agent_shows_warning(
        self, mock_job_state: JobState
    ) -> None:
        """Logs for nonexistent agent should show warning."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = mock_job_state
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["logs", "test-job", "--agent", "fake-agent"])

            assert result.exit_code == 0
            assert "not found" in result.stdout.lower()

    def test_logs_follow_not_implemented(
        self, mock_job_state: JobState, tmp_path: Path
    ) -> None:
        """Logs --follow should show not implemented message."""
        log_dir = tmp_path / "logs" / "jobs"
        log_dir.mkdir(parents=True)
        stdout_log = log_dir / "agent1.stdout.log"
        stdout_log.write_text("Log content\n")

        with (
            patch("src.jobs.cli.get_registry") as mock_get_registry,
            patch("src.jobs.cli.Path.cwd") as mock_cwd,
        ):
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = mock_job_state
            mock_get_registry.return_value = mock_registry
            mock_cwd.return_value = tmp_path

            result = runner.invoke(app, ["logs", "test-job", "--follow"])

            assert result.exit_code == 0
            assert "not yet implemented" in result.stdout.lower()


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestCLIEdgeCases:
    """Tests for CLI edge cases and error handling."""

    def test_help_command_works(self) -> None:
        """Help command should work."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "deploy" in result.stdout.lower() or "job" in result.stdout.lower()

    def test_validate_help_works(self) -> None:
        """Validate --help should work."""
        result = runner.invoke(app, ["validate", "--help"])

        assert result.exit_code == 0
        assert "validate" in result.stdout.lower()

    def test_plan_help_works(self) -> None:
        """Plan --help should work."""
        result = runner.invoke(app, ["plan", "--help"])

        assert result.exit_code == 0

    def test_start_help_works(self) -> None:
        """Start --help should work."""
        result = runner.invoke(app, ["start", "--help"])

        assert result.exit_code == 0

    def test_unknown_command_fails(self) -> None:
        """Unknown command should fail."""
        result = runner.invoke(app, ["unknown-command"])

        assert result.exit_code != 0

    def test_missing_required_argument_fails(self) -> None:
        """Missing required argument should fail."""
        result = runner.invoke(app, ["validate"])

        assert result.exit_code != 0

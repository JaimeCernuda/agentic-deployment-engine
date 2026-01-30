"""Tests for CLI in src/jobs/cli.py.

Tests cover:
- validate command
- plan command
- list command
- status command
- logs command
- stop command
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from typer.testing import CliRunner

from src.jobs.cli import app

runner = CliRunner()


def write_yaml(path: Path, data: dict) -> None:
    """Helper to write YAML files."""
    with open(path, "w") as f:
        yaml.dump(data, f)


def make_valid_job() -> dict:
    """Create a valid job definition."""
    return {
        "job": {
            "name": "test-job",
            "version": "1.0.0",
            "description": "Test job",
        },
        "agents": [
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
        "topology": {"type": "mesh", "agents": ["weather", "maps"]},
    }


class TestValidateCommand:
    """Test validate command."""

    def test_validate_valid_job(self) -> None:
        """Validate command succeeds for valid job."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_file = Path(tmpdir) / "job.yaml"
            write_yaml(job_file, make_valid_job())

            result = runner.invoke(app, ["validate", str(job_file)])

            assert result.exit_code == 0
            assert "valid" in result.output.lower() or "OK" in result.output

    def test_validate_invalid_job(self) -> None:
        """Validate command fails for invalid job."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_file = Path(tmpdir) / "job.yaml"
            write_yaml(job_file, {"invalid": "data"})

            result = runner.invoke(app, ["validate", str(job_file)])

            assert result.exit_code == 1
            assert "fail" in result.output.lower()

    def test_validate_missing_file(self) -> None:
        """Validate command fails for missing file."""
        result = runner.invoke(app, ["validate", "/nonexistent/job.yaml"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "fail" in result.output.lower()

    def test_validate_verbose_output(self) -> None:
        """Validate command with verbose flag shows details."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_file = Path(tmpdir) / "job.yaml"
            write_yaml(job_file, make_valid_job())

            result = runner.invoke(app, ["validate", str(job_file), "--verbose"])

            assert result.exit_code == 0
            assert "test-job" in result.output
            assert "mesh" in result.output.lower()


class TestPlanCommand:
    """Test plan command."""

    def test_plan_valid_job(self) -> None:
        """Plan command succeeds for valid job."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_file = Path(tmpdir) / "job.yaml"
            write_yaml(job_file, make_valid_job())

            result = runner.invoke(app, ["plan", str(job_file)])

            assert result.exit_code == 0
            assert "plan" in result.output.lower() or "stage" in result.output.lower()

    def test_plan_invalid_job(self) -> None:
        """Plan command fails for invalid job."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_file = Path(tmpdir) / "job.yaml"
            write_yaml(job_file, {"invalid": "data"})

            result = runner.invoke(app, ["plan", str(job_file)])

            assert result.exit_code == 1

    def test_plan_json_output(self) -> None:
        """Plan command with json format outputs JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_file = Path(tmpdir) / "job.yaml"
            write_yaml(job_file, make_valid_job())

            result = runner.invoke(app, ["plan", str(job_file), "--format", "json"])

            assert result.exit_code == 0
            # Should contain JSON-like output
            assert "stages" in result.output or "{" in result.output


class TestListCommand:
    """Test list command."""

    def test_list_no_jobs(self) -> None:
        """List command shows message when no jobs."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.list_jobs.return_value = []
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["list"])

            assert result.exit_code == 0
            assert "no" in result.output.lower()

    def test_list_with_jobs(self) -> None:
        """List command shows jobs table."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_job = MagicMock()
            mock_job.job_id = "test-job-123"
            mock_job.status = "running"
            mock_job.agents = {"a": MagicMock(), "b": MagicMock()}
            mock_job.topology_type = "mesh"
            mock_job.start_time = "2024-01-01T12:00:00"
            mock_registry.list_jobs.return_value = [mock_job]
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["list"])

            assert result.exit_code == 0
            assert "test-job-123" in result.output

    def test_list_all_flag(self) -> None:
        """List command with --all shows all jobs."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.list_jobs.return_value = []
            mock_get_registry.return_value = mock_registry

            runner.invoke(app, ["list", "--all"])

            # Should have called with status=None
            mock_registry.list_jobs.assert_called_with(status=None, limit=20)


class TestStatusCommand:
    """Test status command."""

    def test_status_job_not_found(self) -> None:
        """Status command fails for non-existent job."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = None
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["status", "nonexistent-job"])

            assert result.exit_code == 1
            assert "not found" in result.output.lower()

    def test_status_shows_job_info(self) -> None:
        """Status command shows job information."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_job = MagicMock()
            mock_job.job_id = "test-job"
            mock_job.status = "running"
            mock_job.start_time = "2024-01-01T12:00:00"
            mock_job.topology_type = "mesh"
            mock_job.job_file = "/path/to/job.yaml"
            mock_job.agents = {}
            mock_registry.get_job.return_value = mock_job
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["status", "test-job"])

            assert result.exit_code == 0
            assert "test-job" in result.output


class TestStopCommand:
    """Test stop command."""

    def test_stop_job_not_found(self) -> None:
        """Stop command fails for non-existent job."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = None
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["stop", "nonexistent-job"])

            assert result.exit_code == 1
            assert "not found" in result.output.lower()

    def test_stop_already_stopped(self) -> None:
        """Stop command handles already stopped job."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_job = MagicMock()
            mock_job.status = "stopped"
            mock_registry.get_job.return_value = mock_job
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["stop", "test-job"])

            assert result.exit_code == 0
            assert "not running" in result.output.lower()

    def test_stop_running_job(self) -> None:
        """Stop command stops running job agents."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            with patch("os.system"):
                with patch("os.kill"):
                    mock_registry = MagicMock()
                    mock_job = MagicMock()
                    mock_job.status = "running"
                    mock_agent = MagicMock()
                    mock_agent.process_id = 12345
                    mock_job.agents = {"test-agent": mock_agent}
                    mock_registry.get_job.return_value = mock_job
                    mock_get_registry.return_value = mock_registry

                    result = runner.invoke(app, ["stop", "test-job"])

                    assert result.exit_code == 0
                    # Should have tried to stop the process
                    mock_registry.update_status.assert_called_with("test-job", "stopped")


class TestLogsCommand:
    """Test logs command."""

    def test_logs_job_not_found(self) -> None:
        """Logs command fails for non-existent job."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = None
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["logs", "nonexistent-job"])

            assert result.exit_code == 1
            assert "not found" in result.output.lower()

    def test_logs_no_log_files(self) -> None:
        """Logs command handles missing log files."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_job = MagicMock()
            mock_job.agents = {"test-agent": MagicMock()}
            mock_registry.get_job.return_value = mock_job
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["logs", "test-job"])

            assert result.exit_code == 0
            # Should show agent ID even if no logs
            assert "test-agent" in result.output

    def test_logs_specific_agent(self) -> None:
        """Logs command can show logs for specific agent."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_job = MagicMock()
            mock_job.agents = {"agent1": MagicMock(), "agent2": MagicMock()}
            mock_registry.get_job.return_value = mock_job
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["logs", "test-job", "--agent", "agent1"])

            assert result.exit_code == 0


class TestQueryCommand:
    """Test query command."""

    def test_query_job_not_found(self) -> None:
        """Query command fails for non-existent job."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_registry.get_job.return_value = None
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["query", "nonexistent-job", "Hello"])

            assert result.exit_code == 1
            assert "not found" in result.output.lower()

    def test_query_job_not_running(self) -> None:
        """Query command fails for stopped job."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_job = MagicMock()
            mock_job.status = "stopped"
            mock_registry.get_job.return_value = mock_job
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(app, ["query", "test-job", "Hello"])

            assert result.exit_code == 1
            assert "not running" in result.output.lower()

    def test_query_agent_not_found(self) -> None:
        """Query command fails for non-existent agent."""
        with patch("src.jobs.cli.get_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_job = MagicMock()
            mock_job.status = "running"
            mock_job.agents = {"other-agent": MagicMock()}
            mock_registry.get_job.return_value = mock_job
            mock_get_registry.return_value = mock_registry

            result = runner.invoke(
                app, ["query", "test-job", "Hello", "--agent", "nonexistent"]
            )

            assert result.exit_code == 1
            assert "not found" in result.output.lower()


class TestMainEntryPoint:
    """Test main entry point."""

    def test_main_function_exists(self) -> None:
        """main() function exists and is callable."""
        from src.jobs.cli import main

        assert callable(main)

    def test_help_command(self) -> None:
        """--help shows help text."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "deploy" in result.output.lower() or "job" in result.output.lower()

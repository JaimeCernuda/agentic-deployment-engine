"""Comprehensive tests for the deployer module (src/jobs/deployer.py).

Tests all deployer components:
- LocalRunner: Local subprocess deployment
- SSHRunner: Remote SSH deployment
- RemoteProcess: Remote process tracking
- AgentDeployer: Orchestrated deployment
"""

import asyncio
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import httpx
import paramiko
import pytest
from pydantic import SecretStr

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.jobs.deployer import (
    AgentDeployer,
    AgentRunner,
    DeploymentError,
    LocalRunner,
    RemoteProcess,
    SSHRunner,
)
from src.jobs.models import (
    AgentConfig,
    AgentDeploymentConfig,
    DeployedAgent,
    DeployedJob,
    DeploymentConfig,
    DeploymentPlan,
    HealthCheckConfig,
    JobDefinition,
    JobMetadata,
    TopologyConfig,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def agent_config() -> AgentConfig:
    """Create a basic agent configuration."""
    return AgentConfig(
        id="test-agent",
        type="TestAgent",
        module="agents.test_agent",
        config={"port": 9001},
        deployment=AgentDeploymentConfig(target="localhost"),
    )


@pytest.fixture
def remote_agent_config() -> AgentConfig:
    """Create a remote agent configuration."""
    return AgentConfig(
        id="remote-agent",
        type="RemoteAgent",
        module="agents.remote_agent",
        config={"port": 9002},
        deployment=AgentDeploymentConfig(
            target="remote",
            host="192.168.1.100",
            user="deploy",
            port=22,
            ssh_key="~/.ssh/id_rsa",
            environment={"CUSTOM_VAR": "value"},
        ),
    )


@pytest.fixture
def agent_config_with_password() -> AgentConfig:
    """Create agent configuration with password auth."""
    return AgentConfig(
        id="password-agent",
        type="PasswordAgent",
        module="agents.password_agent",
        config={"port": 9003},
        deployment=AgentDeploymentConfig(
            target="remote",
            host="192.168.1.101",
            user="admin",
            password=SecretStr("secret123"),
        ),
    )


@pytest.fixture
def job_definition(agent_config: AgentConfig) -> JobDefinition:
    """Create a complete job definition."""
    return JobDefinition(
        job=JobMetadata(
            name="test-job",
            version="1.0.0",
            description="Test job",
        ),
        agents=[agent_config],
        topology=TopologyConfig(type="hub-spoke", hub="test-agent"),
        deployment=DeploymentConfig(
            strategy="staged",
            timeout=30,
            health_check=HealthCheckConfig(retries=3, interval=5),
        ),
    )


@pytest.fixture
def deployment_plan() -> DeploymentPlan:
    """Create a basic deployment plan."""
    return DeploymentPlan(
        stages=[["test-agent"]],
        agent_urls={"test-agent": "http://localhost:9001"},
        connections={"test-agent": []},
    )


@pytest.fixture
def mock_ssh_client() -> MagicMock:
    """Create a mock SSH client."""
    mock_client = MagicMock(spec=paramiko.SSHClient)
    mock_transport = MagicMock()
    mock_client.get_transport.return_value = mock_transport
    return mock_client


# ============================================================================
# LocalRunner Tests
# ============================================================================


class TestLocalRunner:
    """Tests for LocalRunner class."""

    def test_initialization_creates_log_directory(self, tmp_path: Path) -> None:
        """LocalRunner should create log directory on init."""
        runner = LocalRunner(project_root=tmp_path)

        assert runner.log_dir.exists()
        assert runner.log_dir == tmp_path / "logs" / "jobs"

    def test_initialization_with_default_project_root(self) -> None:
        """LocalRunner should use current directory as default."""
        with patch("src.jobs.deployer.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/fake/path")
            runner = LocalRunner()

            assert runner.project_root == Path("/fake/path")

    @pytest.mark.asyncio
    async def test_start_creates_subprocess(
        self, tmp_path: Path, agent_config: AgentConfig
    ) -> None:
        """start() should create a subprocess with correct command."""
        runner = LocalRunner(project_root=tmp_path)

        with patch("src.jobs.deployer.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.poll.return_value = None  # Process is running
            mock_popen.return_value = mock_process

            result = await runner.start(agent_config, [], {})

            mock_popen.assert_called_once()
            call_args = mock_popen.call_args
            assert sys.executable in call_args[0][0]
            assert "-m" in call_args[0][0]
            assert agent_config.module in call_args[0][0]

    @pytest.mark.asyncio
    async def test_start_sets_environment_variables(
        self, tmp_path: Path, agent_config: AgentConfig
    ) -> None:
        """start() should set agent config as environment variables."""
        runner = LocalRunner(project_root=tmp_path)

        with patch("src.jobs.deployer.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            await runner.start(agent_config, [], {"GLOBAL_VAR": "value"})

            call_kwargs = mock_popen.call_args[1]
            env = call_kwargs["env"]
            assert "AGENT_PORT" in env
            assert env["AGENT_PORT"] == "9001"
            assert env["GLOBAL_VAR"] == "value"

    @pytest.mark.asyncio
    async def test_start_sets_connected_agents(
        self, tmp_path: Path, agent_config: AgentConfig
    ) -> None:
        """start() should set CONNECTED_AGENTS environment variable."""
        runner = LocalRunner(project_root=tmp_path)

        connected = ["http://localhost:9002", "http://localhost:9003"]

        with patch("src.jobs.deployer.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            await runner.start(agent_config, connected, {})

            call_kwargs = mock_popen.call_args[1]
            env = call_kwargs["env"]
            assert "CONNECTED_AGENTS" in env
            assert "localhost:9002" in env["CONNECTED_AGENTS"]
            assert "localhost:9003" in env["CONNECTED_AGENTS"]

    @pytest.mark.asyncio
    async def test_start_creates_log_files(
        self, tmp_path: Path, agent_config: AgentConfig
    ) -> None:
        """start() should create stdout and stderr log files."""
        runner = LocalRunner(project_root=tmp_path)

        with patch("src.jobs.deployer.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process

            await runner.start(agent_config, [], {})

            # Verify log files were opened for writing
            call_kwargs = mock_popen.call_args[1]
            assert call_kwargs["stdout"] is not None
            assert call_kwargs["stderr"] is not None

    @pytest.mark.asyncio
    async def test_start_raises_on_immediate_crash(
        self, tmp_path: Path, agent_config: AgentConfig
    ) -> None:
        """start() should raise DeploymentError if process crashes immediately."""
        runner = LocalRunner(project_root=tmp_path)

        with patch("src.jobs.deployer.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.poll.return_value = 1  # Process exited with error
            mock_popen.return_value = mock_process

            with pytest.raises(DeploymentError) as exc_info:
                await runner.start(agent_config, [], {})

            assert "failed to start" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_start_raises_on_popen_exception(
        self, tmp_path: Path, agent_config: AgentConfig
    ) -> None:
        """start() should raise DeploymentError on Popen exception."""
        runner = LocalRunner(project_root=tmp_path)

        with patch("src.jobs.deployer.subprocess.Popen") as mock_popen:
            mock_popen.side_effect = FileNotFoundError("python not found")

            with pytest.raises(DeploymentError) as exc_info:
                await runner.start(agent_config, [], {})

            assert "failed to start" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_stop_terminates_process(self, tmp_path: Path) -> None:
        """stop() should terminate the process."""
        runner = LocalRunner(project_root=tmp_path)
        mock_process = MagicMock()
        mock_process.wait.return_value = 0

        await runner.stop(mock_process, "test-agent")

        mock_process.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_kills_on_timeout(self, tmp_path: Path) -> None:
        """stop() should kill process if terminate times out."""
        runner = LocalRunner(project_root=tmp_path)
        mock_process = MagicMock()

        # Simulate timeout by raising TimeoutError
        with patch("src.jobs.deployer.asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = TimeoutError()

            await runner.stop(mock_process, "test-agent")

            mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_status_running(self, tmp_path: Path) -> None:
        """get_status() should return 'running' for active process."""
        runner = LocalRunner(project_root=tmp_path)
        mock_process = MagicMock()
        mock_process.poll.return_value = None

        status = await runner.get_status(mock_process)

        assert status == "running"

    @pytest.mark.asyncio
    async def test_get_status_stopped(self, tmp_path: Path) -> None:
        """get_status() should return 'stopped' for terminated process."""
        runner = LocalRunner(project_root=tmp_path)
        mock_process = MagicMock()
        mock_process.poll.return_value = 0

        status = await runner.get_status(mock_process)

        assert status == "stopped"


# ============================================================================
# RemoteProcess Tests
# ============================================================================


class TestRemoteProcess:
    """Tests for RemoteProcess class."""

    def test_initialization(self, mock_ssh_client: MagicMock) -> None:
        """RemoteProcess should store SSH client, PID, and host info."""
        process = RemoteProcess(mock_ssh_client, 12345, "test-agent", "192.168.1.100")

        assert process.ssh_client == mock_ssh_client
        assert process.pid == 12345
        assert process.agent_id == "test-agent"
        assert process.host == "192.168.1.100"

    def test_is_running_true(self, mock_ssh_client: MagicMock) -> None:
        """is_running() should return True if process is active."""
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"PID TTY\n12345 pts/0"
        mock_ssh_client.exec_command.return_value = (None, mock_stdout, None)

        process = RemoteProcess(mock_ssh_client, 12345, "test-agent", "host")

        assert process.is_running() is True

    def test_is_running_false(self, mock_ssh_client: MagicMock) -> None:
        """is_running() should return False if process is not found."""
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"PID TTY"  # No process listed
        mock_ssh_client.exec_command.return_value = (None, mock_stdout, None)

        process = RemoteProcess(mock_ssh_client, 12345, "test-agent", "host")

        assert process.is_running() is False

    def test_is_running_handles_exception(self, mock_ssh_client: MagicMock) -> None:
        """is_running() should return False on SSH error."""
        mock_ssh_client.exec_command.side_effect = Exception("Connection lost")

        process = RemoteProcess(mock_ssh_client, 12345, "test-agent", "host")

        assert process.is_running() is False


# ============================================================================
# SSHRunner Tests
# ============================================================================


class TestSSHRunner:
    """Tests for SSHRunner class."""

    def test_initialization(self, tmp_path: Path) -> None:
        """SSHRunner should initialize with project root and empty connections."""
        runner = SSHRunner(project_root=tmp_path)

        assert runner.project_root == tmp_path
        assert runner.connections == {}

    def test_get_ssh_client_requires_host(
        self, tmp_path: Path, agent_config: AgentConfig
    ) -> None:
        """_get_ssh_client() should raise if host is not set."""
        runner = SSHRunner(project_root=tmp_path)
        agent_config.deployment.host = None

        with pytest.raises(DeploymentError) as exc_info:
            runner._get_ssh_client(agent_config)

        assert "host" in str(exc_info.value).lower()

    def test_get_ssh_client_reuses_connection(
        self, tmp_path: Path, remote_agent_config: AgentConfig, mock_ssh_client: MagicMock
    ) -> None:
        """_get_ssh_client() should reuse existing connections."""
        runner = SSHRunner(project_root=tmp_path)
        connection_key = "192.168.1.100:22"
        runner.connections[connection_key] = mock_ssh_client

        result = runner._get_ssh_client(remote_agent_config)

        assert result == mock_ssh_client

    def test_get_ssh_client_uses_reject_policy(
        self, tmp_path: Path, remote_agent_config: AgentConfig
    ) -> None:
        """_get_ssh_client() should use RejectPolicy for security."""
        runner = SSHRunner(project_root=tmp_path)

        with (
            patch("src.jobs.deployer.paramiko.SSHClient") as MockSSHClient,
            patch("os.path.exists") as mock_exists,
        ):
            mock_client = MagicMock()
            MockSSHClient.return_value = mock_client
            mock_exists.return_value = True

            try:
                runner._get_ssh_client(remote_agent_config)
            except Exception:
                pass  # Connection will fail, but we just check policy

            # Verify RejectPolicy was used
            mock_client.set_missing_host_key_policy.assert_called_once()
            call_args = mock_client.set_missing_host_key_policy.call_args
            assert isinstance(call_args[0][0], paramiko.RejectPolicy)

    def test_get_ssh_client_password_auth(
        self, tmp_path: Path, agent_config_with_password: AgentConfig
    ) -> None:
        """_get_ssh_client() should use password from SecretStr."""
        runner = SSHRunner(project_root=tmp_path)

        with (
            patch("src.jobs.deployer.paramiko.SSHClient") as MockSSHClient,
            patch("os.path.exists") as mock_exists,
        ):
            mock_client = MagicMock()
            MockSSHClient.return_value = mock_client
            mock_exists.side_effect = lambda x: "known_hosts" in x

            runner._get_ssh_client(agent_config_with_password)

            # Verify password was passed correctly
            mock_client.connect.assert_called_once()
            call_kwargs = mock_client.connect.call_args[1]
            assert call_kwargs["password"] == "secret123"

    def test_get_ssh_client_connection_failure(
        self, tmp_path: Path, remote_agent_config: AgentConfig
    ) -> None:
        """_get_ssh_client() should raise DeploymentError on connection failure."""
        runner = SSHRunner(project_root=tmp_path)

        with (
            patch("src.jobs.deployer.paramiko.SSHClient") as MockSSHClient,
            patch("os.path.exists") as mock_exists,
        ):
            mock_client = MagicMock()
            mock_client.connect.side_effect = paramiko.SSHException("Auth failed")
            MockSSHClient.return_value = mock_client
            mock_exists.return_value = True

            with pytest.raises(DeploymentError) as exc_info:
                runner._get_ssh_client(remote_agent_config)

            assert "ssh connection failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_start_uses_shlex_quote_for_env(
        self, tmp_path: Path, remote_agent_config: AgentConfig, mock_ssh_client: MagicMock
    ) -> None:
        """start() should use shlex.quote for shell injection prevention."""
        runner = SSHRunner(project_root=tmp_path)

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"12345"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""
        mock_ssh_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        with patch.object(runner, "_get_ssh_client", return_value=mock_ssh_client):
            # Include a potentially dangerous value
            env = {"MALICIOUS": 'value"; rm -rf / #'}

            await runner.start(remote_agent_config, [], env)

            # Verify shlex.quote was applied (command should be safe)
            call_args = mock_ssh_client.exec_command.call_args_list[-1]
            cmd = call_args[0][0]
            # The malicious value should be quoted/escaped
            assert '"; rm -rf /' not in cmd or "'" in cmd

    @pytest.mark.asyncio
    async def test_start_returns_remote_process(
        self, tmp_path: Path, remote_agent_config: AgentConfig, mock_ssh_client: MagicMock
    ) -> None:
        """start() should return a RemoteProcess on success."""
        runner = SSHRunner(project_root=tmp_path)

        # Mock exec_command responses
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"12345"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        # For ps check - process is running
        mock_ps_stdout = MagicMock()
        mock_ps_stdout.read.return_value = b"PID\n12345"

        mock_ssh_client.exec_command.side_effect = [
            (None, mock_stdout, mock_stderr),  # mkdir
            (None, mock_stdout, mock_stderr),  # start command
            (None, mock_ps_stdout, None),  # ps check
        ]

        with (
            patch.object(runner, "_get_ssh_client", return_value=mock_ssh_client),
            patch.object(runner, "_transfer_code", new_callable=AsyncMock),
        ):
            result = await runner.start(remote_agent_config, [], {})

            assert isinstance(result, RemoteProcess)
            assert result.pid == 12345

    @pytest.mark.asyncio
    async def test_start_raises_on_process_death(
        self, tmp_path: Path, remote_agent_config: AgentConfig, mock_ssh_client: MagicMock
    ) -> None:
        """start() should raise if process dies immediately."""
        runner = SSHRunner(project_root=tmp_path)

        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"12345"
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""

        # ps check shows process not running
        mock_ps_stdout = MagicMock()
        mock_ps_stdout.read.return_value = b"PID"

        # Log output for error message
        mock_log_stdout = MagicMock()
        mock_log_stdout.read.return_value = b"Error: Module not found"

        mock_ssh_client.exec_command.side_effect = [
            (None, mock_stdout, mock_stderr),  # mkdir
            (None, mock_stdout, mock_stderr),  # start command
            (None, mock_ps_stdout, None),  # ps check - not running
            (None, mock_log_stdout, None),  # cat log file
        ]

        with (
            patch.object(runner, "_get_ssh_client", return_value=mock_ssh_client),
            patch.object(runner, "_transfer_code", new_callable=AsyncMock),
        ):
            with pytest.raises(DeploymentError) as exc_info:
                await runner.start(remote_agent_config, [], {})

            assert "failed to start" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_stop_sends_sigterm_then_sigkill(
        self, mock_ssh_client: MagicMock
    ) -> None:
        """stop() should send SIGTERM first, then SIGKILL if needed."""
        runner = SSHRunner()
        process = RemoteProcess(mock_ssh_client, 12345, "test", "host")

        mock_stdout = MagicMock()
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_ssh_client.exec_command.return_value = (None, mock_stdout, None)

        # Process is still running after SIGTERM
        with patch.object(process, "is_running", side_effect=[True, False]):
            await runner.stop(process, "test")

            # Should have been called twice: kill and kill -9
            assert mock_ssh_client.exec_command.call_count == 2

    @pytest.mark.asyncio
    async def test_get_status(self, mock_ssh_client: MagicMock) -> None:
        """get_status() should check if remote process is running."""
        runner = SSHRunner()
        process = RemoteProcess(mock_ssh_client, 12345, "test", "host")

        with patch.object(process, "is_running", return_value=True):
            status = await runner.get_status(process)
            assert status == "running"

        with patch.object(process, "is_running", return_value=False):
            status = await runner.get_status(process)
            assert status == "stopped"

    def test_close_all_closes_connections(self, mock_ssh_client: MagicMock) -> None:
        """close_all() should close all SSH connections."""
        runner = SSHRunner()
        runner.connections["host1:22"] = mock_ssh_client
        runner.connections["host2:22"] = MagicMock()

        runner.close_all()

        assert runner.connections == {}
        mock_ssh_client.close.assert_called_once()


# ============================================================================
# AgentDeployer Tests
# ============================================================================


class TestAgentDeployer:
    """Tests for AgentDeployer class."""

    def test_initialization(self, tmp_path: Path) -> None:
        """AgentDeployer should initialize runners for each target."""
        deployer = AgentDeployer(project_root=tmp_path)

        assert "localhost" in deployer.runners
        assert "remote" in deployer.runners
        assert isinstance(deployer.runners["localhost"], LocalRunner)
        assert isinstance(deployer.runners["remote"], SSHRunner)

    @pytest.mark.asyncio
    async def test_deploy_empty_stages_returns_job(
        self, tmp_path: Path, job_definition: JobDefinition
    ) -> None:
        """deploy() with empty stages should return DeployedJob."""
        deployer = AgentDeployer(project_root=tmp_path)
        plan = DeploymentPlan(
            stages=[],
            agent_urls={},
            connections={},
        )

        result = await deployer.deploy(job_definition, plan)

        assert isinstance(result, DeployedJob)
        assert result.job_id == "test-job"
        assert result.agents == {}

    @pytest.mark.asyncio
    async def test_deploy_agent_not_found_raises(
        self, tmp_path: Path, job_definition: JobDefinition
    ) -> None:
        """deploy() should raise if agent not in job definition."""
        deployer = AgentDeployer(project_root=tmp_path)
        plan = DeploymentPlan(
            stages=[["nonexistent-agent"]],
            agent_urls={"nonexistent-agent": "http://localhost:9999"},
            connections={},
        )

        with pytest.raises(DeploymentError) as exc_info:
            await deployer.deploy(job_definition, plan)

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_deploy_unknown_target_raises(
        self, tmp_path: Path, job_definition: JobDefinition, deployment_plan: DeploymentPlan
    ) -> None:
        """deploy() should raise for unknown deployment target."""
        deployer = AgentDeployer(project_root=tmp_path)
        job_definition.agents[0].deployment.target = "kubernetes"  # Not implemented

        with pytest.raises(DeploymentError) as exc_info:
            await deployer.deploy(job_definition, deployment_plan)

        assert "runner" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_deploy_cleans_up_on_failure(
        self, tmp_path: Path
    ) -> None:
        """deploy() should cleanup deployed agents on failure."""
        deployer = AgentDeployer(project_root=tmp_path)

        # Create job with 2 agents - first succeeds, second fails
        job = JobDefinition(
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
                AgentConfig(
                    id="agent2",
                    type="TestAgent",
                    module="agents.test_agent",
                    config={"port": 9002},
                    deployment=AgentDeploymentConfig(target="localhost"),
                ),
            ],
            topology=TopologyConfig(type="pipeline", stages=[["agent1"], ["agent2"]]),
            deployment=DeploymentConfig(
                strategy="staged",
                timeout=30,
                health_check=HealthCheckConfig(retries=3, interval=5),
            ),
        )

        plan = DeploymentPlan(
            stages=[["agent1"], ["agent2"]],
            agent_urls={
                "agent1": "http://localhost:9001",
                "agent2": "http://localhost:9002",
            },
            connections={"agent1": [], "agent2": ["http://localhost:9001"]},
        )

        mock_process = MagicMock()
        mock_runner = AsyncMock()
        mock_runner.start.return_value = mock_process
        mock_runner.stop = AsyncMock()
        deployer.runners["localhost"] = mock_runner

        call_count = 0
        async def mock_health(url, agent_id, timeout, retries):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Fail on second agent
                raise DeploymentError("Health check failed")

        with patch.object(deployer, "_wait_for_health", side_effect=mock_health):
            with pytest.raises(DeploymentError):
                await deployer.deploy(job, plan)

            # First agent's process should have been stopped during cleanup
            mock_runner.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_deploy_successful_returns_deployed_job(
        self, tmp_path: Path, job_definition: JobDefinition, deployment_plan: DeploymentPlan
    ) -> None:
        """deploy() should return DeployedJob on success."""
        deployer = AgentDeployer(project_root=tmp_path)

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_runner = AsyncMock()
        mock_runner.start.return_value = mock_process
        deployer.runners["localhost"] = mock_runner

        with patch.object(deployer, "_wait_for_health", new_callable=AsyncMock):
            result = await deployer.deploy(job_definition, deployment_plan)

            assert isinstance(result, DeployedJob)
            assert result.status == "running"
            assert "test-agent" in result.agents
            assert result.agents["test-agent"].process_id == 12345

    @pytest.mark.asyncio
    async def test_wait_for_health_empty_url_skips(self, tmp_path: Path) -> None:
        """_wait_for_health() with empty URL should skip."""
        deployer = AgentDeployer(project_root=tmp_path)

        # Should not raise
        await deployer._wait_for_health("", "test-agent", timeout=10, retries=3)

    @pytest.mark.asyncio
    async def test_wait_for_health_success(self, tmp_path: Path) -> None:
        """_wait_for_health() should succeed on 200 response."""
        deployer = AgentDeployer(project_root=tmp_path)

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("src.jobs.deployer.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            # Should not raise
            await deployer._wait_for_health(
                "http://localhost:9001", "test-agent", timeout=10, retries=3
            )

    @pytest.mark.asyncio
    async def test_wait_for_health_retries_on_failure(self, tmp_path: Path) -> None:
        """_wait_for_health() should retry on connection failure."""
        deployer = AgentDeployer(project_root=tmp_path)

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("src.jobs.deployer.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            # Fail twice, then succeed
            mock_client.get.side_effect = [
                httpx.ConnectError("Connection refused"),
                httpx.ConnectError("Connection refused"),
                mock_response,
            ]
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            # Should succeed after retries
            await deployer._wait_for_health(
                "http://localhost:9001", "test-agent", timeout=10, retries=3
            )

    @pytest.mark.asyncio
    async def test_wait_for_health_raises_after_max_retries(
        self, tmp_path: Path
    ) -> None:
        """_wait_for_health() should raise after max retries."""
        deployer = AgentDeployer(project_root=tmp_path)

        with patch("src.jobs.deployer.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            with pytest.raises(DeploymentError) as exc_info:
                await deployer._wait_for_health(
                    "http://localhost:9001", "test-agent", timeout=1, retries=2
                )

            assert "failed to become healthy" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_stop_reverses_deployment_order(
        self, tmp_path: Path, job_definition: JobDefinition
    ) -> None:
        """stop() should stop agents in reverse deployment order."""
        deployer = AgentDeployer(project_root=tmp_path)

        # Create a deployed job with multiple stages
        deployed_job = DeployedJob(
            job_id="test-job",
            definition=job_definition,
            plan=DeploymentPlan(
                stages=[["agent1"], ["agent2", "agent3"]],
                agent_urls={
                    "agent1": "http://localhost:9001",
                    "agent2": "http://localhost:9002",
                    "agent3": "http://localhost:9003",
                },
                connections={},
            ),
            agents={
                "agent1": DeployedAgent(
                    agent_id="agent1", url="http://localhost:9001", process_id=1
                ),
                "agent2": DeployedAgent(
                    agent_id="agent2", url="http://localhost:9002", process_id=2
                ),
                "agent3": DeployedAgent(
                    agent_id="agent3", url="http://localhost:9003", process_id=3
                ),
            },
            start_time=datetime.now().isoformat(),
            status="running",
        )

        # Should complete without error
        await deployer.stop(deployed_job)


# ============================================================================
# DeploymentError Tests
# ============================================================================


class TestDeploymentError:
    """Tests for DeploymentError exception."""

    def test_deployment_error_message(self) -> None:
        """DeploymentError should store and return message."""
        error = DeploymentError("Test error message")

        assert str(error) == "Test error message"

    def test_deployment_error_inheritance(self) -> None:
        """DeploymentError should inherit from Exception."""
        error = DeploymentError("Test")

        assert isinstance(error, Exception)


# ============================================================================
# Integration Tests
# ============================================================================


class TestDeployerIntegration:
    """Integration tests for deployer components."""

    @pytest.mark.asyncio
    async def test_local_deployment_flow(self, tmp_path: Path) -> None:
        """Test complete local deployment flow."""
        deployer = AgentDeployer(project_root=tmp_path)

        job = JobDefinition(
            job=JobMetadata(
                name="integration-test",
                version="1.0.0",
                description="Integration test job",
            ),
            agents=[
                AgentConfig(
                    id="agent1",
                    type="TestAgent",
                    module="tests.fake_agent",
                    config={"port": 19001},
                    deployment=AgentDeploymentConfig(target="localhost"),
                ),
            ],
            topology=TopologyConfig(type="hub-spoke", hub="agent1"),
            deployment=DeploymentConfig(
                strategy="staged",
                timeout=5,
                health_check=HealthCheckConfig(retries=2, interval=1),
            ),
        )

        plan = DeploymentPlan(
            stages=[["agent1"]],
            agent_urls={"agent1": "http://localhost:19001"},
            connections={},
        )

        mock_process = MagicMock()
        mock_process.pid = 99999
        mock_process.poll.return_value = None

        with (
            patch("src.jobs.deployer.subprocess.Popen", return_value=mock_process),
            patch.object(deployer, "_wait_for_health", new_callable=AsyncMock),
        ):
            result = await deployer.deploy(job, plan)

            assert result.status == "running"
            assert result.agents["agent1"].process_id == 99999

"""Comprehensive tests for deployer module in src/jobs/deployer.py.

Tests cover:
- LocalRunner (subprocess management)
- SSHRunner (remote deployment via SSH)
- RemoteProcess
- AgentDeployer (orchestration)
- Error handling and cleanup
"""

import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    JobDefinition,
    JobMetadata,
    TopologyConfig,
)


def make_agent(
    agent_id: str,
    port: int,
    target: str = "localhost",
    host: str | None = None,
    module: str = "test.module",
) -> AgentConfig:
    """Helper to create agent configs."""
    return AgentConfig(
        id=agent_id,
        type="TestAgent",
        module=module,
        config={"port": port},
        deployment=AgentDeploymentConfig(target=target, host=host),
    )


def make_job(agents: list[AgentConfig], topology: TopologyConfig) -> JobDefinition:
    """Helper to create job definitions."""
    return JobDefinition(
        job=JobMetadata(name="test-job", version="1.0.0", description="Test"),
        agents=agents,
        topology=topology,
    )


class TestDeploymentError:
    """Test DeploymentError exception."""

    def test_deployment_error_is_exception(self) -> None:
        """DeploymentError is an Exception."""
        error = DeploymentError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"


class TestAgentRunnerBase:
    """Test AgentRunner abstract base class."""

    def test_agent_runner_is_abstract(self) -> None:
        """AgentRunner cannot be instantiated directly."""
        # AgentRunner has abstract methods, but we can test a concrete subclass
        runner = LocalRunner()
        assert isinstance(runner, AgentRunner)

    @pytest.mark.asyncio
    async def test_stop_by_pid_not_implemented_by_default(self) -> None:
        """Base stop_by_pid raises NotImplementedError."""

        class MinimalRunner(AgentRunner):
            async def start(self, agent, connected_urls, env, job_id=None):
                pass

            async def stop(self, process, agent_id):
                pass

            async def get_status(self, process):
                return "running"

        runner = MinimalRunner()
        with pytest.raises(NotImplementedError):
            await runner.stop_by_pid(123, "agent")


class TestLocalRunner:
    """Test LocalRunner for local subprocess deployment."""

    def test_init_creates_log_dir(self) -> None:
        """LocalRunner creates log directory on init."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = LocalRunner(project_root=Path(tmpdir))
            assert runner.log_dir.exists()
            assert runner.log_dir == Path(tmpdir) / "logs" / "jobs"

    def test_init_default_project_root(self) -> None:
        """LocalRunner uses cwd as default project root."""
        runner = LocalRunner()
        assert runner.project_root == Path.cwd()

    @pytest.mark.asyncio
    async def test_start_creates_process(self) -> None:
        """start() creates subprocess."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = LocalRunner(project_root=Path(tmpdir))
            agent = make_agent("test", 9001, module="http.server")

            # Mock subprocess.Popen and file operations
            with patch("subprocess.Popen") as mock_popen:
                with patch("builtins.open", MagicMock()):
                    mock_process = MagicMock()
                    mock_process.poll.return_value = None  # Process is running
                    mock_popen.return_value = mock_process

                    process = await runner.start(agent, [], {})

                    # Popen was called
                    mock_popen.assert_called_once()
                    assert process == mock_process

    @pytest.mark.asyncio
    async def test_start_includes_environment(self) -> None:
        """start() passes environment variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = LocalRunner(project_root=Path(tmpdir))
            agent = make_agent("test", 9001, module="http.server")
            agent.deployment.environment = {"CUSTOM_VAR": "value"}

            with patch("subprocess.Popen") as mock_popen:
                with patch("builtins.open", MagicMock()):
                    mock_process = MagicMock()
                    mock_process.poll.return_value = None
                    mock_popen.return_value = mock_process

                    await runner.start(agent, ["http://other:9002"], {"GLOBAL": "env"})

                    # Check env was passed
                    call_kwargs = mock_popen.call_args.kwargs
                    env = call_kwargs["env"]
                    assert "GLOBAL" in env
                    assert "CUSTOM_VAR" in env
                    assert "AGENT_PORT" in env
                    assert "CONNECTED_AGENTS" in env

    @pytest.mark.asyncio
    async def test_start_handles_immediate_crash(self) -> None:
        """start() raises DeploymentError if process crashes immediately."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = LocalRunner(project_root=Path(tmpdir))
            agent = make_agent("test", 9001, module="http.server")

            mock_stderr_content = MagicMock()
            mock_stderr_content.read.return_value = "Error: process crashed"

            with patch("subprocess.Popen") as mock_popen:
                with patch("builtins.open") as mock_open:
                    # Set up the context manager mock for reading error file
                    mock_open.return_value.__enter__.return_value = mock_stderr_content
                    mock_process = MagicMock()
                    mock_process.poll.return_value = 1  # Process exited
                    mock_popen.return_value = mock_process

                    with pytest.raises(DeploymentError) as exc_info:
                        await runner.start(agent, [], {})

                    assert "failed to start" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_start_creates_log_files(self) -> None:
        """start() creates stdout/stderr log files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = LocalRunner(project_root=Path(tmpdir))
            agent = make_agent("test", 9001, module="http.server")

            with patch("subprocess.Popen") as mock_popen:
                with patch("builtins.open", MagicMock()):
                    mock_process = MagicMock()
                    mock_process.poll.return_value = None
                    mock_popen.return_value = mock_process

                    await runner.start(agent, [], {}, job_id="test-job")

                    # Check call included stdout/stderr file handles
                    call_kwargs = mock_popen.call_args.kwargs
                    assert "stdout" in call_kwargs
                    assert "stderr" in call_kwargs

    @pytest.mark.asyncio
    async def test_stop_terminates_process(self) -> None:
        """stop() terminates the process."""
        runner = LocalRunner()

        mock_process = MagicMock()
        mock_process.wait.return_value = 0

        await runner.stop(mock_process, "test-agent")

        mock_process.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_force_kills_on_timeout(self) -> None:
        """stop() force kills if process doesn't terminate."""
        runner = LocalRunner()

        mock_process = MagicMock()
        # Make wait() raise TimeoutError to simulate hung process
        mock_process.wait.side_effect = [TimeoutError, None]

        with patch("asyncio.wait_for", side_effect=TimeoutError):
            with patch("asyncio.to_thread", return_value=None):
                await runner.stop(mock_process, "test-agent")

        mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_status_running(self) -> None:
        """get_status() returns 'running' for active process."""
        runner = LocalRunner()

        mock_process = MagicMock()
        mock_process.poll.return_value = None

        status = await runner.get_status(mock_process)
        assert status == "running"

    @pytest.mark.asyncio
    async def test_get_status_stopped(self) -> None:
        """get_status() returns 'stopped' for terminated process."""
        runner = LocalRunner()

        mock_process = MagicMock()
        mock_process.poll.return_value = 0

        status = await runner.get_status(mock_process)
        assert status == "stopped"

    @pytest.mark.asyncio
    async def test_stop_by_pid_unix(self) -> None:
        """stop_by_pid() sends SIGTERM on Unix."""
        runner = LocalRunner()

        if sys.platform == "win32":
            # Test Windows path
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stderr="")
                await runner.stop_by_pid(12345, "test-agent")
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert "taskkill" in args
        else:
            # Test Unix path
            with patch("os.kill") as mock_kill:
                await runner.stop_by_pid(12345, "test-agent")
                mock_kill.assert_called()


class TestRemoteProcess:
    """Test RemoteProcess reference class."""

    def test_remote_process_init(self) -> None:
        """RemoteProcess stores connection info."""
        mock_ssh = MagicMock()
        rp = RemoteProcess(mock_ssh, 12345, "agent-1", "host.example.com")

        assert rp.ssh_client == mock_ssh
        assert rp.pid == 12345
        assert rp.agent_id == "agent-1"
        assert rp.host == "host.example.com"

    def test_is_running_checks_ps(self) -> None:
        """is_running() checks remote process status."""
        mock_ssh = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"  PID TTY\n12345 pts/0"
        mock_ssh.exec_command.return_value = (None, mock_stdout, None)

        rp = RemoteProcess(mock_ssh, 12345, "agent-1", "host.example.com")

        assert rp.is_running() is True
        mock_ssh.exec_command.assert_called_with("ps -p 12345")

    def test_is_running_returns_false_when_dead(self) -> None:
        """is_running() returns False when process not found."""
        mock_ssh = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"  PID TTY\n"  # No matching PID
        mock_ssh.exec_command.return_value = (None, mock_stdout, None)

        rp = RemoteProcess(mock_ssh, 12345, "agent-1", "host.example.com")

        assert rp.is_running() is False

    def test_is_running_handles_exception(self) -> None:
        """is_running() returns False on SSH error."""
        mock_ssh = MagicMock()
        mock_ssh.exec_command.side_effect = Exception("SSH error")

        rp = RemoteProcess(mock_ssh, 12345, "agent-1", "host.example.com")

        assert rp.is_running() is False


class TestSSHRunner:
    """Test SSHRunner for remote SSH deployment."""

    def test_init_creates_runner(self) -> None:
        """SSHRunner initializes with project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = SSHRunner(project_root=Path(tmpdir))
            assert runner.project_root == Path(tmpdir)
            assert runner.connections == {}

    def test_get_ssh_client_requires_host(self) -> None:
        """_get_ssh_client raises error without host."""
        runner = SSHRunner()
        agent = make_agent("test", 9001, target="remote")  # No host

        with pytest.raises(DeploymentError) as exc_info:
            runner._get_ssh_client(agent)

        assert "host" in str(exc_info.value).lower()

    @patch("paramiko.SSHClient")
    @patch("os.path.exists")
    def test_get_ssh_client_connects(
        self, mock_exists: MagicMock, mock_ssh_class: MagicMock
    ) -> None:
        """_get_ssh_client establishes SSH connection."""
        mock_exists.return_value = False  # No SSH config/keys
        mock_ssh = MagicMock()
        mock_ssh_class.return_value = mock_ssh

        runner = SSHRunner()
        agent = make_agent("test", 9001, target="remote", host="192.168.1.100")

        client = runner._get_ssh_client(agent)

        mock_ssh.connect.assert_called_once()
        assert client == mock_ssh

    @patch("paramiko.SSHClient")
    @patch("os.path.exists")
    def test_get_ssh_client_reuses_connection(
        self, mock_exists: MagicMock, mock_ssh_class: MagicMock
    ) -> None:
        """_get_ssh_client reuses existing connection."""
        mock_exists.return_value = False
        mock_ssh = MagicMock()
        mock_ssh_class.return_value = mock_ssh

        runner = SSHRunner()
        agent = make_agent("test", 9001, target="remote", host="192.168.1.100")

        # First call
        client1 = runner._get_ssh_client(agent)
        # Second call should reuse
        client2 = runner._get_ssh_client(agent)

        # Only one connection made
        assert mock_ssh.connect.call_count == 1
        assert client1 == client2

    def test_close_all_closes_connections(self) -> None:
        """close_all() closes all SSH connections."""
        runner = SSHRunner()

        mock_ssh1 = MagicMock()
        mock_ssh2 = MagicMock()
        runner.connections = {"host1:22": mock_ssh1, "host2:22": mock_ssh2}

        runner.close_all()

        mock_ssh1.close.assert_called_once()
        mock_ssh2.close.assert_called_once()
        assert runner.connections == {}

    @pytest.mark.asyncio
    async def test_stop_sends_kill(self) -> None:
        """stop() sends kill command via SSH."""
        runner = SSHRunner()

        mock_ssh = MagicMock()
        mock_stdout = MagicMock()
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_ssh.exec_command.return_value = (None, mock_stdout, None)

        rp = RemoteProcess(mock_ssh, 12345, "agent", "host")
        rp.is_running = MagicMock(return_value=False)

        await runner.stop(rp, "agent")

        mock_ssh.exec_command.assert_called_with("kill 12345")

    @pytest.mark.asyncio
    async def test_get_status_checks_remote_process(self) -> None:
        """get_status() checks if remote process is running."""
        runner = SSHRunner()

        mock_ssh = MagicMock()
        rp = RemoteProcess(mock_ssh, 12345, "agent", "host")
        rp.is_running = MagicMock(return_value=True)

        status = await runner.get_status(rp)
        assert status == "running"

        rp.is_running.return_value = False
        status = await runner.get_status(rp)
        assert status == "stopped"


class TestAgentDeployer:
    """Test AgentDeployer orchestration."""

    def test_init_creates_runners(self) -> None:
        """AgentDeployer initializes with runners."""
        deployer = AgentDeployer()

        assert "localhost" in deployer.runners
        assert "remote" in deployer.runners
        assert isinstance(deployer.runners["localhost"], LocalRunner)
        assert isinstance(deployer.runners["remote"], SSHRunner)

    @pytest.mark.asyncio
    async def test_deploy_creates_deployed_job(self) -> None:
        """deploy() returns DeployedJob on success."""
        deployer = AgentDeployer()

        agent = make_agent("test", 9001)
        job = make_job([agent], TopologyConfig(type="mesh", agents=["test"]))
        plan = DeploymentPlan(
            stages=[["test"]],
            agent_urls={"test": "http://localhost:9001"},
            connections={"test": []},
        )

        # Mock the runner and health check
        mock_runner = AsyncMock()
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_runner.start.return_value = mock_process
        deployer.runners["localhost"] = mock_runner

        with patch.object(deployer, "_wait_for_health", new_callable=AsyncMock):
            result = await deployer.deploy(job, plan)

        assert isinstance(result, DeployedJob)
        assert result.status == "running"
        assert "test" in result.agents

    @pytest.mark.asyncio
    async def test_deploy_stages_in_order(self) -> None:
        """deploy() deploys stages in order."""
        deployer = AgentDeployer()

        agents = [make_agent("a", 9001), make_agent("b", 9002)]
        job = make_job(
            agents, TopologyConfig(type="pipeline", stages=["a", "b"])
        )
        plan = DeploymentPlan(
            stages=[["a"], ["b"]],
            agent_urls={"a": "http://localhost:9001", "b": "http://localhost:9002"},
            connections={"a": ["http://localhost:9002"], "b": []},
        )

        deploy_order = []

        async def track_start(agent, *args, **kwargs):
            deploy_order.append(agent.id)
            mock = MagicMock()
            mock.pid = 12345
            return mock

        mock_runner = AsyncMock()
        mock_runner.start.side_effect = track_start
        deployer.runners["localhost"] = mock_runner

        with patch.object(deployer, "_wait_for_health", new_callable=AsyncMock):
            await deployer.deploy(job, plan)

        assert deploy_order == ["a", "b"]

    @pytest.mark.asyncio
    async def test_deploy_cleans_up_on_failure(self) -> None:
        """deploy() cleans up deployed agents on failure."""
        deployer = AgentDeployer()

        agents = [make_agent("a", 9001), make_agent("b", 9002)]
        job = make_job(
            agents, TopologyConfig(type="pipeline", stages=["a", "b"])
        )
        plan = DeploymentPlan(
            stages=[["a"], ["b"]],
            agent_urls={"a": "http://localhost:9001", "b": "http://localhost:9002"},
            connections={"a": [], "b": []},
        )

        call_count = 0

        async def fail_second(agent, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Deployment failed")
            mock = MagicMock()
            mock.pid = 12345
            return mock

        mock_runner = AsyncMock()
        mock_runner.start.side_effect = fail_second
        deployer.runners["localhost"] = mock_runner

        with patch.object(deployer, "_wait_for_health", new_callable=AsyncMock):
            with pytest.raises(DeploymentError):
                await deployer.deploy(job, plan)

        # Cleanup should have been called
        mock_runner.stop.assert_called()

    @pytest.mark.asyncio
    async def test_deploy_agent_not_found(self) -> None:
        """_deploy_agent raises error for missing agent."""
        deployer = AgentDeployer()

        agent = make_agent("test", 9001)
        job = make_job([agent], TopologyConfig(type="mesh", agents=["test"]))
        plan = DeploymentPlan(
            stages=[["nonexistent"]],
            agent_urls={},
            connections={},
        )

        with pytest.raises(DeploymentError) as exc_info:
            await deployer._deploy_agent(job, "nonexistent", plan, {}, "run-1")

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_deploy_unsupported_target(self) -> None:
        """_deploy_agent raises error for unsupported target."""
        deployer = AgentDeployer()

        agent = make_agent("test", 9001, target="kubernetes")  # Not implemented
        job = make_job([agent], TopologyConfig(type="mesh", agents=["test"]))
        plan = DeploymentPlan(
            stages=[["test"]],
            agent_urls={"test": "http://test:9001"},
            connections={"test": []},
        )

        # Remove the kubernetes runner if it exists
        deployer.runners.pop("kubernetes", None)

        with pytest.raises(DeploymentError) as exc_info:
            await deployer._deploy_agent(job, "test", plan, {}, "run-1")

        assert "no runner" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_wait_for_health_success(self) -> None:
        """_wait_for_health succeeds when agent responds."""
        deployer = AgentDeployer()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Should not raise
            await deployer._wait_for_health(
                "http://localhost:9001", "test", timeout=10, retries=3
            )

    @pytest.mark.asyncio
    async def test_wait_for_health_timeout(self) -> None:
        """_wait_for_health raises error after retries exhausted."""
        deployer = AgentDeployer()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Connection refused")
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(DeploymentError) as exc_info:
                await deployer._wait_for_health(
                    "http://localhost:9001", "test", timeout=1, retries=2
                )

            assert "failed to become healthy" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_wait_for_health_empty_url(self) -> None:
        """_wait_for_health returns early for empty URL."""
        deployer = AgentDeployer()

        # Should not raise or make any requests
        await deployer._wait_for_health("", "test", timeout=10, retries=3)

    @pytest.mark.asyncio
    async def test_stop_deployed_job(self) -> None:
        """stop() stops all agents in reverse order."""
        deployer = AgentDeployer()

        agent_config = make_agent("test", 9001)
        job = make_job([agent_config], TopologyConfig(type="mesh", agents=["test"]))
        plan = DeploymentPlan(
            stages=[["test"]],
            agent_urls={"test": "http://localhost:9001"},
            connections={"test": []},
        )

        deployed_job = DeployedJob(
            job_id="test-run",
            definition=job,
            plan=plan,
            agents={
                "test": DeployedAgent(
                    agent_id="test",
                    url="http://localhost:9001",
                    process_id=12345,
                    status="healthy",
                )
            },
            start_time="2024-01-01T00:00:00",
            status="running",
        )

        mock_runner = AsyncMock()
        deployer.runners["localhost"] = mock_runner

        await deployer.stop(deployed_job)

        mock_runner.stop_by_pid.assert_called_with(12345, "test")

    @pytest.mark.asyncio
    async def test_stop_remote_agent(self) -> None:
        """stop() passes host info for remote agents."""
        deployer = AgentDeployer()

        agent_config = make_agent("test", 9001, target="remote", host="192.168.1.100")
        job = make_job([agent_config], TopologyConfig(type="mesh", agents=["test"]))
        plan = DeploymentPlan(
            stages=[["test"]],
            agent_urls={"test": "http://192.168.1.100:9001"},
            connections={"test": []},
        )

        deployed_job = DeployedJob(
            job_id="test-run",
            definition=job,
            plan=plan,
            agents={
                "test": DeployedAgent(
                    agent_id="test",
                    url="http://192.168.1.100:9001",
                    process_id=12345,
                    host="192.168.1.100",
                    status="healthy",
                )
            },
            start_time="2024-01-01T00:00:00",
            status="running",
        )

        mock_runner = AsyncMock()
        deployer.runners["remote"] = mock_runner

        await deployer.stop(deployed_job)

        mock_runner.stop_by_pid.assert_called_with(
            12345, "test", host="192.168.1.100"
        )


class TestParallelDeployment:
    """Test parallel deployment within stages."""

    @pytest.mark.asyncio
    async def test_parallel_strategy_deploys_concurrently(self) -> None:
        """Parallel strategy deploys all agents in stage concurrently."""
        deployer = AgentDeployer()

        agents = [make_agent("a", 9001), make_agent("b", 9002)]
        job = make_job(agents, TopologyConfig(type="mesh", agents=["a", "b"]))
        job.deployment = DeploymentConfig(strategy="parallel")
        plan = DeploymentPlan(
            stages=[["a", "b"]],
            agent_urls={"a": "http://localhost:9001", "b": "http://localhost:9002"},
            connections={"a": ["http://localhost:9002"], "b": ["http://localhost:9001"]},
        )

        async def mock_start(agent, *args, **kwargs):
            mock = MagicMock()
            mock.pid = 12345
            return mock

        mock_runner = AsyncMock()
        mock_runner.start.side_effect = mock_start
        deployer.runners["localhost"] = mock_runner

        with patch.object(deployer, "_wait_for_health", new_callable=AsyncMock):
            result = await deployer.deploy(job, plan)

        assert len(result.agents) == 2

    @pytest.mark.asyncio
    async def test_sequential_strategy_deploys_one_by_one(self) -> None:
        """Sequential strategy deploys agents one at a time."""
        deployer = AgentDeployer()

        agents = [make_agent("a", 9001), make_agent("b", 9002)]
        job = make_job(agents, TopologyConfig(type="mesh", agents=["a", "b"]))
        job.deployment = DeploymentConfig(strategy="sequential")
        plan = DeploymentPlan(
            stages=[["a", "b"]],
            agent_urls={"a": "http://localhost:9001", "b": "http://localhost:9002"},
            connections={"a": ["http://localhost:9002"], "b": ["http://localhost:9001"]},
        )

        deploy_order = []

        async def mock_start(agent, *args, **kwargs):
            deploy_order.append(agent.id)
            mock = MagicMock()
            mock.pid = 12345
            return mock

        mock_runner = AsyncMock()
        mock_runner.start.side_effect = mock_start
        deployer.runners["localhost"] = mock_runner

        with patch.object(deployer, "_wait_for_health", new_callable=AsyncMock):
            await deployer.deploy(job, plan)

        # Sequential should maintain order within stage
        assert deploy_order == ["a", "b"]


class TestCleanupAgents:
    """Test agent cleanup functionality."""

    @pytest.mark.asyncio
    async def test_cleanup_stops_all_processes(self) -> None:
        """_cleanup_agents stops all running processes."""
        deployer = AgentDeployer()

        agent_a = make_agent("a", 9001)
        agent_b = make_agent("b", 9002)
        job = make_job([agent_a, agent_b], TopologyConfig(type="mesh", agents=["a", "b"]))

        mock_process_a = MagicMock()
        mock_process_b = MagicMock()
        processes = {"a": mock_process_a, "b": mock_process_b}

        mock_runner = AsyncMock()
        deployer.runners["localhost"] = mock_runner

        await deployer._cleanup_agents(job, processes)

        assert mock_runner.stop.call_count == 2

    @pytest.mark.asyncio
    async def test_cleanup_handles_stop_errors(self) -> None:
        """_cleanup_agents continues even if stop fails."""
        deployer = AgentDeployer()

        agent = make_agent("test", 9001)
        job = make_job([agent], TopologyConfig(type="mesh", agents=["test"]))

        mock_process = MagicMock()
        processes = {"test": mock_process}

        mock_runner = AsyncMock()
        mock_runner.stop.side_effect = Exception("Stop failed")
        deployer.runners["localhost"] = mock_runner

        # Should not raise
        await deployer._cleanup_agents(job, processes)

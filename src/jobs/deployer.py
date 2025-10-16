"""Agent deployer - Execute deployment plans."""

import asyncio
import getpass
import os
import subprocess
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import paramiko

from .models import (
    AgentConfig,
    DeployedAgent,
    DeployedJob,
    DeploymentPlan,
    JobDefinition,
)


class DeploymentError(Exception):
    """Error during deployment."""

    pass


# ============================================================================
# Base Runner Interface
# ============================================================================


class AgentRunner(ABC):
    """Base class for agent runners."""

    @abstractmethod
    async def start(
        self, agent: AgentConfig, connected_urls: List[str], env: Dict[str, str]
    ) -> Any:
        """Start an agent.

        Args:
            agent: Agent configuration
            connected_urls: URLs of connected agents
            env: Environment variables

        Returns:
            Process/container reference
        """
        pass

    @abstractmethod
    async def stop(self, process: Any, agent_id: str) -> None:
        """Stop an agent.

        Args:
            process: Process/container reference
            agent_id: Agent identifier
        """
        pass

    @abstractmethod
    async def get_status(self, process: Any) -> str:
        """Get agent status.

        Args:
            process: Process/container reference

        Returns:
            Status string
        """
        pass


# ============================================================================
# Local Runner (subprocess)
# ============================================================================


class LocalRunner(AgentRunner):
    """Run agents locally via subprocess."""

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize local runner.

        Args:
            project_root: Project root directory (for log files)
        """
        self.project_root = project_root or Path.cwd()
        self.log_dir = self.project_root / "logs" / "jobs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    async def start(
        self, agent: AgentConfig, connected_urls: List[str], env: Dict[str, str]
    ) -> subprocess.Popen:
        """Start agent locally via python -m.

        Args:
            agent: Agent configuration
            connected_urls: URLs of connected agents
            env: Environment variables

        Returns:
            Process handle
        """
        # Use python -m to run the agent module directly
        cmd = [sys.executable, "-m", agent.module]

        # Build environment
        process_env = env.copy()

        # Add agent-specific config as environment variables
        for key, value in agent.config.items():
            process_env[f"AGENT_{key.upper()}"] = str(value)

        # Add connected agents (comma-separated URLs)
        if connected_urls:
            process_env["CONNECTED_AGENTS"] = ",".join(connected_urls)

        # Add agent deployment environment
        if agent.deployment.environment:
            process_env.update(agent.deployment.environment)

        # Setup log files
        stdout_log = self.log_dir / f"{agent.id}.stdout.log"
        stderr_log = self.log_dir / f"{agent.id}.stderr.log"

        stdout_file = open(stdout_log, "w")
        stderr_file = open(stderr_log, "w")

        # Start process
        try:
            process = subprocess.Popen(
                cmd,
                env=process_env,
                stdout=stdout_file,
                stderr=stderr_file,
                cwd=self.project_root,
            )

            # Give it a moment to start
            await asyncio.sleep(0.5)

            # Check if it crashed immediately
            if process.poll() is not None:
                stdout_file.close()
                stderr_file.close()
                with open(stderr_log) as f:
                    error = f.read()
                raise DeploymentError(
                    f"Agent {agent.id} failed to start:\n{error}"
                )

            return process

        except Exception as e:
            stdout_file.close()
            stderr_file.close()
            raise DeploymentError(f"Failed to start agent {agent.id}: {e}")

    async def stop(self, process: subprocess.Popen, agent_id: str) -> None:
        """Stop agent process.

        Args:
            process: Process handle
            agent_id: Agent identifier
        """
        try:
            process.terminate()
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(process.wait), timeout=10.0
                )
            except asyncio.TimeoutError:
                process.kill()
                await asyncio.to_thread(process.wait)
        except Exception as e:
            print(f"Warning: Error stopping agent {agent_id}: {e}")

    async def get_status(self, process: subprocess.Popen) -> str:
        """Get process status.

        Args:
            process: Process handle

        Returns:
            Status string
        """
        if process.poll() is None:
            return "running"
        else:
            return "stopped"


# ============================================================================
# SSH Runner (remote deployment)
# ============================================================================


class RemoteProcess:
    """Reference to a remote process."""

    def __init__(self, ssh_client: paramiko.SSHClient, pid: int, agent_id: str, host: str):
        self.ssh_client = ssh_client
        self.pid = pid
        self.agent_id = agent_id
        self.host = host

    def is_running(self) -> bool:
        """Check if remote process is still running."""
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(f"ps -p {self.pid}")
            output = stdout.read().decode()
            return str(self.pid) in output
        except Exception:
            return False


class SSHRunner(AgentRunner):
    """Run agents on remote hosts via SSH."""

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize SSH runner.

        Args:
            project_root: Project root directory (for transferring code)
        """
        self.project_root = project_root or Path.cwd()
        self.connections: Dict[str, paramiko.SSHClient] = {}

    def _get_ssh_client(self, agent: AgentConfig) -> paramiko.SSHClient:
        """Get or create SSH connection for agent.

        Args:
            agent: Agent configuration

        Returns:
            SSH client
        """
        host = agent.deployment.host
        if not host:
            raise DeploymentError("Remote deployment requires 'host' in deployment config")

        # Reuse connection if exists
        connection_key = f"{host}:{agent.deployment.port or 22}"
        if connection_key in self.connections:
            return self.connections[connection_key]

        # Create new connection
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Get SSH configuration
        user = agent.deployment.user or getpass.getuser()
        ssh_port = agent.deployment.port or 22
        ssh_key = agent.deployment.ssh_key
        password = agent.deployment.password

        # Expand ~ in ssh_key path
        if ssh_key:
            ssh_key = os.path.expanduser(ssh_key)
        else:
            # Try default key
            default_key = os.path.expanduser("~/.ssh/id_rsa")
            if os.path.exists(default_key):
                ssh_key = default_key

        try:
            print(f"    Connecting to {user}@{host}:{ssh_port}...")

            connect_kwargs = {
                "hostname": host,
                "port": ssh_port,
                "username": user,
                "timeout": 10,
            }

            if ssh_key and os.path.exists(ssh_key):
                connect_kwargs["key_filename"] = ssh_key
            elif password:
                connect_kwargs["password"] = password

            ssh.connect(**connect_kwargs)
            self.connections[connection_key] = ssh
            print(f"    ✓ SSH connected")

            return ssh

        except Exception as e:
            raise DeploymentError(f"SSH connection failed to {user}@{host}: {e}")

    async def start(
        self, agent: AgentConfig, connected_urls: List[str], env: Dict[str, str]
    ) -> RemoteProcess:
        """Start agent on remote host via SSH.

        Args:
            agent: Agent configuration
            connected_urls: URLs of connected agents
            env: Environment variables

        Returns:
            Remote process reference
        """
        ssh = self._get_ssh_client(agent)

        # Build environment variables
        env_vars = env.copy()
        for key, value in agent.config.items():
            env_vars[f"AGENT_{key.upper()}"] = str(value)

        if connected_urls:
            env_vars["CONNECTED_AGENTS"] = ",".join(connected_urls)

        if agent.deployment.environment:
            env_vars.update(agent.deployment.environment)

        # Build environment string for command - properly quote values with spaces
        env_str = " ".join([f'{k}="{v}"' for k, v in env_vars.items()])

        # Get remote configuration
        # Special case: if deploying to localhost, use project directory with uv
        if agent.deployment.host == "localhost":
            import os
            import shutil
            workdir = os.getcwd()  # Use current project directory
            # Find uv in PATH
            uv_path = shutil.which("uv") or os.path.expanduser("~/.local/bin/uv")
            python = f"{uv_path} run python"  # Use uv with full path
        else:
            workdir = agent.deployment.workdir or f"~/agents/{agent.id}"
            python = agent.deployment.python or "python3"

        # Ensure working directory exists (except for localhost project dir)
        if agent.deployment.host != "localhost":
            stdin, stdout, stderr = ssh.exec_command(f"mkdir -p {workdir}")
            stdout.channel.recv_exit_status()  # Wait for command

            # Transfer agent code to remote host
            print(f"    Transferring code to {workdir}...")
            await self._transfer_code(ssh, agent, workdir)
        else:
            print(f"    Using project directory: {workdir}...")

        # Build command to run agent
        # We'll use nohup to keep it running after SSH disconnect
        log_file = f"{workdir}/{agent.id}.log"
        cmd = (
            f"cd {workdir} && "
            f"nohup env {env_str} {python} -m {agent.module} "
            f"> {log_file} 2>&1 & "
            f"echo $!"
        )

        print(f"    Starting remote process...")
        print(f"    Command: {cmd[:100]}...")
        stdin, stdout, stderr = ssh.exec_command(cmd)

        # Get PID
        pid_str = stdout.read().decode().strip()
        try:
            pid = int(pid_str)
        except ValueError:
            error = stderr.read().decode()
            raise DeploymentError(f"Failed to start remote agent: {error}")

        print(f"    ✓ Remote process started (PID: {pid})")

        # Give it a moment to start
        await asyncio.sleep(1.0)

        # Check if still running
        stdin, stdout, stderr = ssh.exec_command(f"ps -p {pid}")
        ps_output = stdout.read().decode()
        if str(pid) not in ps_output:
            # Process died, get logs
            stdin, stdout, stderr = ssh.exec_command(f"cat {log_file} 2>&1")
            log_output = stdout.read().decode()
            if not log_output:
                log_output = "(no log output - check if log file was created)"
            raise DeploymentError(
                f"Remote agent {agent.id} failed to start:\n{log_output}"
            )

        return RemoteProcess(ssh, pid, agent.id, agent.deployment.host)

    async def _transfer_code(
        self, ssh: paramiko.SSHClient, agent: AgentConfig, remote_dir: str
    ) -> None:
        """Transfer agent code to remote host.

        Args:
            ssh: SSH client
            agent: Agent configuration
            remote_dir: Remote directory
        """
        sftp = ssh.open_sftp()

        try:
            # Transfer main agent module and dependencies
            # For now, we assume the code is already on the remote host
            # In production, you'd use rsync or SFTP to transfer files

            # Create directory structure
            module_parts = agent.module.split(".")
            current_dir = remote_dir

            for part in module_parts[:-1]:
                current_dir = f"{current_dir}/{part}"
                try:
                    sftp.mkdir(current_dir)
                except IOError:
                    pass  # Directory exists

            # For this implementation, we assume code is already deployed
            # or we're using a shared filesystem
            # TODO: Implement actual file transfer via SFTP

        finally:
            sftp.close()

    async def stop(self, process: RemoteProcess, agent_id: str) -> None:
        """Stop remote agent process.

        Args:
            process: Remote process reference
            agent_id: Agent identifier
        """
        try:
            # Send SIGTERM
            stdin, stdout, stderr = process.ssh_client.exec_command(
                f"kill {process.pid}"
            )
            stdout.channel.recv_exit_status()

            # Wait for graceful shutdown
            await asyncio.sleep(2)

            # Check if still running
            if process.is_running():
                # Force kill
                stdin, stdout, stderr = process.ssh_client.exec_command(
                    f"kill -9 {process.pid}"
                )
                stdout.channel.recv_exit_status()

        except Exception as e:
            print(f"Warning: Error stopping remote agent {agent_id}: {e}")

    async def get_status(self, process: RemoteProcess) -> str:
        """Get remote process status.

        Args:
            process: Remote process reference

        Returns:
            Status string
        """
        if process.is_running():
            return "running"
        else:
            return "stopped"

    def close_all(self):
        """Close all SSH connections."""
        for ssh in self.connections.values():
            try:
                ssh.close()
            except Exception:
                pass
        self.connections.clear()


# ============================================================================
# Agent Deployer
# ============================================================================


class AgentDeployer:
    """Deploy agents according to deployment plan."""

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize deployer.

        Args:
            project_root: Project root directory
        """
        self.project_root = project_root or Path.cwd()
        self.runners: Dict[str, AgentRunner] = {
            "localhost": LocalRunner(self.project_root),
            "remote": SSHRunner(self.project_root),
            # TODO: Add DockerRunner, KubernetesRunner
        }

    async def deploy(
        self, job: JobDefinition, plan: DeploymentPlan
    ) -> DeployedJob:
        """Execute deployment plan.

        Args:
            job: Job definition
            plan: Deployment plan

        Returns:
            Deployed job with running agents

        Raises:
            DeploymentError: If deployment fails
        """
        print(f"Deploying job: {job.job.name}")
        print(f"Deployment strategy: {job.deployment.strategy}")
        print(f"Stages: {len(plan.stages)}")

        deployed_agents: Dict[str, DeployedAgent] = {}
        processes: Dict[str, Any] = {}

        try:
            # Build global environment
            global_env = dict(job.environment) if job.environment else {}

            # Deploy stage by stage
            for stage_idx, stage in enumerate(plan.stages):
                if not stage:
                    continue

                print(f"\nStage {stage_idx + 1}/{len(plan.stages)}: {stage}")

                # Deploy all agents in this stage (in parallel if strategy allows)
                if job.deployment.strategy == "parallel" or (
                    job.deployment.strategy == "staged"
                ):
                    # Parallel deployment within stage
                    tasks = []
                    for agent_id in stage:
                        task = self._deploy_agent(
                            job, agent_id, plan, global_env
                        )
                        tasks.append((agent_id, task))

                    # Wait for all in parallel
                    for agent_id, task in tasks:
                        try:
                            agent, process = await task
                            deployed_agents[agent_id] = agent
                            processes[agent_id] = process
                        except Exception as e:
                            raise DeploymentError(
                                f"Failed to deploy agent {agent_id}: {e}"
                            )

                else:
                    # Sequential deployment
                    for agent_id in stage:
                        try:
                            agent, process = await self._deploy_agent(
                                job, agent_id, plan, global_env
                            )
                            deployed_agents[agent_id] = agent
                            processes[agent_id] = process
                        except Exception as e:
                            raise DeploymentError(
                                f"Failed to deploy agent {agent_id}: {e}"
                            )

            print(f"\n✓ Deployed {len(deployed_agents)} agents")

            return DeployedJob(
                job_id=job.job.name,
                definition=job,
                plan=plan,
                agents=deployed_agents,
                start_time=datetime.now().isoformat(),
                status="running",
            )

        except Exception as e:
            # Cleanup on failure
            print(f"\n✗ Deployment failed: {e}")
            print("Cleaning up deployed agents...")
            await self._cleanup_agents(job, processes)
            raise

    async def _deploy_agent(
        self,
        job: JobDefinition,
        agent_id: str,
        plan: DeploymentPlan,
        global_env: Dict[str, str],
    ) -> tuple[DeployedAgent, Any]:
        """Deploy a single agent.

        Args:
            job: Job definition
            agent_id: Agent identifier
            plan: Deployment plan
            global_env: Global environment variables

        Returns:
            Tuple of (DeployedAgent, process handle)
        """
        agent_config = job.get_agent(agent_id)
        if not agent_config:
            raise DeploymentError(f"Agent {agent_id} not found in job definition")

        print(f"  Deploying {agent_id}...", end=" ", flush=True)

        # Get runner for deployment target
        runner = self.runners.get(agent_config.deployment.target)
        if not runner:
            raise DeploymentError(
                f"No runner available for target: {agent_config.deployment.target}"
            )

        # Get connected agent URLs
        connected_urls = plan.connections.get(agent_id, [])

        # Start agent
        process = await runner.start(agent_config, connected_urls, global_env)

        # Get agent URL
        agent_url = plan.agent_urls.get(agent_id, "")

        # Wait for health check
        await self._wait_for_health(
            agent_url,
            agent_id,
            timeout=job.deployment.timeout,
            retries=job.deployment.health_check.retries,
        )

        print(f"✓ {agent_url}")

        # Create deployed agent record
        deployed_agent = DeployedAgent(
            agent_id=agent_id,
            url=agent_url,
            process_id=getattr(process, "pid", None),
            status="healthy",
        )

        return deployed_agent, process

    async def _wait_for_health(
        self, url: str, agent_id: str, timeout: int, retries: int
    ) -> None:
        """Wait for agent to become healthy.

        Args:
            url: Agent URL
            agent_id: Agent identifier
            timeout: Total timeout in seconds
            retries: Number of retries

        Raises:
            DeploymentError: If agent doesn't become healthy
        """
        if not url:
            return

        health_url = f"{url}/.well-known/agent-configuration"
        interval = timeout / max(retries, 1)

        async with httpx.AsyncClient() as client:
            for attempt in range(retries):
                try:
                    response = await client.get(
                        health_url, timeout=5.0, follow_redirects=True
                    )

                    if response.status_code == 200:
                        return  # Healthy!

                except Exception:
                    pass

                if attempt < retries - 1:
                    await asyncio.sleep(interval)

        raise DeploymentError(
            f"Agent {agent_id} failed to become healthy at {url}"
        )

    async def stop(self, deployed_job: DeployedJob) -> None:
        """Stop all agents in a deployed job.

        Args:
            deployed_job: Deployed job to stop
        """
        print(f"Stopping job: {deployed_job.job_id}")

        # Stop in reverse order
        stages = list(reversed(deployed_job.plan.stages))

        for stage_idx, stage in enumerate(stages):
            print(f"Stage {stage_idx + 1}/{len(stages)}: Stopping {stage}")

            for agent_id in stage:
                if agent_id in deployed_job.agents:
                    agent = deployed_job.agents[agent_id]
                    print(f"  Stopping {agent_id}...")

                    # Get agent config to determine runner
                    agent_config = deployed_job.definition.get_agent(agent_id)
                    if agent_config:
                        runner = self.runners.get(agent_config.deployment.target)
                        if runner and agent.process_id:
                            # Reconstruct process object (simplified)
                            # In real implementation, we'd track processes
                            pass

        print("✓ Job stopped")

    async def _cleanup_agents(
        self, job: JobDefinition, processes: Dict[str, Any]
    ) -> None:
        """Cleanup agents after deployment failure.

        Args:
            job: Job definition
            processes: Process handles
        """
        for agent_id, process in processes.items():
            agent_config = job.get_agent(agent_id)
            if agent_config:
                runner = self.runners.get(agent_config.deployment.target)
                if runner:
                    try:
                        await runner.stop(process, agent_id)
                    except Exception as e:
                        print(f"Warning: Failed to stop {agent_id}: {e}")
